"""Chunk geometry and the causal offset, as data rather than tensor arithmetic.

Deliberately dependency-free -- no torch, no numpy. The causal rule is the
highest-risk logic in the whole architecture: a leak here produces *better*
looking numbers downstream, which is the worst kind of bug because it resembles
success. Keeping the arithmetic separate from tensor code means it can be
exhaustively property-tested in milliseconds with no model loaded, and it means
`gcca_layer.py` consumes a plan instead of recomputing indices in a reshape.

Convention borrowed from the sibling MAAILMA project (`src/chunking.py` there),
which reached this design first and has the property tests to show for it.

**The rule (RETRO, Borgeaud et al. ICML 2022, sec. 2.4).** The sequence is split
into chunks of `m` tokens. Bank `R_u = ANN(C_u)` is retrieved from chunk `u`. The
*attending window* for `R_u` begins at the LAST token of `C_u` -- absolute
position `u*m + m - 1` -- and runs `m` positions. Positions `[0, m-1)` precede
any completed chunk and attend nothing.

Why the shift rather than the simpler "chunk `C_i` attends `R_{i-1}`": the hidden
state at position `p` predicts token `p+1`, and `R_u` is keyed on tokens up to and
including `u*m + m - 1`, all of which are already inputs at that position. So the
shifted form is causal *and* maximally fresh -- staleness is bounded by `m` rather
than `2m`. MAAILMA uses the chunk-aligned form, one token more conservative; the
difference is immaterial to any claim but the two must not be silently mixed,
because the decode loop and the training path have to agree exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ChunkSpec",
    "active_query_chunk",
    "chunk_spans",
    "query_span",
    "retrieval_plan",
    "window_plan",
]


@dataclass(frozen=True)
class ChunkSpec:
    """One attending window and the retrieval it is allowed to condition on."""

    index: int
    """Position of this window in the sequence, 0-based."""

    start: int
    """Inclusive token offset where the window begins."""

    end: int
    """Exclusive token offset where the window ends. May be partial."""

    query_chunk: int | None
    """Index of the chunk whose tokens retrieve this window's bank.

    `None` for the head window, which precedes any completed chunk. This is a
    field rather than an implicit convention buried in tensor code, so the offset
    can be tested directly.
    """

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def attends_to_retrieval(self) -> bool:
        return self.query_chunk is not None


def chunk_spans(seq_len: int, m: int) -> list[tuple[int, int]]:
    """Split `seq_len` tokens into `m`-sized retrieval-source spans.

    >>> chunk_spans(140, 64)
    [(0, 64), (64, 128), (128, 140)]
    """
    if seq_len < 0:
        raise ValueError(f"seq_len must be non-negative, got {seq_len}")
    if m <= 0:
        raise ValueError(f"chunk size m must be positive, got {m}")
    return [(s, min(s + m, seq_len)) for s in range(0, seq_len, m)]


def active_query_chunk(position: int, m: int) -> int | None:
    """Which bank the token at absolute `position` is allowed to attend.

    The single source of truth for the offset. The decode loop calls this once
    per token; the layer gets the same answer via `retrieval_plan`.

    >>> [active_query_chunk(p, 4) for p in range(10)]
    [None, None, None, 0, 0, 0, 0, 1, 1, 1]
    """
    if m <= 0:
        raise ValueError(f"chunk size m must be positive, got {m}")
    if position < m - 1:
        return None
    return (position - (m - 1)) // m


def retrieval_plan(seq_len: int, m: int) -> list[ChunkSpec]:
    """Full per-window plan for a sequence.

    Tensor code consumes this rather than recomputing indices, so the property
    tests cover the shipped path.

    >>> [(c.start, c.end, c.query_chunk) for c in retrieval_plan(12, 4)]
    [(0, 3, None), (3, 7, 0), (7, 11, 1), (11, 12, 2)]
    """
    if seq_len <= 0:
        return []
    if m <= 0:
        raise ValueError(f"chunk size m must be positive, got {m}")

    out: list[ChunkSpec] = []
    head_end = min(m - 1, seq_len)
    if head_end > 0:
        out.append(ChunkSpec(index=0, start=0, end=head_end, query_chunk=None))

    u = 0
    while True:
        start = u * m + m - 1
        if start >= seq_len:
            break
        end = min(start + m, seq_len)
        out.append(ChunkSpec(index=len(out), start=start, end=end, query_chunk=u))
        u += 1
    return out


def query_span(query_chunk: int, m: int, prefix: int | None = None) -> tuple[int, int]:
    """Token span whose text builds the query for bank `query_chunk`.

    `prefix` enables speculative retrieval: query on only the first `prefix`
    tokens of the chunk instead of waiting for it to complete, buying
    `(m - prefix) / m` of a chunk of decode time as slack for the ANN round-trip.
    Not used yet; implemented here so causality code is touched once rather than
    twice.

    >>> query_span(1, 64)
    (64, 128)
    >>> query_span(1, 64, prefix=48)
    (64, 112)
    """
    if query_chunk < 0:
        raise ValueError(f"query_chunk must be non-negative, got {query_chunk}")
    start = query_chunk * m
    end = start + m
    if prefix is not None:
        if not 1 <= prefix <= m:
            raise ValueError(f"prefix must be in [1, {m}], got {prefix}")
        end = start + prefix
    return start, end


def window_plan(m: int, offset: int, length: int) -> list[ChunkSpec]:
    """Plan for the token window `[offset, offset + length)`, in local coordinates.

    Incremental decoding feeds one token at a time, so a plan built for the prompt
    does not describe the tokens being generated: every span falls outside the
    tensor and cross-attention silently does nothing. MAAILMA measured that exact
    failure -- an adapter trained with retrieval active on the answer scored
    EM 0.250 under a KV cache and 1.000 once the plan tracked the real position.

    `start`/`end` come back relative to `offset` so tensor code can slice the
    incoming hidden states directly, while `query_chunk` stays absolute: the
    causal offset is a property of the sequence, not of the window.

    >>> [(c.start, c.end, c.query_chunk) for c in window_plan(4, offset=6, length=3)]
    [(0, 1, 0), (1, 3, 1)]
    """
    if length <= 0:
        return []
    out: list[ChunkSpec] = []
    for spec in retrieval_plan(offset + length, m):
        start = max(spec.start, offset)
        end = min(spec.end, offset + length)
        if start < end:
            out.append(ChunkSpec(index=spec.index, start=start - offset,
                                 end=end - offset, query_chunk=spec.query_chunk))
    return out
