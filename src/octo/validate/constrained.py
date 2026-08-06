"""
Graph-constrained decoding: hallucinated entities become impossible to emit.

This is the mechanism the project was always describing and never built. RAG
places retrieved text in the prompt and hopes the model uses it -- nothing stops
the decoder from emitting a gene symbol that appears nowhere in the evidence.
Unaided, the 1.5B answered "which genes does Thiamine bind" with
`THAP1, THAP2, ... THAP62`. Every one of those was a legal token sequence.

Here the knowledge graph acts *during* decoding. At each step the sampler is
masked to the tokens that continue some entity the graph actually supports, so
`THAP1` is not merely unlikely -- it is unreachable. The guarantee is a property
of the decoder, not of a metric or a prompt.

Relationship to GCCA: same intent -- retrieved knowledge acting inside the
generation loop rather than before it -- but applied at the logit layer instead
of the hidden-state layer. No adapters, no gate, no training. GCCA's O(1) KV
scaling remains a separate performance question; this is about correctness.

Limits, stated plainly:

  - It constrains WHICH entities may be named, not whether the claim about them
    is true. Polarity is still uninterpreted (see `buffer_validator`).
  - It presumes the graph's answer set is right. Constrained decoding onto a
    wrong set produces confident, well-formed, wrong output.
  - It suits list-shaped answers. Free prose needs the constraint applied only
    to entity spans, which is a harder segmentation problem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import torch
from transformers import LogitsProcessor


@dataclass
class DecodeState:
    """Where the decoder is inside the allowed-answer automaton."""

    used: set[int]
    n_emitted: int
    path: list[int]
    complete: bool


class GraphConstrainedLogits(LogitsProcessor):
    """Mask the sampler to entity names the graph supports.

    The automaton is: emit an entity, then a separator, then another entity,
    until the allowed set is exhausted or EOS is permitted. State is recomputed
    from the generated tokens each step rather than tracked incrementally --
    slower, but immune to the desync bugs that make this class of code produce
    silently wrong constraints.
    """

    def __init__(self, tokenizer, allowed_names: Sequence[str], *,
                 prompt_len: int, eos_token_id: int,
                 separator: str = ", ", min_items: int = 1,
                 max_items: Optional[int] = None):
        self.tok = tokenizer
        self.prompt_len = prompt_len
        self.eos = eos_token_id
        self.min_items = min_items
        self.max_items = max_items or len(allowed_names)
        self.names = list(allowed_names)

        enc = lambda s: tokenizer(s, add_special_tokens=False)["input_ids"]  # noqa: E731
        # A name tokenizes differently at the start of a reply than after a
        # separator, so both forms are stored.
        self.first = [enc(n) for n in self.names]
        self.rest = [enc(separator + n) for n in self.names]
        self.blocked_steps = 0
        self.total_steps = 0

    def _state(self, gen_ids: list[int]) -> DecodeState:
        used: set[int] = set()
        n = 0
        i = 0
        while i < len(gen_ids):
            pool = self.first if n == 0 else self.rest
            # Longest match first, so `IL1` cannot shadow `IL1B`.
            order = sorted(
                (idx for idx in range(len(pool)) if idx not in used),
                key=lambda k: -len(pool[k]),
            )
            hit = None
            for idx in order:
                seq = pool[idx]
                if gen_ids[i:i + len(seq)] == seq:
                    hit = idx
                    break
            if hit is None:
                return DecodeState(used, n, gen_ids[i:], False)
            used.add(hit)
            n += 1
            i += len(self.rest[hit]) if n > 1 else len(self.first[hit])
        return DecodeState(used, n, [], n >= len(self.names))

    def allowed_tokens(self, gen_ids: list[int]) -> set[int]:
        st = self._state(gen_ids)
        pool = self.first if st.n_emitted == 0 else self.rest
        allowed: set[int] = set()

        if st.n_emitted < self.max_items:
            plen = len(st.path)
            for idx, seq in enumerate(pool):
                if idx in st.used or plen >= len(seq):
                    continue
                if seq[:plen] == st.path:
                    allowed.add(seq[plen])

        # EOS only at an entity boundary, never mid-name.
        if not st.path and st.n_emitted >= self.min_items:
            allowed.add(self.eos)
        if not allowed:
            allowed.add(self.eos)
        return allowed

    def __call__(self, input_ids: torch.LongTensor,
                 scores: torch.FloatTensor) -> torch.FloatTensor:
        self.total_steps += 1
        mask = torch.full_like(scores, float("-inf"))
        for b in range(scores.shape[0]):
            gen = input_ids[b, self.prompt_len:].tolist()
            allowed = self.allowed_tokens(gen)
            idx = torch.tensor(sorted(allowed), device=scores.device,
                               dtype=torch.long)
            mask[b, idx] = scores[b, idx]
            if int(scores[b].argmax()) not in allowed:
                # The unconstrained model wanted something the graph forbids.
                self.blocked_steps += 1
        return mask

    @property
    def intervention_rate(self) -> float:
        """Share of steps where the constraint changed the model's choice.

        Zero means the graph did nothing and any improvement came from the
        prompt, not from constrained decoding.
        """
        return self.blocked_steps / self.total_steps if self.total_steps else 0.0


def generate_constrained(model, tokenizer, prompt: str,
                         allowed_names: Sequence[str], *,
                         device: str = "cuda", max_new_tokens: int = 200,
                         min_items: int = 1):
    """Greedy decode restricted to graph-supported entity names.

    Returns (text, stats). `stats["intervention_rate"]` is the honest readout:
    if it is ~0 the constraint was inert and the result says nothing about
    constrained decoding.
    """
    from transformers import LogitsProcessorList

    ids = tokenizer(prompt, return_tensors="pt").to(device)
    prompt_len = ids["input_ids"].shape[1]
    proc = GraphConstrainedLogits(
        tokenizer, allowed_names, prompt_len=prompt_len,
        eos_token_id=tokenizer.eos_token_id, min_items=min_items,
    )
    with torch.no_grad():
        out = model.generate(
            **ids, max_new_tokens=max_new_tokens, do_sample=False,
            logits_processor=LogitsProcessorList([proc]),
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    text = tokenizer.decode(out[0][prompt_len:], skip_special_tokens=True)
    return text.strip(), {
        "intervention_rate": proc.intervention_rate,
        "blocked_steps": proc.blocked_steps,
        "total_steps": proc.total_steps,
        "n_allowed": len(allowed_names),
    }
