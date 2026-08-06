import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import build_schema_compression_plan, snapshot_to_world_model  # noqa: E402
from implementations.spider import SpiderSnowflakeMetadataLoader  # noqa: E402

import pytest  # noqa: E402

SPIDER2_ROOT = os.environ.get("SPIDER2_ROOT", "")
pytestmark = pytest.mark.skipif(
    not SPIDER2_ROOT or not os.path.isdir(SPIDER2_ROOT),
    reason="Spider2 dataset not present; set SPIDER2_ROOT to run these tests.",
)





class SchemaCompressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = SpiderSnowflakeMetadataLoader()
        cls.snapshot = loader.load(
            SPIDER2_ROOT + "/spider2-snow/resource/databases/TCGA_MITELMAN",
            db_id="TCGA_MITELMAN",
        )

    def test_tcga_compression_groups_release_families(self):
        plan = build_schema_compression_plan(self.snapshot)
        family_labels = {family.label: len(family.members) for family in plan.families}

        self.assertGreaterEqual(family_labels.get("versioned clinical <source> <release>", 0), 5)
        self.assertGreaterEqual(
            family_labels.get("versioned per sample file metadata <assembly> <source> <release>", 0),
            5,
        )

    def test_world_model_includes_schema_family_nodes(self):
        world = snapshot_to_world_model(self.snapshot)
        family_nodes = [node_id for node_id, attrs in world.nodes.items() if attrs.get("type") == "schema_family"]
        self.assertTrue(any("clinical" in world.nodes[node_id]["label"] for node_id in family_nodes))
        table_node = "table:TCGA_VERSIONED.CLINICAL_GDC_R24"
        self.assertEqual(
            world.nodes[table_node]["schema_family_label"],
            "versioned clinical <source> <release>",
        )


if __name__ == "__main__":
    unittest.main()
