"""
The custom decode loop the RETRO-v2 brief specified and the Level 3 run never had.

    | When | prompt-RAG: once, at step 0 | GCCA: every 64 tokens |
    | Serving | off-the-shelf vLLM | custom decode loop + adapter alignment |
                                        -- docs/retro-v2-brief.md, table 1

`model.generate()` cannot express the right-hand column. It runs to completion under
whatever memory was set before the call, which makes the retrieval schedule identical
to one-shot RAG and reduces the architecture to where-the-vectors-enter. This loop
replaces it: greedy decode, stopping at every `chunk_size`-token boundary to re-query
using the text just produced, and swapping the bank the GCCA hooks cross-attend.

Two properties this must have, both asserted in `tests/test_chunked_gcca.py`:

* **alpha = 0 is bit-identical to the base model.** The gate closed must reproduce the
  stock model's logits exactly, or no downstream comparison is interpretable.
* **O(1) memory.** The active bank is `[1, K, d]` at token 10 and at token 10,000. The
  retrieval count grows with length; the resident memory does not. That is the entire
  efficiency claim -- iterative-RAG quality at single-shot cost -- and it is a property
  of this loop, not of the layer.

What is deliberately NOT here: sampling, beam search, batching. The falsification plan
scores greedy decode at batch 1. Adding decode strategies before the mechanism is
proven repeats the mistake of building serving infrastructure for an untested claim.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import torch

from .chunk_retriever import ChunkRetrieval
from .chunking import active_query_chunk, query_span, window_plan
from .gcca_layer import DEFAULT_CHUNK_SIZE


@dataclass
class BoundaryEvent:
    """One re-aim of retrieval, recorded so a run can be audited after the fact."""

    index: int                  # 0-based boundary number
    n_generated: int            # tokens produced when it fired
    query_text: str             # what the model had just written -- the search query
    node_ids: list[str] = field(default_factory=list)
    n_slots: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "n_generated": self.n_generated,
                "query_text": self.query_text, "node_ids": self.node_ids,
                "n_slots": self.n_slots}


@dataclass
class ChunkedGeneration:
    text: str
    token_ids: list[int] = field(default_factory=list)
    boundaries: list[BoundaryEvent] = field(default_factory=list)
    logits: list[torch.Tensor] = field(default_factory=list)
    peak_memory_slots: int = 0
    retrieval_calls: int = 0

    @property
    def n_new_tokens(self) -> int:
        return len(self.token_ids)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "n_new_tokens": self.n_new_tokens,
                "boundaries": [b.to_dict() for b in self.boundaries],
                "peak_memory_slots": self.peak_memory_slots,
                "retrieval_calls": self.retrieval_calls}


def _unpack(out: Any) -> tuple[torch.Tensor, Any]:
    """Accept HuggingFace output objects or plain (logits, cache) tuples."""
    if hasattr(out, "logits"):
        return out.logits, getattr(out, "past_key_values", None)
    if isinstance(out, tuple):
        return out[0], (out[1] if len(out) > 1 else None)
    return out, None


def boundaries_expected(n_prompt: int, max_new_tokens: int, chunk_size: int) -> int:
    """How many times retrieval will re-aim over a run of this shape.

    Zero or one means the schedule is indistinguishable from one-shot injection,
    whatever the architecture does. That is not a hypothetical: the 2026-08-04
    benchmark generated a mean of 9.8-18.4 tokens per item at `chunk_size=64`, so
    even a correct implementation could not have re-aimed once during generation.

    MAAILMA hit the same wall from the other side -- QA pairs tokenising to 38-52
    tokens land entirely in `C_0`, which never retrieves, so every gradient
    vanished and training was vacuous. Their fix was to assert at step 0 that some
    chunk retrieves rather than failing silently. Call this before a run and refuse
    to spend GPU time on a shape that cannot express the mechanism.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    last = active_query_chunk(n_prompt + max_new_tokens - 1, chunk_size)
    first = active_query_chunk(max(0, n_prompt - 1), chunk_size)
    if last is None:
        return 0
    return last - (first if first is not None else -1)


def assert_schedule_is_expressible(n_prompt: int, max_new_tokens: int,
                                   chunk_size: int, minimum: int = 2) -> None:
    """Refuse a run whose generation is too short to re-aim `minimum` times."""
    got = boundaries_expected(n_prompt, max_new_tokens, chunk_size)
    if got < minimum:
        raise ValueError(
            f"generation would re-aim retrieval {got} time(s) "
            f"(prompt={n_prompt}, max_new_tokens={max_new_tokens}, m={chunk_size}); "
            f"at least {minimum} are needed for the chunked schedule to differ "
            "from one-shot injection. Lengthen generation or shorten the chunk."
        )


