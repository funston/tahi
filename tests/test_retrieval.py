import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender.world_state import WorldModel


class RetrievalTests(unittest.TestCase):
    def test_world_model_retrieval_returns_relevant_biomedical_nodes(self):
        wm = WorldModel(domain="biomedical")
        wm.upsert_node(
            "marine_bacteria",
            label="marine bacteria",
            type="organism",
            summary="Marine bacteria produce natural products with bioactive potential.",
            keywords=["marine", "bacteria", "natural", "products"],
        )
        wm.upsert_node(
            "antimalarial_compounds",
            label="antimalarial compounds",
            type="compound_class",
            summary="Compounds used in malaria screening.",
            keywords=["antimalarial", "malaria", "screening"],
        )
        wm.upsert_node(
            "contract_law",
            label="contract law",
            type="legal_domain",
            summary="A legal domain unrelated to malaria.",
            keywords=["legal", "contract", "precedent"],
        )
        wm.add_edge("marine_bacteria", "produces", "antimalarial_compounds", score=0.9)

        results = wm.retrieve("marine bacteria antimalarial screening", top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].node_id, "marine_bacteria")
        self.assertIn(results[1].node_id, {"marine_bacteria", "antimalarial_compounds"})
        self.assertTrue(all(result.score > 0.0 for result in results))


if __name__ == "__main__":
    unittest.main()
