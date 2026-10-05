"""
Tier 1 of the RETRO-v2 falsification ladder, run hermetically on CPU.

    | 1 | Do the GCCA mechanics work? | days · MacBook | Verify plumbing: alpha=0 =>
    |   | bit-identical logits, O(1) KV memory over 1k tokens, causality mask no leak.
                                    -- docs/retro-v2-falsification-plan.md, table 2

These tests do not measure quality. They establish that the mechanism is the one the
brief specified, which is precisely what the 2026-08-04 Level 3 run assumed without
checking. Each maps to a line of that tier:

  alpha=0 identity      -> test_alpha_zero_is_bit_identical_*        (2 tests)
  causality, no leak    -> test_chunk_causal_alignment_no_leak
                           test_bank_zero_cannot_touch_first_chunk
  O(1) memory           -> test_resident_memory_is_constant_in_length
                           test_decode_bank_never_accumulates
  schedule is real      -> test_boundary_query_is_the_chunk_the_model_just_completed
                           test_decode_grid_matches_teacher_forced_grid
  init / diagnostics    -> test_wv_zero_* , test_contribution_*
  expressible shape     -> test_short_generation_cannot_re_aim

The causal offset itself is property-tested without torch in test_chunking.py.

A tiny causal LM with a real KV cache stands in for Qwen. It has to be real: a stack
of Linears would satisfy the identity test trivially and prove nothing about whether
the cache and the hooks interact correctly.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
import torch
import torch.nn as nn

from tahi.native import (
    GatedChunkedCrossAttention,
    TahiNativeAdapter,
    StaticChunkRetriever,
    build_chunk_banks,
    chunked_generate,
)
from tahi.native.chunk_retriever import ChunkRetrieval
from tahi.native.chunked_decode import (
    assert_schedule_is_expressible,
    boundaries_expected,
)
from tahi.native.chunking import query_span

M = 4          # chunk size under test; 64 in production, 4 keeps the tests fast
D_MODEL = 16
D_RET = 8
VOCAB = 24


# --------------------------------------------------------------------------- #
# a minimal causal LM with a working KV cache
# --------------------------------------------------------------------------- #

class TinyLayer(nn.Module):
    def __init__(self, d: int):
        super().__init__()
        self.ln = nn.LayerNorm(d)
        self.q, self.k, self.v, self.o = (nn.Linear(d, d) for _ in range(4))

    def forward(self, x, layer_past=None, use_cache=True):
        h = self.ln(x)
        q, k, v = self.q(h), self.k(h), self.v(h)
        if layer_past is not None:
            k = torch.cat([layer_past[0], k], dim=1)
            v = torch.cat([layer_past[1], v], dim=1)
        s, t = q.size(1), k.size(1)
        att = q @ k.transpose(1, 2) / math.sqrt(q.size(-1))
        # Query i sits at absolute position t - s + i and may see keys up to it.
        mask = torch.ones(s, t, dtype=torch.bool).tril(diagonal=t - s)
        att = att.masked_fill(~mask, float("-inf")).softmax(dim=-1)
        return (x + self.o(att @ v), (k, v))


class TinyCausalLM(nn.Module):
    def __init__(self, vocab: int = VOCAB, d: int = D_MODEL, n_layers: int = 8):
        super().__init__()
        self.config = SimpleNamespace(hidden_size=d)
        self.embed = nn.Embedding(vocab, d)
        self.model = nn.Module()
        self.model.layers = nn.ModuleList([TinyLayer(d) for _ in range(n_layers)])
        self.head = nn.Linear(d, vocab)

    def forward(self, input_ids, past_key_values=None, use_cache=True, **_):
        x = self.embed(input_ids)
        presents = []
        for i, layer in enumerate(self.model.layers):
            past = past_key_values[i] if past_key_values is not None else None
            x, present = layer(x, past, use_cache)
            presents.append(present)
        return SimpleNamespace(logits=self.head(x), past_key_values=tuple(presents))


class CharTokenizer:
    """Ids are characters. `decode` is what the boundary query is built from, so it
    has to round-trip faithfully or the test would be checking its own stub."""

    eos_token_id = None

    def decode(self, ids, skip_special_tokens=True):  # noqa: ARG002
        if isinstance(ids, torch.Tensor):
            ids = ids.tolist()
        return "".join(chr(ord("a") + int(i) % 26) for i in ids)

    def __call__(self, text, return_tensors=None, truncation=True, max_length=None):  # noqa: ARG002
        ids = [ord(c) % VOCAB for c in text]
        return {"input_ids": torch.tensor([ids])}


class RecordingRetriever:
    """Returns a distinct bank per call and remembers every query it was given."""

    def __init__(self, k: int = 3, d: int = D_RET):
        self.queries: list[str] = []
        self.k, self.d = k, d

    def __call__(self, query_text: str) -> ChunkRetrieval:
        self.queries.append(query_text)
        g = torch.Generator().manual_seed(abs(hash(query_text)) % (2**31))
        mem = torch.randn(1, self.k, self.d, generator=g)
        return ChunkRetrieval(memory=mem,
                              node_ids=[f"node::{len(self.queries)}::{i}"
                                        for i in range(self.k)])


def _seeded_model() -> TinyCausalLM:
    torch.manual_seed(0)
    return TinyCausalLM()


def _open_gates(adapter: TahiNativeAdapter, value: float = 1.0) -> None:
    with torch.no_grad():
        for g in adapter.gcca_layers.values():
            g.alpha.fill_(value)
            # Untrained W_K/W_V start near zero-mean random; make the projection
            # non-degenerate so "the gate is open" actually changes the output.
            nn.init.normal_(g.w_k.weight, std=0.5)
            nn.init.normal_(g.w_v.weight, std=0.5)


# --------------------------------------------------------------------------- #
# 1. alpha = 0 identity
# --------------------------------------------------------------------------- #

def test_alpha_zero_is_bit_identical_static():
    """Closed gate, static bank: output must be the input, exactly."""
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    h = torch.randn(2, 5 * M, D_MODEL)
    out = gcca(h, torch.randn(2, 6, D_RET))
    assert torch.equal(out, h)


def test_alpha_zero_is_bit_identical_chunked():
    """Closed gate, per-chunk banks: still exactly the input.

    `torch.equal`, not `allclose`. The identity control in the benchmark asserts zero
    token mismatches; anything short of exact equality here can surface there as a
    flipped argmax on a near-tie and be misread as a harness bug.
    """
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    h = torch.randn(2, 5 * M, D_MODEL)
    banks = torch.randn(2, 5, 3, D_RET)
    assert torch.equal(gcca(h, banks), h)


def test_alpha_zero_survives_an_empty_bank():
    """All-zero slots must not produce NaN through the closed gate."""
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    h = torch.randn(1, 4 * M, D_MODEL)
    out = gcca(h, torch.zeros(1, 4, 3, D_RET))
    assert torch.equal(out, h)
    assert torch.isfinite(out).all()


# --------------------------------------------------------------------------- #
# 2. causality: the alignment, checked by perturbation
# --------------------------------------------------------------------------- #

def test_chunk_causal_alignment_no_leak():
    """Bank `u` may influence positions >= u*M + M - 1 and no earlier position.

    Checked by perturbing one bank and diffing, rather than by reading the reshape.
    An off-by-one-chunk error lets the model attend a retrieval keyed on text it has
    not written yet; that inflates every score and is invisible in the metric.
    """
    torch.manual_seed(1)
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    with torch.no_grad():
        gcca.alpha.fill_(1.0)
        nn.init.normal_(gcca.w_k.weight, std=0.5)
        nn.init.normal_(gcca.w_v.weight, std=0.5)

    h = torch.randn(1, 5 * M, D_MODEL)
    banks = torch.randn(1, 5, 3, D_RET)

    base = gcca(h, banks)

    u = 2
    perturbed = banks.clone()
    perturbed[0, u] += 10.0
    after = gcca(h, perturbed)

    first_allowed = u * M + M - 1          # 11 when M == 4
    diff = (after - base).abs().sum(dim=-1)[0]

    assert torch.equal(after[:, :first_allowed], base[:, :first_allowed]), (
        f"bank {u} changed a position before {first_allowed} -- retrieval leaked "
        "backwards into tokens generated before the chunk it was keyed on"
    )
    assert diff[first_allowed:first_allowed + M].max() > 0, (
        f"bank {u} changed nothing in its own attending window -- the bank is "
        "inert and the mechanism is not connected"
    )


def test_bank_zero_cannot_touch_first_chunk():
    """Positions [0, M-1) precede any completed chunk and must attend nothing."""
    torch.manual_seed(2)
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    with torch.no_grad():
        gcca.alpha.fill_(1.0)
        nn.init.normal_(gcca.w_v.weight, std=0.5)

    h = torch.randn(1, 3 * M, D_MODEL)
    banks = torch.randn(1, 3, 3, D_RET)
    out = gcca(h, banks)
    assert torch.equal(out[:, : M - 1], h[:, : M - 1])


def test_shorter_than_one_chunk_is_untouched():
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    with torch.no_grad():
        gcca.alpha.fill_(1.0)
    h = torch.randn(1, M - 1, D_MODEL)
    assert torch.equal(gcca(h, torch.randn(1, 2, 3, D_RET)), h)


# --------------------------------------------------------------------------- #
# 3. the decode loop
# --------------------------------------------------------------------------- #

def test_alpha_zero_decode_is_bit_identical_to_base_model():
    """The identity control, end to end through the chunked loop.

    Retrieval fires at every boundary, banks change, hooks run -- and with the gate
    closed the emitted tokens and the per-step logits must match the bare model
    exactly. If this fails, no arm in the benchmark is interpretable.
    """
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)

    prompt = torch.tensor([[1, 2, 3, 4, 5, 6]])

    gated = chunked_generate(model, tok, prompt, adapter=adapter,
                             retriever=RecordingRetriever(), chunk_size=M,
                             max_new_tokens=5 * M, collect_logits=True)

    adapter.remove_hooks()
    bare = chunked_generate(model, tok, prompt, adapter=None, retriever=None,
                            chunk_size=M, max_new_tokens=5 * M,
                            collect_logits=True)

    assert gated.token_ids == bare.token_ids
    for a, b in zip(gated.logits, bare.logits, strict=True):
        assert torch.equal(a, b)


def test_open_gate_changes_the_output():
    """Counterpart to the identity control: an open gate must actually do something,
    or the identity result above is vacuous."""
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    prompt = torch.tensor([[1, 2, 3, 4, 5, 6]])

    closed = chunked_generate(model, tok, prompt, adapter=adapter,
                              retriever=RecordingRetriever(), chunk_size=M,
                              max_new_tokens=6 * M)
    _open_gates(adapter)
    opened = chunked_generate(model, tok, prompt, adapter=adapter,
                              retriever=RecordingRetriever(), chunk_size=M,
                              max_new_tokens=6 * M)

    assert closed.token_ids != opened.token_ids


def test_boundary_query_is_the_chunk_the_model_just_completed():
    """The query must be the completed chunk's own tokens, on the ABSOLUTE grid.

    Two things are asserted, and the second is the one the 2026-08-04 arm got
    wrong: the query is generated text rather than the question, and the chunk
    grid counts from position 0 including the prompt. Counting boundaries over
    generated tokens alone would put decode on a different grid than the
    teacher-forced path whenever the prompt is not a multiple of M.
    """
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    retriever = RecordingRetriever()
    prompt = torch.tensor([[1, 2, 3, 4, 5, 6]])       # P = 6, not a multiple of M
    n_new = 5 * M

    out = chunked_generate(model, tok, prompt, adapter=adapter,
                           retriever=retriever, chunk_size=M,
                           max_new_tokens=n_new)

    full = prompt[0].tolist() + out.token_ids
    for b in out.boundaries:
        assert b.index >= 0
        start, end = query_span(b.index, M)
        assert b.query_text == tok.decode(full[start:end])
        assert end <= len(full), "queried a chunk that had not completed -- leak"

    # Consecutive, starting at chunk 0, with no gaps: every position that is
    # allowed a bank gets the right one.
    assert [b.index for b in out.boundaries] == list(range(len(out.boundaries)))

    # The grid is absolute: with P=6 and M=4 the first boundary covers prompt
    # tokens only, which is exactly what the teacher-forced path would build.
    assert out.boundaries[0].query_text == tok.decode(prompt[0, :M])


def test_decode_grid_matches_teacher_forced_grid():
    """The decode loop and `build_chunk_banks` must agree chunk for chunk.

    Train on one grid and infer on another and the adapter sees a distribution it
    was never fitted to. MAAILMA measured that mismatch at EM 0.250 against 1.000
    for the same checkpoint.
    """
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    prompt = torch.tensor([[1, 2, 3, 4, 5, 6]])

    decoded = chunked_generate(model, tok, prompt, adapter=adapter,
                               retriever=RecordingRetriever(), chunk_size=M,
                               max_new_tokens=5 * M)

    full = torch.tensor([prompt[0].tolist() + decoded.token_ids])
    tf = RecordingRetriever()
    _, events = build_chunk_banks(full, tok, tf, chunk_size=M,
                                  max_slots=8, d_retriever=D_RET)

    decode_queries = [b.query_text for b in decoded.boundaries]
    tf_queries = [e.query_text for e in events]
    assert decode_queries == tf_queries[:len(decode_queries)]


def test_resident_memory_is_constant_in_length():
    """O(1): what the attention resides over does not grow with generated length.

    Retrieval *calls* grow linearly -- that is the cost being traded -- but the
    per-step bank does not. This is the efficiency half of the win condition
    (iterative-RAG quality at single-shot cost).
    """
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    prompt = torch.tensor([[1, 2, 3, 4, 5, 6]])

    short = chunked_generate(model, tok, prompt, adapter=adapter,
                             retriever=RecordingRetriever(k=3), chunk_size=M,
                             max_new_tokens=2 * M, max_slots=8)
    long = chunked_generate(model, tok, prompt, adapter=adapter,
                            retriever=RecordingRetriever(k=3), chunk_size=M,
                            max_new_tokens=20 * M, max_slots=8)

    assert short.peak_memory_slots == long.peak_memory_slots
    assert long.retrieval_calls > short.retrieval_calls   # queries do scale
    assert adapter.active_memory_slots == 0               # cleared on exit


def test_decode_bank_never_accumulates():
    """During generation exactly one bank is resident, whatever the position."""
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    seen: list[int] = []

    class Watching(RecordingRetriever):
        def __call__(self, q):
            r = super().__call__(q)
            if adapter._current_retrieved_memory is not None:
                seen.append(adapter._current_retrieved_memory.numel())
            return r

    chunked_generate(model, tok, torch.tensor([[1, 2, 3, 4, 5, 6]]),
                     adapter=adapter, retriever=Watching(k=3), chunk_size=M,
                     max_new_tokens=20 * M, max_slots=8)

    # One prefill install (padded to max_slots) then a constant 3-slot bank.
    assert len(set(seen[1:])) == 1, f"resident bank size drifted: {sorted(set(seen))}"


def test_static_retriever_holds_one_bank_across_every_boundary():
    """`StaticChunkRetriever` must return the same bank at every boundary.

    It is the 2026-08-04 architecture expressed as a retriever, so the old result
    can be reproduced inside this harness rather than argued about. Note it is no
    longer token-identical to a single up-front injection: on the chunked grid the
    first M-1 positions correctly attend nothing, which one-shot injection does
    not model. Same bank, different schedule -- which is the distinction the whole
    experiment exists to measure.
    """
    model = _seeded_model()
    tok = CharTokenizer()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    _open_gates(adapter)

    torch.manual_seed(7)
    fixed = torch.randn(1, 3, D_RET)
    retriever = StaticChunkRetriever(fixed, node_ids=["n0", "n1", "n2"])

    out = chunked_generate(model, tok, torch.tensor([[1, 2, 3, 4, 5, 6]]),
                           adapter=adapter, retriever=retriever,
                           chunk_size=M, max_new_tokens=5 * M, max_slots=8)

    assert retriever.calls == out.retrieval_calls > 1
    assert all(b.node_ids == ["n0", "n1", "n2"] for b in out.boundaries)


# --------------------------------------------------------------------------- #
# 4. teacher-forced banks (training / offline scoring path)
# --------------------------------------------------------------------------- #

def test_build_chunk_banks_shape_and_keying():
    tok = CharTokenizer()
    retriever = RecordingRetriever(k=3)
    ids = torch.arange(1, 1 + 5 * M).unsqueeze(0)

    banks, events = build_chunk_banks(ids, tok, retriever, chunk_size=M,
                                      max_slots=6, d_retriever=D_RET)

    assert banks.shape == (1, 5, 6, D_RET)
    assert len(events) == 5
    for u, ev in enumerate(events):
        assert ev.query_text == tok.decode(ids[0, u * M: (u + 1) * M])
    # Padded slots stay zero; they never borrow another chunk's content.
    assert torch.equal(banks[0, :, 3:], torch.zeros(5, 3, D_RET))


def test_build_chunk_banks_handles_short_sequence():
    tok = CharTokenizer()
    banks, events = build_chunk_banks(torch.arange(1, M).unsqueeze(0), tok,
                                      RecordingRetriever(), chunk_size=M)
    assert banks is None and events == []


# --------------------------------------------------------------------------- #
# 5. identity init modes and the gate-collapse diagnostic
# --------------------------------------------------------------------------- #

def test_wv_zero_is_also_bit_exact_identity():
    """Identity needs the gated *term* to vanish, not alpha specifically.

    `W_v = 0` with alpha at its target gives the same bit-exact identity while
    leaving `dL/dW_v` non-zero from step 1 -- under alpha=0 the bridge cannot
    learn at all until alpha itself has moved, because dL/dW_k and dL/dW_v both
    carry a factor of tanh(alpha).
    """
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    nn.init.normal_(gcca.w_v.weight, std=0.5)
    gcca.set_identity_mode("wv-zero", alpha=0.3)

    h = torch.randn(2, 5 * M, D_MODEL)
    assert torch.equal(gcca(h, torch.randn(2, 5, 3, D_RET)), h)
    assert float(gcca.alpha.detach()) == pytest.approx(0.3)


def test_wv_zero_leaves_gradient_on_w_v_where_alpha_zero_does_not():
    """The measured reason to prefer `wv-zero`, asserted rather than cited."""
    grads = {}
    for mode in ("alpha-zero", "wv-zero"):
        torch.manual_seed(3)
        gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
        nn.init.normal_(gcca.w_v.weight, std=0.5)
        gcca.set_identity_mode(mode, alpha=0.3)
        out = gcca(torch.randn(1, 5 * M, D_MODEL), torch.randn(1, 5, 3, D_RET))
        out.sum().backward()
        grads[mode] = gcca.w_v.weight.grad.abs().sum().item()

    assert grads["alpha-zero"] == 0.0
    assert grads["wv-zero"] > 0.0


def test_negative_control_for_wv_zero_perturbs_w_v_not_alpha():
    """Under `wv-zero`, moving alpha no longer breaks identity.

    A control that still perturbs alpha would silently pass forever -- exactly the
    failure a negative control exists to prevent.
    """
    torch.manual_seed(4)
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    gcca.set_identity_mode("wv-zero", alpha=0.3)
    h = torch.randn(1, 5 * M, D_MODEL)
    banks = torch.randn(1, 5, 3, D_RET)

    with torch.no_grad():
        gcca.alpha.fill_(0.9)
    assert torch.equal(gcca(h, banks), h), "alpha perturbation is not a valid control here"

    with torch.no_grad():
        nn.init.normal_(gcca.w_v.weight, std=0.5)
    assert not torch.equal(gcca(h, banks), h)


def test_contribution_separates_a_shut_gate_from_a_useless_one():
    """`contribution` must be 0 when the gate is shut and non-zero when it bites."""
    torch.manual_seed(5)
    gcca = GatedChunkedCrossAttention(D_MODEL, D_RET, num_heads=2, chunk_size=M)
    h = torch.randn(1, 5 * M, D_MODEL)
    banks = torch.randn(1, 5, 3, D_RET)

    gcca(h, banks)
    assert gcca.last_contribution == 0.0

    with torch.no_grad():
        gcca.alpha.fill_(1.0)
        nn.init.normal_(gcca.w_v.weight, std=0.5)
    gcca(h, banks)
    assert gcca.last_contribution > 0.0


def test_adapter_reports_per_block_diagnostics():
    model = _seeded_model()
    adapter = TahiNativeAdapter(model, d_retriever=D_RET, interleave_step=4,
                                num_heads=2, chunk_size=M)
    adapter.set_identity_mode("wv-zero", alpha=0.3)
    assert all(a == pytest.approx(0.3) for a in adapter.alphas().values())

    adapter.set_retrieved_memory(torch.randn(1, 3, D_RET))
    adapter(torch.tensor([[1, 2, 3, 4, 5]]))
    assert set(adapter.contributions()) == set(adapter.gcca_layers)
    assert all(c == 0.0 for c in adapter.contributions().values())


# --------------------------------------------------------------------------- #
# 6. run shapes that cannot express the schedule
# --------------------------------------------------------------------------- #

def test_short_generation_cannot_re_aim():
    """The 2026-08-04 run's shape: ~10 output tokens at m=64 never re-aims."""
    assert boundaries_expected(n_prompt=800, max_new_tokens=10, chunk_size=64) == 0
    with pytest.raises(ValueError, match="re-aim retrieval 0 time"):
        assert_schedule_is_expressible(800, 10, 64)


def test_long_generation_re_aims_once_per_chunk():
    assert boundaries_expected(n_prompt=64, max_new_tokens=256, chunk_size=64) == 4
    assert_schedule_is_expressible(64, 256, 64)
