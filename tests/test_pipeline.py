import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender import BlackBoxIntegration, NativeIntegration, WorldModel, wrap_llm


def build_world_model() -> WorldModel:
    wm = WorldModel(domain="biomedical")
    wm.upsert_node(
        "marine_bacteria",
        label="marine bacteria",
        type="organism",
        summary="Marine bacteria produce natural products and metabolites.",
        keywords=["marine", "bacteria", "metabolites", "natural"],
    )
    wm.upsert_node(
        "antimalarial_compounds",
        label="antimalarial compounds",
        type="compound_class",
        summary="Compounds used to inhibit malaria parasites.",
        keywords=["antimalarial", "malaria", "compounds", "screening"],
    )
    wm.upsert_node(
        "plasmodium_falciparum",
        label="Plasmodium falciparum",
        type="pathogen",
        summary="A malaria parasite used in assay screening.",
        keywords=["plasmodium", "falciparum", "malaria", "assay"],
    )
    wm.add_edge("marine_bacteria", "produces", "antimalarial_compounds", score=0.88)
    wm.add_edge("antimalarial_compounds", "tested_against", "plasmodium_falciparum", score=0.9)
    return wm


class PipelineTests(unittest.TestCase):
    def test_black_box_pipeline_emits_control_packet_and_reasoning_outputs(self):
        model = wrap_llm(
            "demo-black-box",
            world_model=build_world_model(),
            integration=BlackBoxIntegration(),
        )

        result = model.ask(
            "Can marine bacteria produce antimalarial compounds for screening?",
            mode="coprocessor",
            trace=True,
        )

        self.assertIn("marine bacteria", result["entities"])
        self.assertTrue(result["hypotheses"])
        self.assertEqual(result["control_packet"]["integration"], "black_box")
        self.assertTrue(result["retrievals"])
        self.assertTrue(any(item["reference"].startswith("rule:") for item in result["provenance"]))
        self.assertEqual(result["simulation"]["status"], "estimated")

    def test_native_pipeline_accepts_hidden_state_and_marks_native_integration(self):
        model = wrap_llm(
            "demo-native",
            world_model=build_world_model(),
            integration=NativeIntegration(),
        )

        result = model.ask(
            "Can marine bacteria produce antimalarial compounds for Plasmodium falciparum screening?",
            mode="latent",
            trace=True,
            hidden_state=[0.8, 0.1, 0.2, 0.7, 0.0, 0.3, 0.5, 0.9],
        )

        self.assertEqual(result["control_packet"]["integration"], "native_hidden_state")
        self.assertTrue(result["control_packet"]["metadata"]["hidden_state_present"])
        self.assertGreater(result["fusion"]["graph_weight"], 0.0)
        self.assertIn("Plasmodium falciparum", result["entities"])


if __name__ == "__main__":
    unittest.main()
