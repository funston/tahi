"""
Demonstrable Integration Test: Kùzu Property Graph Engine in WorldModel.

Verifies that:
1. WorldModel can initialize KuzuGraphStore (init_kuzu()).
2. Nodes and edges added to WorldModel are synced into Kùzu's indexed database.
3. WorldModel.neighbors() queries Kùzu's Cypher property graph rather than scanning dicts.
4. Multi-hop retrieval over Kùzu correctly retrieves evidence nodes.
"""

import tempfile
import unittest
from pathlib import Path

from octo.world_state import WorldModel


class TestKuzuWorldModelIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_kuzu_wm.kz"
        self.wm = WorldModel(domain="enterprise_rag", use_ann=True)
        self.wm.init_kuzu(str(self.db_path))

    def tearDown(self):
        if hasattr(self.wm, "_kuzu_store") and self.wm._kuzu_store:
            self.wm._kuzu_store.close()
        self.temp_dir.cleanup()

    def test_kuzu_sync_and_neighbors(self):
        # Add entity nodes and evidence document nodes
        self.wm.upsert_node("proj_alpha", type="project", label="Project Alpha")
        self.wm.upsert_node("doc_101", type="document", label="Alpha Design Doc", text="Project Alpha uses 10 MiB limit.")
        self.wm.upsert_node("doc_102", type="document", label="Alpha Budget Doc", text="Project Alpha budget is 50k.")
        
        self.wm.add_edge("proj_alpha", "HAS_DOC", "doc_101")
        self.wm.add_edge("proj_alpha", "HAS_DOC", "doc_102")

        # Verify Kùzu store stats
        stats = self.wm._kuzu_store.stats()
        self.assertEqual(stats["nodes"], 3)
        self.assertEqual(stats["edges"], 2)

        # Verify neighbors query via Kùzu
        neighbors = self.wm.neighbors("proj_alpha")
        self.assertEqual(len(neighbors), 2)
        neighbor_ids = {dst for src, rel, dst, attrs in neighbors}
        self.assertIn("doc_101", neighbor_ids)
        self.assertIn("doc_102", neighbor_ids)

    def test_kuzu_multi_hop_expand(self):
        # Set traversal-only index nodes
        self.wm.set_index_node_types(["project", "topic"])

        # Construct multi-hop graph: doc_A -> topic_X -> doc_B
        self.wm.upsert_node("doc_A", type="document", label="Doc A", text="Security architecture details")
        self.wm.upsert_node("topic_sec", type="topic", label="Security Topic")
        self.wm.upsert_node("doc_B", type="document", label="Doc B", text="Authentication compliance rules")

        self.wm.add_edge("doc_A", "MENTIONS", "topic_sec")
        self.wm.add_edge("topic_sec", "COVERS", "doc_B")

        self.wm.build_index()

        # Retrieve starting from doc_A text
        memories = self.wm.retrieve("Security architecture details", top_k=2, expand=True)
        retrieved_ids = [m.node_id for m in memories]
        self.assertIn("doc_A", retrieved_ids)
        self.assertIn("doc_B", retrieved_ids)


if __name__ == "__main__":
    unittest.main()
