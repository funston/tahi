"""
PyTorch implementation of Gated Chunked Cross-Attention (GCCA) for OCTO native residual injection.

Implements intermediate layer cross-attention between frozen LLM hidden states and
retrieved graph/vector world-state memory. Gated by a zero-initialized tanh(alpha)
scalar parameter to guarantee zero logit disruption at step 0 (Flamingo / InstructRetro principle).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


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
    ):
        super().__init__()
        self.d_model = d_model
        self.d_retriever = d_retriever
        self.num_heads = num_heads

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

    def forward(
        self,
        h: torch.Tensor,                # Base LLM hidden states: [B, S, d_model]
        e_retrieved: torch.Tensor,      # Fused graph/vector memory: [B, K, d_retriever]
        attn_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Forward pass for GCCA block.

        Args:
            h: [B, S, d_model] Tensor of intermediate Transformer layer hidden states.
            e_retrieved: [B, K, d_retriever] Tensor of retrieved memory node vectors.
            attn_mask: Optional attention mask.

        Returns:
            [B, S, d_model] Hidden state tensor with gated cross-attention residual added.
        """
        # Pre-LN
        normed_h = self.norm(h)

        # Project retrieved vectors to key/value space
        k = self.w_k(e_retrieved)       # [B, K, d_model]
        v = self.w_v(e_retrieved)       # [B, K, d_model]

        # Cross-attend: Query = normed_h, Key = k, Value = v
        attn_out, _ = self.cross_attn(
            query=normed_h,
            key=k,
            value=v,
            attn_mask=attn_mask,
        )

        # Residual connection gated by tanh(alpha)
        gate = torch.tanh(self.alpha)
        return h + gate * attn_out
