import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import WorldModel, build_pagila_fixture_snapshot, snapshot_to_world_model  # noqa: E402


class WorldCacheTests(unittest.TestCase):
    def test_world_model_round_trip_json(self):
        world = snapshot_to_world_model(build_pagila_fixture_snapshot())

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "world.json")
            world.save_json(path)
            loaded = WorldModel.load_json(path)

        self.assertEqual(world.domain, loaded.domain)
        self.assertEqual(set(world.nodes), set(loaded.nodes))
        self.assertEqual(len(world.edges), len(loaded.edges))

    def test_world_model_to_dict_shape(self):
        world = snapshot_to_world_model(build_pagila_fixture_snapshot())
        payload = world.to_dict()

        self.assertIn("domain", payload)
        self.assertIn("nodes", payload)
        self.assertIn("edges", payload)
        self.assertTrue(payload["nodes"])
        self.assertTrue(payload["edges"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
