import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender import BlackBoxIntegration, ComparisonCase, WorldModel, evaluate_comparison_suite, wrap_llm
from bender.demo_worlds import build_biomedical_world_model, build_hello_world_animal_model


def build_empty_world_model(domain: str) -> WorldModel:
    return WorldModel(domain=f"{domain}_baseline")


class ComparisonEvaluationTests(unittest.TestCase):
    def test_hello_world_comparison_shows_bender_reasoning_gain(self):
        with_bender = wrap_llm(
            "hello-world-with-bender",
            world_model=build_hello_world_animal_model(),
            integration=BlackBoxIntegration(),
            top_k=5,
        )
        without_bender = wrap_llm(
            "hello-world-without-bender",
            world_model=build_empty_world_model("hello_world"),
            integration=BlackBoxIntegration(),
            top_k=5,
        )

        result = evaluate_comparison_suite(
            "hello_world_compare",
            with_bender_model=with_bender,
            without_bender_model=without_bender,
            cases=[
                ComparisonCase(
                    name="penguin_exception",
                    query="Can a penguin fly?",
                    expected_entity_gain=2,
                    expected_retrieval_gain=2,
                    required_with_bender_hypothesis_substrings=("penguin-specific exception",),
                    forbidden_without_bender_hypothesis_substrings=("penguin-specific exception",),
                    expected_with_bender_integration="black_box",
                )
            ],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.passed_cases, 1)

    def test_biomedical_comparison_shows_constraint_gain(self):
        with_bender = wrap_llm(
            "bio-with-bender",
            world_model=build_biomedical_world_model(),
            integration=BlackBoxIntegration(),
            top_k=5,
        )
        without_bender = wrap_llm(
            "bio-without-bender",
            world_model=build_empty_world_model("biomedical"),
            integration=BlackBoxIntegration(),
            top_k=5,
        )

        result = evaluate_comparison_suite(
            "bio_compare",
            with_bender_model=with_bender,
            without_bender_model=without_bender,
            cases=[
                ComparisonCase(
                    name="screening_priority",
                    query="Can marine bacteria produce antimalarial compounds for screening?",
                    expected_entity_gain=2,
                    expected_retrieval_gain=2,
                    required_with_bender_constraints={"screening_priority": "natural_products"},
                    required_with_bender_hypothesis_substrings=("antimalarial compounds worth screening",),
                    forbidden_without_bender_hypothesis_substrings=("antimalarial compounds worth screening",),
                    expected_with_bender_integration="black_box",
                )
            ],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.passed_cases, 1)


if __name__ == "__main__":
    unittest.main()