def _stack_banks(banks: list, max_slots: int, width: int, device) -> torch.Tensor:
    """Pack per-chunk `[K, d]` banks into `[1, L, max_slots, d]`, right-padded.

    Padded slots stay zero: they contribute a constant key/value the gate can learn
    to ignore, and they never borrow another chunk's content.
    """
    out = torch.zeros((1, len(banks), max_slots, width), device=device)
    for u, b in enumerate(banks):
        if b is None:
            continue
        k = min(int(b.shape[0]), max_slots)
        out[0, u, :k] = b[:k].to(device)
    return out


@torch.no_grad()
def chunked_generate(
    model: Any,
    tokenizer: Any,
    prompt: str | torch.Tensor,
    *,
    adapter: Any | None = None,
    retriever: Callable[[str], ChunkRetrieval] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_new_tokens: int = 128,
    device: str | torch.device = "cpu",
    seed_from_prompt: bool = True,
    eos_token_id: int | None = None,
    collect_logits: bool = False,
    max_prompt_tokens: int = 3072,
    max_slots: int = 16,
) -> ChunkedGeneration:
    """Greedy decode with retrieval re-aimed at every chunk boundary.

    Boundaries are computed in **absolute sequence position**, counting the prompt,
    via `chunking.active_query_chunk` -- the same function the teacher-forced path
    uses. Counting boundaries over generated tokens alone would put training and
    inference on different chunk grids for any prompt whose length is not a
    multiple of `chunk_size`, which is the class of bug MAAILMA measured at
    EM 0.250 against 1.000 for one checkpoint.

    Args:
        adapter: `TahiNativeAdapter` whose GCCA hooks are live. `None` runs the bare
            model -- the base arm, and the reference the identity control compares to.
        retriever: called at each boundary with the text of the completed chunk.
            `None` means no re-aim: the loop degenerates to one-shot, which is how
            the 2026-08-04 arm is reproduced for comparison.
        seed_from_prompt: install a bank retrieved from the prompt tail when the
            prompt is shorter than one chunk, so generation does not start blind.
            A deviation from strict RETRO (where `C_0` never retrieves), kept
            because short QA prompts otherwise retrieve nothing for their first
            `chunk_size - 1` tokens. Set `False` for paper-faithful behaviour.

    Returns:
        `ChunkedGeneration` with the text, the boundary trace, and the peak slot
        count that substantiates the O(1) claim.
    """
    if isinstance(prompt, torch.Tensor):
        input_ids = prompt.to(device)
        if input_ids.dim() == 1:
            input_ids = input_ids.unsqueeze(0)
    else:
        enc = tokenizer(prompt, return_tensors="pt", truncation=True,
                        max_length=max_prompt_tokens)
        input_ids = enc["input_ids"].to(device)

    if eos_token_id is None:
        eos_token_id = getattr(tokenizer, "eos_token_id", None)

    result = ChunkedGeneration(text="")
    full_ids: list[int] = input_ids[0].tolist()
    n_prompt = len(full_ids)

    def _retrieve_chunk(u: int) -> ChunkRetrieval:
        start, end = query_span(u, chunk_size)
        text = tokenizer.decode(full_ids[start:end], skip_special_tokens=True)
        r = retriever(text)
        result.retrieval_calls += 1
        result.boundaries.append(BoundaryEvent(
            index=u, n_generated=max(0, len(full_ids) - n_prompt),
            query_text=text, node_ids=list(r.node_ids), n_slots=r.n_slots))
        return r

    def _install(mem: torch.Tensor | None, plan=None) -> int:
        if adapter is None:
            return 0
        if mem is None:
            adapter.clear_retrieved_memory()
            return 0
        adapter.set_retrieved_memory(mem.to(device), plan=plan)
        return int(mem.shape[-2])

    if adapter is not None:
        adapter.clear_retrieved_memory()

    # --- prefill -------------------------------------------------------------
    # Prompt positions span several chunks, each of which must attend its own
    # bank. One static bank here would put the prompt on a different grid than
    # training uses.
    installed_u: int | None = None
    if retriever is not None:
        last_u = active_query_chunk(n_prompt - 1, chunk_size)
        if last_u is not None:
            banks, width = [], None
            for u in range(last_u + 1):
                r = _retrieve_chunk(u)
                mem = None if r.memory is None else (
                    r.memory.squeeze(0) if r.memory.dim() == 3 else r.memory)
                if mem is not None:
                    width = width or int(mem.shape[-1])
                banks.append(mem)
            if width is not None:
                stacked = _stack_banks(banks, max_slots, width, device)
                result.peak_memory_slots = max(result.peak_memory_slots, max_slots)
                _install(stacked, plan=window_plan(chunk_size, 0, n_prompt))
                installed_u = last_u
        elif seed_from_prompt:
            # Prompt shorter than one chunk: nothing has completed. Bootstrap.
            seed_text = tokenizer.decode(full_ids[-chunk_size:],
                                         skip_special_tokens=True)
            r = retriever(seed_text)
            result.retrieval_calls += 1
            result.boundaries.append(BoundaryEvent(
                index=-1, n_generated=0, query_text=seed_text,
                node_ids=list(r.node_ids), n_slots=r.n_slots))
            result.peak_memory_slots = max(result.peak_memory_slots,
                                           _install(r.memory))

    logits, past = _unpack(model(input_ids=input_ids, use_cache=True))

    generated: list[int] = []

    for _ in range(max_new_tokens):
        step_logits = logits[:, -1, :]
        if collect_logits:
            result.logits.append(step_logits.detach().clone())

        next_id = int(torch.argmax(step_logits, dim=-1)[0])
        generated.append(next_id)
        full_ids.append(next_id)
        if eos_token_id is not None and next_id == eos_token_id:
            break
        if len(generated) >= max_new_tokens:
            break

        # --- boundary: the bank this position is allowed to attend ------------
        if retriever is not None:
            pos = len(full_ids) - 1          # absolute position of `next_id`
            u = active_query_chunk(pos, chunk_size)
            if u is not None and u != installed_u:
                r = _retrieve_chunk(u)
                result.peak_memory_slots = max(result.peak_memory_slots,
                                               _install(r.memory))
                installed_u = u

        nxt = torch.tensor([[next_id]], device=device)
        logits, past = _unpack(model(input_ids=nxt, past_key_values=past,
                                     use_cache=True))

    if adapter is not None:
        adapter.clear_retrieved_memory()

    result.token_ids = generated
    result.text = tokenizer.decode(generated, skip_special_tokens=True).strip()
    return result


