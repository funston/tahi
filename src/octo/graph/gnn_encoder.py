"""
Relational Graph Attention Network (RGAT) Encoder for OCTO.

Computes topology-aware node embeddings over retrieved subgraphs by running
relation-aware message passing across multi-relational graph edges.

Output node embeddings encode both node semantic content AND graph structural
topology, feeding directly into Level 3 Gated Chunked Cross-Attention (GCCA).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional


class RelationalGraphAttentionLayer(nn.Module):
    """
    Relational Graph Attention (RGAT) Layer.
    
    Computes relation-specific query, key, value projections and attention weights
    across heterogeneous edges (src, relation_type, dst).
    """

    def __init__(self, in_features: int, out_features: int, num_relations: int = 16, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.num_relations = num_relations
        self.num_heads = num_heads
        self.head_dim = out_features // num_heads

        # Relation-specific transformation matrices
        self.w_relation = nn.Parameter(torch.Tensor(num_relations, in_features, out_features))
        self.attn_src = nn.Parameter(torch.Tensor(num_heads, self.head_dim))
        self.attn_dst = nn.Parameter(torch.Tensor(num_heads, self.head_dim))
        self.bias = nn.Parameter(torch.Tensor(out_features))

        self.dropout = nn.Dropout(dropout)
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.xavier_uniform_(self.w_relation)
        nn.init.xavier_uniform_(self.attn_src.unsqueeze(0))
        nn.init.xavier_uniform_(self.attn_dst.unsqueeze(0))
        nn.init.zeros_(self.bias)

    def forward(
        self,
        node_features: torch.Tensor,               # [K, in_features]
        edge_index: torch.Tensor,                  # [2, E] (src_idx, dst_idx)
        edge_type: torch.Tensor,                   # [E] relation type indices
    ) -> torch.Tensor:
        """
        Forward pass for Relational Graph Attention over a retrieved subgraph.
        
        Returns:
            [K, out_features] GNN topological node embeddings.
        """
        num_nodes = node_features.size(0)
        if num_nodes == 0:
            return torch.empty((0, self.out_features), device=node_features.device)

        if edge_index.numel() == 0:
            # Self-loop transformation if no edges exist
            w_default = self.w_relation[0]
            out = torch.matmul(node_features, w_default) + self.bias
            return F.relu(out)

        src_idx, dst_idx = edge_index[0], edge_index[1]

        # Apply relation-specific linear transformations for each edge
        # [E, in_features]
        edge_src_feat = node_features[src_idx]
        edge_rel_w = self.w_relation[edge_type] # [E, in_features, out_features]

        # Transformed features per edge: [E, out_features]
        transformed_edges = torch.bmm(edge_src_feat.unsqueeze(1), edge_rel_w).squeeze(1)

        # Multi-head attention computation
        # [E, num_heads, head_dim]
        t_reshaped = transformed_edges.view(-1, self.num_heads, self.head_dim)
        edge_dst_feat = torch.bmm(node_features[dst_idx].unsqueeze(1), edge_rel_w).squeeze(1)
        dst_feat = edge_dst_feat.view(-1, self.num_heads, self.head_dim)

        score_src = (t_reshaped * self.attn_src).sum(dim=-1) # [E, num_heads]
        score_dst = (dst_feat * self.attn_dst).sum(dim=-1)   # [E, num_heads]
        edge_attn = F.leaky_relu(score_src + score_dst, negative_slope=0.2)

        # Scatter softmax normalization per destination node
        attn_weights = torch.zeros_like(edge_attn)
        for i in range(num_nodes):
            mask = (dst_idx == i)
            if mask.any():
                attn_weights[mask] = F.softmax(edge_attn[mask], dim=0)

        attn_weights = self.dropout(attn_weights).unsqueeze(-1) # [E, num_heads, 1]

        # Aggregation over incoming edges per node
        aggregated = torch.zeros((num_nodes, self.num_heads, self.head_dim), device=node_features.device)
        for i in range(num_nodes):
            mask = (dst_idx == i)
            if mask.any():
                msg = (t_reshaped[mask] * attn_weights[mask]).sum(dim=0)
                aggregated[i] = msg

        out = aggregated.view(num_nodes, self.out_features) + self.bias
        return F.relu(out)


class SubgraphRGATEncoder(nn.Module):
    """
    Complete Subgraph Relational GNN Encoder.
    
    Converts a retrieved subgraph (node texts + relational edges) into a
    topological memory tensor [1, K, d_retriever] for GCCA injection.
    """

    def __init__(self, d_in: int = 384, d_hidden: int = 384, d_out: int = 768, num_relations: int = 16):
        super().__init__()
        self.rgat1 = RelationalGraphAttentionLayer(d_in, d_hidden, num_relations=num_relations)
        self.rgat2 = RelationalGraphAttentionLayer(d_hidden, d_out, num_relations=num_relations)
        self.residual_proj = nn.Linear(d_in, d_out)

    def forward(
        self,
        node_embeddings: torch.Tensor,             # [K, d_in]
        edge_tuples: List[Tuple[int, int, int]],    # [(src_idx, rel_type_idx, dst_idx)]
    ) -> torch.Tensor:
        """
        Encode subgraph nodes into GNN topological memory tensor [1, K, d_out].
        """
        K, d_in = node_embeddings.shape
        if K == 0:
            return torch.empty((1, 0, self.rgat2.out_features), device=node_embeddings.device)

        if not edge_tuples:
            # Dense residual path if no edges
            res = self.residual_proj(node_embeddings)
            return res.unsqueeze(0)

        src_list = [e[0] for e in edge_tuples]
        rel_list = [e[1] for e in edge_tuples]
        dst_list = [e[2] for e in edge_tuples]

        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long, device=node_embeddings.device)
        edge_type = torch.tensor(rel_list, dtype=torch.long, device=node_embeddings.device)

        # 2-Layer RGAT message passing
        h1 = self.rgat1(node_embeddings, edge_index, edge_type)
        h2 = self.rgat2(h1, edge_index, edge_type)

        # Residual connection from input embeddings
        out = h2 + self.residual_proj(node_embeddings)
        return out.unsqueeze(0) # [1, K, d_out]
