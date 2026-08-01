import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo.fusion import WeightedBlendFusion
from octo.models import CognitiveState, Hypothesis, RetrievedMemory


class FusionTests(unittest.TestCase):
    def test_weighted_blend_shifts_toward_graph_signal_when_retrieval_is_strong(self):
        state = CognitiveState(
            retrievals=[
                RetrievedMemory(
                    node_id="marine_bacteria",
                    label="marine bacteria",
                    node_type="organism",
                    score=0.9,
                ),
                RetrievedMemory(
                    node_id="antimalarial_compounds",
                    label="antimalarial compounds",
                    node_type="compound_class",
                    score=0.85,
                ),
            ],
            hypotheses=[Hypothesis(text="screen marine-derived compounds", confidence=0.8)],
            constraints={"assay_target": "plasmodium_falciparum"},
        )
        mixer = WeightedBlendFusion(width=4)

        fused = mixer.mix(
            token_signal=[1.0, 0.0, 0.0, 0.0],
            graph_signal=[0.0, 1.0, 0.0, 0.0],
            state=state,
        )

        self.assertGreater(fused.graph_weight, fused.token_weight)
        self.assertAlmostEqual(sum((fused.token_weight, fused.graph_weight)), 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
