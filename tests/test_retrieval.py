import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from tahi.world_state import WorldModel


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


def test_embedding_text_falls_back_to_text_when_no_summary():
    """A node with `text` and no `summary` must index on its content.

    It previously indexed on its label alone, so a document store built the
    obvious way retrieved on identifiers rather than content -- no error, no
    warning, just uniformly wrong neighbours.
    """
    from tahi.world_state import WorldModel

    wm = WorldModel(use_ann=False)
    wm.upsert_node("fact::0", label="fact::0", text="Kismet was directed by William Dieterle.")
    assert "William Dieterle" in wm.embedding_text("fact::0")


def test_embedding_text_prefers_summary_when_both_present():
    """Existing callers that set both keep byte-identical behaviour."""
    from tahi.world_state import WorldModel

    wm = WorldModel(use_ann=False)
    wm.upsert_node("doc::1", label="doc::1", summary="short form", text="the very long form")
    assert wm.embedding_text("doc::1") == "doc::1 short form"
