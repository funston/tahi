"""
Demonstrable Integration Test: Relational Graph Attention Network (RGAT) & GCCA Memory Tensor.

Verifies that:
1. SubgraphRGATEncoder computes Relational Graph Attention over retrieved subgraphs.
2. Message passing updates node features based on graph topology and relation types.
3. build_memory_tensor(gnn_encoder=...) yields GNN topological memory tensors [1, K, d_retriever].
4. Topological memory tensor feeds cleanly into GatedChunkedCrossAttention (GCCA Level 3).
"""

import unittest

import torch

from tahi.graph.gnn_encoder import SubgraphRGATEncoder
from tahi.models import CognitiveState, RetrievedMemory
from tahi.native.gcca_layer import GatedChunkedCrossAttention
from tahi.native.memory import build_memory_tensor, memory_is_informative
from tahi.world_state import WorldModel


class TestGNNEncoder(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        self.encoder = SubgraphRGATEncoder(d_in=384, d_hidden=384, d_out=768, num_relations=16)

    def test_rgat_layer_forward_and_shapes(self):
        # 3 nodes, 2 edges
        node_feats = torch.randn(3, 384)
        edge_tuples = [(0, 1, 1), (1, 2, 2)] # (node_0 -rel_1-> node_1, node_1 -rel_2-> node_2)

        out_tensor = self.encoder(node_feats, edge_tuples)
        self.assertEqual(out_tensor.shape, (1, 3, 768))

    def test_gnn_topological_memory_tensor_building(self):
        wm = WorldModel(domain="enterprise_rag", use_ann=True)
        wm.upsert_node("doc_101", type="document", label="Security Doc", text="Security architecture details")
        wm.upsert_node("doc_102", type="document", label="Compliance Doc", text="Compliance guidelines")
        wm.add_edge("doc_101", "RELATED_TO", "doc_102")
        wm.build_index()

        state = CognitiveState()
        state.retrievals = [
            RetrievedMemory(node_id="doc_101", label="Security Doc", node_type="document", score=0.9, attributes={}, relations=[]),
            RetrievedMemory(node_id="doc_102", label="Compliance Doc", node_type="document", score=0.8, attributes={}, relations=[]),
        ]

        gnn_memory = build_memory_tensor(state, wm, gnn_encoder=self.encoder)
        self.assertIsNotNone(gnn_memory)
        self.assertEqual(gnn_memory.shape, (1, 2, 768))
        self.assertTrue(memory_is_informative(gnn_memory))

    def test_gnn_memory_tensor_fed_into_gcca_level3(self):
        # Feed GNN memory tensor directly into Level 3 GCCA block
        gcca = GatedChunkedCrossAttention(d_model=768, d_retriever=768)
        gcca.eval()

        # Set non-zero alpha to activate cross-attention residual
        with torch.no_grad():
            gcca.alpha.fill_(0.5)

        h_llm = torch.randn(1, 16, 768) # Base LLM hidden states [B, S, d_model]
        node_feats = torch.randn(2, 384)
        edge_tuples = [(0, 1, 1)]
        gnn_memory = self.encoder(node_feats, edge_tuples)

        with torch.no_grad():
            out_llm = gcca(h_llm, gnn_memory)

        self.assertEqual(out_llm.shape, (1, 16, 768))
        self.assertFalse(torch.equal(out_llm, h_llm), "GNN topological memory tensor must alter LLM hidden states when alpha > 0.")


if __name__ == "__main__":
    unittest.main()
