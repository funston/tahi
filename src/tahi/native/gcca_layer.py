"""
PyTorch implementation of Gated Chunked Cross-Attention (GCCA) for TAHI native residual injection.

Implements intermediate layer cross-attention between frozen LLM hidden states and
retrieved graph/vector world-state memory. Gated by a zero-initialized tanh(alpha)
scalar parameter to guarantee zero logit disruption at step 0 (Flamingo / InstructRetro principle).

Two memory modes:

* **static** -- `e_retrieved` is `[B, K, d_retriever]`. Every position attends to the
  same K slots. This is one-shot retrieval expressed inside the layer stack: it is
  what the 2026-08-04 Level 3 run measured, and it is NOT the RETRO mechanism. It
  remains available because the incremental decode loop drives chunk selection from
  outside the layer (see `chunked_decode.py`), and because training and the identity
  control still use it.

* **chunked** -- `e_retrieved` is `[B, L, K, d_retriever]`, one memory bank per chunk.
  This is RETRO's Chunked Cross-Attention (Borgeaud et al. 2022, sec. 2.4) with the
  autoregressive alignment intact: the bank retrieved from chunk `u` may only be
  attended by positions at or after `u*m + m - 1`, the last token of chunk `u`. Every
  token attending bank `u` is therefore predicted from tokens that were already
  generated when bank `u` was retrieved. Positions `[0, m-1)` attend nothing.

The alignment is the entire safety argument. Get it wrong by one chunk and the model
sees a retrieval keyed on text it has not written yet, which inflates every downstream
number and cannot be detected from the score alone. `tests/test_chunked_gcca.py`
asserts it by perturbation rather than by inspection.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .chunking import ChunkSpec, retrieval_plan

# RETRO's chunk length. The stride at which generation re-aims its retrieval.
DEFAULT_CHUNK_SIZE = 64


class GatedChunkedCrossAttention(nn.Module):
    """
    Level 3 Native Integration: PyTorch Gated Chunked Cross-Attention (GCCA) Module.

    Inserts lightweight trainable cross-attention adapters into frozen Transformer blocks.
    Uses tanh(alpha) gating initialized to 0.0 to guarantee zero disruption at step 0.
    """

    def __init__(
        self,
        d_model: int,
        d_retriever: int,
        num_heads: int = 8,
        dropout: float = 0.0,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        super().__init__()
        self.d_model = d_model
        self.d_retriever = d_retriever
        self.num_heads = num_heads
        self.chunk_size = chunk_size

        # Linear projection matrices for Key and Value from retrieved world state
        self.w_k = nn.Linear(d_retriever, d_model, bias=False)
        self.w_v = nn.Linear(d_retriever, d_model, bias=False)

        # Multi-head cross-attention over retrieved graph/vector memory
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(d_model)

        # Zero-initialized tanh(alpha) gating scalar (Flamingo/InstructRetro principle)
        self.alpha = nn.Parameter(torch.zeros(1))

        # Diagnostic, refreshed every forward. See `last_contribution`.
        self._last_contribution: float | None = None

    # ------------------------------------------------------------------ #
    # identity initialisation
    # ------------------------------------------------------------------ #

    @torch.no_grad()
    def set_identity_mode(self, mode: str, alpha: float = 0.3) -> None:
        """Choose which factor of the gated term is zeroed at init.

        Bit-exact identity requires the *product* `tanh(alpha) * W_v(...)` to be
        zero, not `alpha` specifically. The choice changes which gradients exist
        at step 0, and MAAILMA measured the difference on Qwen2.5-0.5B:

            init                    grad norm @0   dW_v @0   dW_k drift (final)
            alpha=0, W_v random         0.185       0.000        0.94
            alpha=0.3, W_v=0            0.641       0.584        2.08

        With `alpha = 0` the gated term is annihilated, so `dL/dW_k` and
        `dL/dW_v` are **exactly** zero -- their gradients carry a factor of
        `tanh(alpha)`. Only `alpha` itself learns at first (`d tanh/d alpha` is
        `sech^2(0) = 1`), so the bridge must bootstrap through the gate before any
        projection moves. Zeroing `W_v` instead keeps `tanh(alpha)` finite, so
        `dL/dW_v` is non-zero from step 1 and `W_k` follows the moment `W_v`
        leaves zero.

        Consequence for the negative control: under `wv-zero`, setting
        `alpha != 0` no longer breaks identity, so a control that perturbs
        `alpha` becomes vacuous and must perturb `W_v` instead.
        """
        if mode == "alpha-zero":
            self.alpha.zero_()
        elif mode == "wv-zero":
            self.alpha.fill_(float(alpha))
            self.w_v.weight.zero_()
        else:
            raise ValueError(f"unknown identity mode {mode!r}; "
                             "expected 'alpha-zero' or 'wv-zero'")

    @property
    def gate(self) -> torch.Tensor:
        return torch.tanh(self.alpha)

    @property
    def last_contribution(self) -> float | None:
        """`||tanh(alpha) * CCA(H)|| / ||H||` from the most recent forward.

        More informative than `alpha` alone, which is why gate-collapse detection
        keys on it: `alpha` can be large while the cross-attention output is
        negligible, and vice versa. The 2026-08-04 run had no such readout, so
        "the gate never opened" and "the gate opened onto useless memory" were
        indistinguishable in its numbers.
        """
        return self._last_contribution

    # ------------------------------------------------------------------ #
    # forward
    # ------------------------------------------------------------------ #

    def forward(
        self,
        h: torch.Tensor,                # Base LLM hidden states: [B, S, d_model]
        e_retrieved: torch.Tensor | None,  # [B, K, d_ret] static, or [B, L, K, d_ret]
        attn_mask: torch.Tensor | None = None,
        *,
        chunk_size: int | None = None,
        plan: list[ChunkSpec] | None = None,
    ) -> torch.Tensor:
        """Apply the gated cross-attention residual.

        Args:
            h: `[B, S, d_model]` intermediate hidden states.
            e_retrieved: `[B, K, d_ret]` (static: every position attends the same
                bank, used by the incremental decode loop which selects the bank
                itself) or `[B, L, K, d_ret]` (chunked: one bank per chunk, used
                by the teacher-forced path).
            plan: window plan from `chunking`. Chunked mode only. Supplied by the
                caller during incremental decode so the spans track absolute
                position; derived from `h` when omitted.

        Returns:
            `[B, S, d_model]`.
        """
        if e_retrieved is None:
            self._last_contribution = 0.0
            return h

        if e_retrieved.dim() == 4:
            cca = self._chunked_attend(h, e_retrieved,
                                       chunk_size or self.chunk_size, plan)
        else:
            cca = self._static_attend(h, e_retrieved, attn_mask)

        gated = self.gate * cca

        with torch.no_grad():
            denom = h.norm().item()
            self._last_contribution = (gated.norm().item() / denom) if denom > 0 else 0.0

        # Never short-circuited when the gate is closed. `h + 0.0 * x == h` holds
        # exactly in IEEE-754 for finite x, so bit-exact identity survives while
        # the cross-attention path is genuinely exercised -- and a NaN in that
        # path propagates rather than being silently repaired. An
        # `if alpha == 0: return h` fast path would make the identity test vacuous.
        return h + gated

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _static_attend(
        self,
        h: torch.Tensor,
        e_retrieved: torch.Tensor,
        attn_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        """Every position attends the same K slots."""
        k = self.w_k(e_retrieved)
        v = self.w_v(e_retrieved)
        out, _ = self.cross_attn(query=self.norm(h), key=k, value=v, attn_mask=attn_mask)
        return out

    def _chunked_attend(
        self,
        h: torch.Tensor,
        e_retrieved: torch.Tensor,
        m: int,
        plan: list[ChunkSpec] | None,
    ) -> torch.Tensor:
        """RETRO chunked cross-attention, driven by the plan from `chunking`.

        The causal offset is read from `spec.query_chunk` and never recomputed
        here. A window with no predecessor chunk leaves its slice at exactly zero
        -- that is the correct output, not a placeholder, and it is why no
        NaN-repair is needed: a bank is only ever attended if it exists.
        """
        b, s, d = h.shape
        n_banks = e_retrieved.size(1)
        cca = torch.zeros_like(h)
        normed = self.norm(h)

        if plan is None:
            plan = retrieval_plan(s, m)

        for spec in plan:
            if not spec.attends_to_retrieval:
                continue
            if spec.query_chunk >= n_banks:
                # Generation ran past the banks the caller supplied. Skip rather
                # than crash; the caller should size banks to prompt + new tokens.
                continue
            q = normed[:, spec.start: spec.end, :]
            if q.size(1) == 0:
                continue

            bank = e_retrieved[:, spec.query_chunk].to(h.dtype)   # [B, K, d_ret]
            out, _ = self.cross_attn(query=q, key=self.w_k(bank), value=self.w_v(bank))
            cca[:, spec.start: spec.end, :] = out

        del b, d
        return cca
