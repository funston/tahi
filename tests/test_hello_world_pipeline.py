import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender import NativeTokenformerIntegration, wrap_llm
from bender.demo_worlds import build_hello_world_animal_model


class HelloWorldPipelineTests(unittest.TestCase):
    def test_penguin_exception_is_explicit_in_reasoning_pipeline(self):
        model = wrap_llm(
            "hello-world",
            world_model=build_hello_world_animal_model(),
            integration=NativeTokenformerIntegration(),
            top_k=5,
        )

        result = model.ask(
            "Can a penguin fly?",
            mode="latent",
            trace=True,
            hidden_state=[0.8, 0.0, 0.1, 0.9, 0.1, 0.2, 0.4, 0.7],
        )

        texts = [item["text"] for item in result["hypotheses"]]
        self.assertTrue(any("cannot fly" in text for text in texts))
        self.assertEqual(result["control_packet"]["integration"], "native_tokenformer")
        self.assertEqual(
            result["control_packet"]["metadata"]["adapter_action"],
            "tokenformer_coprocessor_delta",
        )
        self.assertTrue(
            any(item["reference"] == "rule:penguin_exception_override" for item in result["provenance"])
        )

    def test_antarctic_fish_eaters_are_resolved_from_relation_intersection(self):
        model = wrap_llm(
            "hello-world",
            world_model=build_hello_world_animal_model(),
            top_k=5,
        )

        result = model.ask(
            "What animals in Antarctica eat fish?",
            mode="coprocessor",
            trace=True,
        )

        self.assertEqual(
            result["constraints"]["antarctic_fish_eaters"],
            ["penguin", "seal"],
        )
        self.assertTrue(
            any("penguin, seal" in item["text"] for item in result["hypotheses"])
        )


if __name__ == "__main__":
    unittest.main()
