import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import BlackBoxIntegration, ComparisonCase, WorldModel, evaluate_comparison_suite, wrap_llm
from octo.demo_worlds import build_biomedical_world_model, build_hello_world_animal_model


def build_empty_world_model(domain: str) -> WorldModel:
    return WorldModel(domain=f"{domain}_baseline")


class ComparisonEvaluationTests(unittest.TestCase):
    def test_hello_world_comparison_shows_octo_reasoning_gain(self):
        with_octo = wrap_llm(
            "hello-world-with-octo",
            world_model=build_hello_world_animal_model(),
            integration=BlackBoxIntegration(),
            top_k=5,
        )
        without_octo = wrap_llm(
            "hello-world-without-octo",
            world_model=build_empty_world_model("hello_world"),
            integration=BlackBoxIntegration(),
            top_k=5,
        )

        result = evaluate_comparison_suite(
            "hello_world_compare",
            with_octo_model=with_octo,
            without_octo_model=without_octo,
            cases=[
                ComparisonCase(
                    name="penguin_exception",
                    query="Can a penguin fly?",
                    expected_entity_gain=2,
                    expected_retrieval_gain=2,
                    required_with_octo_hypothesis_substrings=("explicit exception",),
                    forbidden_without_octo_hypothesis_substrings=("explicit exception",),
                    expected_with_octo_integration="black_box",
                )
            ],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.passed_cases, 1)

    def test_biomedical_comparison_shows_constraint_gain(self):
        with_octo = wrap_llm(
            "bio-with-octo",
            world_model=build_biomedical_world_model(),
            integration=BlackBoxIntegration(),
            top_k=5,
        )
        without_octo = wrap_llm(
            "bio-without-octo",
            world_model=build_empty_world_model("biomedical"),
            integration=BlackBoxIntegration(),
            top_k=5,
        )

        result = evaluate_comparison_suite(
            "bio_compare",
            with_octo_model=with_octo,
            without_octo_model=without_octo,
            cases=[
                ComparisonCase(
                    name="screening_priority",
                    query="Can marine bacteria produce antimalarial compounds for screening?",
                    expected_entity_gain=2,
                    expected_retrieval_gain=2,
                    expected_provenance_gain=1,
                    expected_with_octo_integration="black_box",
                )
            ],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.passed_cases, 1)


if __name__ == "__main__":
    unittest.main()
