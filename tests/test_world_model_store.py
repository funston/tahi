"""
Tests for WorldModelStore (FTI Feature Pipeline)
"""

import tempfile
import unittest
from pathlib import Path

from octo import WorldModel, WorldModelStore


class WorldModelStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = WorldModelStore(self.temp_dir, compress=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_save_and_load(self):
        """Test basic save and load"""
        world = WorldModel(domain="test")
        world.upsert_node("node1", label="Test Node", type="concept")
        world.add_edge("node1", "relates_to", "node2")

        self.store.save(world, source="test-source", version="v1.0.0", model_id="test-model")

        loaded = self.store.load("test-source", "v1.0.0", model_id="test-model")

        self.assertEqual(loaded.domain, "test")
        self.assertEqual(len(loaded.nodes), 1)
        self.assertEqual(len(loaded.edges), 1)
        self.assertEqual(loaded.nodes["node1"]["label"], "Test Node")

    def test_exists(self):
        """Test exists check"""
        world = WorldModel(domain="test")
        world.upsert_node("node1", label="Test")

        self.assertFalse(self.store.exists("test-source", "v1.0.0", "test-model"))

        self.store.save(world, source="test-source", version="v1.0.0", model_id="test-model")

        self.assertTrue(self.store.exists("test-source", "v1.0.0", "test-model"))

    def test_get_or_build(self):
        """Test lazy loading with get_or_build"""
        build_count = 0

        def builder():
            nonlocal build_count
            build_count += 1
            world = WorldModel(domain="test")
            world.upsert_node(f"node{build_count}", label=f"Node {build_count}")
            return world

        # First call: builds
        world1 = self.store.get_or_build(
            builder,
            source="test",
            version="v1.0.0",
            model_id="model1",
        )
        self.assertEqual(build_count, 1)
        self.assertEqual(len(world1.nodes), 1)

        # Second call: loads from cache
        world2 = self.store.get_or_build(
            builder,
            source="test",
            version="v1.0.0",
            model_id="model1",
        )
        self.assertEqual(build_count, 1)  # Should not rebuild
        self.assertEqual(len(world2.nodes), 1)

        # Force rebuild
        world3 = self.store.get_or_build(
            builder,
            source="test",
            version="v1.0.0",
            model_id="model1",
            force_rebuild=True,
        )
        self.assertEqual(build_count, 2)  # Should rebuild

    def test_list_versions(self):
        """Test listing versions"""
        world = WorldModel(domain="test")
        world.upsert_node("node1", label="Test")

        self.assertEqual(self.store.list_versions("test-source"), [])

        self.store.save(world, source="test-source", version="v1.0.0", model_id="model1")
        self.store.save(world, source="test-source", version="v1.1.0", model_id="model1")

        versions = self.store.list_versions("test-source")
        self.assertEqual(sorted(versions), ["v1.0.0", "v1.1.0"])

    def test_list_models(self):
        """Test listing models in a version"""
        world = WorldModel(domain="test")
        world.upsert_node("node1", label="Test")

        self.assertEqual(self.store.list_models("test-source", "v1.0.0"), [])

        self.store.save(world, source="test-source", version="v1.0.0", model_id="model1")
        self.store.save(world, source="test-source", version="v1.0.0", model_id="model2")

        models = self.store.list_models("test-source", "v1.0.0")
        self.assertEqual(sorted(models), ["model1", "model2"])

    def test_manifest(self):
        """Test manifest creation and retrieval"""
        world = WorldModel(domain="test-domain")
        world.upsert_node("node1", label="Test")
        world.upsert_node("node2", label="Test2")
        world.add_edge("node1", "relates_to", "node2")

        self.store.save(
            world,
            source="test-source",
            version="v1.0.0",
            model_id="model1",
            metadata={"enrichment": "test"},
        )

        manifest = self.store.get_manifest("test-source", "v1.0.0")

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.source, "test-source")
        self.assertEqual(manifest.version, "v1.0.0")
        self.assertEqual(manifest.domain, "test-domain")
        self.assertEqual(manifest.num_nodes, 2)
        self.assertEqual(manifest.num_edges, 1)
        self.assertIn("models", manifest.metadata)
        self.assertEqual(manifest.metadata["models"]["model1"]["enrichment"], "test")

    def test_compression(self):
        """Test gzip compression"""
        store_compressed = WorldModelStore(self.temp_dir + "/compressed", compress=True)

        world = WorldModel(domain="test")
        for i in range(100):
            world.upsert_node(f"node{i}", label=f"Node {i}", type="concept")

        store_compressed.save(world, source="test", version="v1.0.0", model_id="large")

        # Check file exists with .gz extension
        model_path = store_compressed._model_path("test", "v1.0.0", "large")
        self.assertTrue(model_path.exists())
        self.assertTrue(str(model_path).endswith(".json.gz"))

        # Load and verify
        loaded = store_compressed.load("test", "v1.0.0", "large")
        self.assertEqual(len(loaded.nodes), 100)

    def test_use_ann_preserved(self):
        """Test that use_ann flag is preserved through save/load"""
        world = WorldModel(domain="test", use_ann=True)
        world.upsert_node("node1", label="Test")

        self.store.save(world, source="test", version="v1.0.0", model_id="ann-model")

        loaded = self.store.load("test", "v1.0.0", "ann-model")
        self.assertTrue(loaded.use_ann)


if __name__ == "__main__":
    unittest.main()
