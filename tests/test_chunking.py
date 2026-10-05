"""
Property tests for the causal offset. No torch, no model, milliseconds.

The rule these cover is the highest-risk logic in the architecture: a leak makes
downstream numbers look *better*, so it cannot be caught by watching the metric.
Keeping the arithmetic in a dependency-free module means it can be checked
exhaustively over a grid of sizes rather than spot-checked against tensors.

The central invariant, stated once and tested three ways below:

    a position may only attend a bank whose source chunk ended at or before it.
"""

from __future__ import annotations

import pytest

from tahi.native.chunking import (
    active_query_chunk,
    chunk_spans,
    query_span,
    retrieval_plan,
    window_plan,
)

SIZES = [1, 2, 3, 4, 5, 7, 8, 16, 64]
LENGTHS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 64, 65, 100, 129]


# --------------------------------------------------------------------------- #
# the invariant
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("m", SIZES)
@pytest.mark.parametrize("seq_len", LENGTHS)
def test_no_position_attends_a_chunk_that_has_not_ended(seq_len, m):
    """For every position, the bank it may attend was keyed on earlier tokens.

    `query_span(u)` ends at `(u+1)*m`; the first position allowed to attend it is
    `u*m + m - 1 = (u+1)*m - 1`. So the span must end at or before `position + 1`
    -- every source token is already an input when the bank is used.
    """
    for spec in retrieval_plan(seq_len, m):
        if not spec.attends_to_retrieval:
            continue
        _, src_end = query_span(spec.query_chunk, m)
        assert src_end <= spec.start + 1, (
            f"m={m} seq_len={seq_len}: window starting at {spec.start} attends a "
            f"chunk ending at {src_end} -- retrieval keyed on unwritten tokens"
        )


@pytest.mark.parametrize("m", SIZES)
@pytest.mark.parametrize("seq_len", LENGTHS)
def test_plan_and_active_query_chunk_agree(seq_len, m):
    """The layer reads the plan; the decode loop calls `active_query_chunk`.

    They are two entry points to one rule, and they must never disagree -- that
    disagreement is exactly how training and inference end up on different grids.
    """
    for spec in retrieval_plan(seq_len, m):
        for pos in range(spec.start, spec.end):
            assert active_query_chunk(pos, m) == spec.query_chunk


@pytest.mark.parametrize("m", SIZES)
@pytest.mark.parametrize("seq_len", LENGTHS)
def test_plan_tiles_the_sequence_exactly_once(seq_len, m):
    covered = [p for spec in retrieval_plan(seq_len, m)
               for p in range(spec.start, spec.end)]
    assert covered == list(range(seq_len))


@pytest.mark.parametrize("m", SIZES)
def test_head_positions_attend_nothing(m):
    """Positions before the first completed chunk have no legal bank."""
    for pos in range(m - 1):
        assert active_query_chunk(pos, m) is None
    assert active_query_chunk(m - 1, m) == 0


# --------------------------------------------------------------------------- #
# window_plan: the incremental-decode path
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("m", [3, 4, 8, 64])
@pytest.mark.parametrize("offset", [0, 1, 5, 6, 63, 64, 65, 100])
@pytest.mark.parametrize("length", [1, 2, 7])
def test_window_plan_matches_the_full_plan(m, offset, length):
    """A window's spans must be the full plan's spans, shifted into local coords.

    Deriving the plan from the window's own length instead would describe position
    0 rather than the real position -- the bug MAAILMA measured at EM 0.250
    against 1.000 for one checkpoint, because every span fell outside the tensor
    and cross-attention silently did nothing.
    """
    win = window_plan(m, offset, length)
    assert [p for s in win for p in range(s.start, s.end)] == list(range(length))
    for spec in win:
        for local in range(spec.start, spec.end):
            assert active_query_chunk(offset + local, m) == spec.query_chunk


def test_window_plan_of_one_token_is_that_token_s_bank():
    """The decode case: S=1 at absolute position `offset`."""
    for offset in range(20):
        win = window_plan(4, offset, 1)
        assert len(win) == 1
        assert (win[0].start, win[0].end) == (0, 1)
        assert win[0].query_chunk == active_query_chunk(offset, 4)


def test_window_plan_empty_for_nonpositive_length():
    assert window_plan(4, 10, 0) == []
    assert window_plan(4, 10, -1) == []


# --------------------------------------------------------------------------- #
# spans and guards
# --------------------------------------------------------------------------- #

def test_chunk_spans_partial_tail():
    assert chunk_spans(140, 64) == [(0, 64), (64, 128), (128, 140)]
    assert chunk_spans(0, 64) == []


def test_query_span_prefix_is_speculative_not_causal_relief():
    """A prefix shortens the query, never extends it past the chunk."""
    assert query_span(1, 64) == (64, 128)
    assert query_span(1, 64, prefix=48) == (64, 112)
    with pytest.raises(ValueError):
        query_span(1, 64, prefix=65)
    with pytest.raises(ValueError):
        query_span(1, 64, prefix=0)


def test_invalid_sizes_raise():
    with pytest.raises(ValueError):
        chunk_spans(10, 0)
    with pytest.raises(ValueError):
        chunk_spans(-1, 4)
    with pytest.raises(ValueError):
        active_query_chunk(5, 0)