@torch.no_grad()
def build_chunk_banks(
    token_ids: torch.Tensor,
    tokenizer: Any,
    retriever: Callable[[str], ChunkRetrieval],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_slots: int = 16,
    d_retriever: int | None = None,
    device: str | torch.device = "cpu",
) -> tuple[torch.Tensor | None, list[BoundaryEvent]]:
    """Teacher-forced counterpart of the decode loop: one bank per chunk, `[1, L, K, d]`.

    Training and offline scoring see the whole sequence at once, so they retrieve for
    every chunk up front. `GatedChunkedCrossAttention` then applies the same
    autoregressive shift the decode loop enforces in time, which is what keeps the two
    paths equivalent. Bank `u` is keyed on chunk `u`'s own tokens -- never on later
    ones -- so nothing here can see the future.
    """
    ids = token_ids[0] if token_ids.dim() == 2 else token_ids
    n = int(ids.shape[0])
    n_chunks = n // chunk_size
    if n_chunks == 0:
        return None, []

    banks: list[torch.Tensor] = []
    events: list[BoundaryEvent] = []
    width = d_retriever

    for u in range(n_chunks):
        span = ids[u * chunk_size: (u + 1) * chunk_size]
        text = tokenizer.decode(span, skip_special_tokens=True)
        r = retriever(text)
        events.append(BoundaryEvent(index=u, n_generated=(u + 1) * chunk_size,
                                    query_text=text, node_ids=list(r.node_ids),
                                    n_slots=r.n_slots))
        if r.memory is None:
            banks.append(None)  # type: ignore[arg-type]
            continue
        mem = r.memory.squeeze(0) if r.memory.dim() == 3 else r.memory
        width = width or int(mem.shape[-1])
        banks.append(mem)

    if width is None or all(b is None for b in banks):
        return None, events

    # Right-pad every chunk to `max_slots` so the stack is rectangular. Padded slots
    # are zeros; they contribute a constant key/value, which the gate can learn to
    # ignore, and they never carry another chunk's content.
    out = torch.zeros((1, n_chunks, max_slots, width), device=device)
    for u, b in enumerate(banks):
        if b is None:
            continue
        k = min(int(b.shape[0]), max_slots)
        out[0, u, :k] = b[:k].to(device)
    return out, events
