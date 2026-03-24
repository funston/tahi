import json

from bender import (
    BlackBoxIntegration,
    ComparisonCase,
    WorldModel,
    comparison_suite_to_dict,
    evaluate_comparison_suite,
    wrap_llm,
)
from bender.demo_worlds import (
    build_biomedical_world_model,
    build_hello_world_animal_model,
)


def build_empty_world_model(domain: str) -> WorldModel:
    return WorldModel(domain=f"{domain}_baseline")


def run_hello_world_comparison() -> dict:
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

    cases = [
        ComparisonCase(
            name="penguin_exception",
            query="Can a penguin fly?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=4,
            required_with_bender_hypothesis_substrings=(
                "penguin-specific exception overrides the default flying capability",
            ),
            forbidden_without_bender_hypothesis_substrings=("penguin-specific exception",),
            expected_with_bender_integration="black_box",
        ),
        ComparisonCase(
            name="antarctic_fish_eaters",
            query="What animals in Antarctica eat fish?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=4,
            required_with_bender_constraints={
                "antarctic_fish_eaters": ["penguin", "seal"],
            },
            required_with_bender_hypothesis_substrings=(
                "animals in antarctica that eat fish include penguin, seal",
            ),
            forbidden_without_bender_hypothesis_substrings=("penguin, seal",),
            expected_with_bender_integration="black_box",
        ),
    ]
    return comparison_suite_to_dict(
        evaluate_comparison_suite(
            "hello_world_with_vs_without_bender",
            with_bender_model=with_bender,
            without_bender_model=without_bender,
            cases=cases,
        )
    )


def run_biomedical_comparison() -> dict:
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

    cases = [
        ComparisonCase(
            name="marine_bacteria_screening",
            query="Can marine bacteria produce antimalarial compounds for screening?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=5,
            required_with_bender_constraints={"screening_priority": "natural_products"},
            required_with_bender_hypothesis_substrings=(
                "plausible sources of antimalarial compounds worth screening",
            ),
            forbidden_without_bender_hypothesis_substrings=(
                "antimalarial compounds worth screening",
            ),
            expected_with_bender_integration="black_box",
        ),
        ComparisonCase(
            name="plasmodium_assay_target",
            query="Can marine bacteria produce antimalarial compounds for Plasmodium falciparum screening?",
            expected_entity_gain=3,
            expected_retrieval_gain=3,
            expected_provenance_gain=6,
            required_with_bender_constraints={"assay_target": "plasmodium_falciparum"},
            required_with_bender_hypothesis_substrings=(
                "testing marine-derived metabolites against plasmodium falciparum assays",
            ),
            forbidden_without_bender_hypothesis_substrings=(
                "plasmodium falciparum assays",
            ),
            expected_with_bender_integration="black_box",
        ),
    ]
    return comparison_suite_to_dict(
        evaluate_comparison_suite(
            "biomedical_with_vs_without_bender",
            with_bender_model=with_bender,
            without_bender_model=without_bender,
            cases=cases,
        )
    )


if __name__ == "__main__":
    result = {
        "hello_world": run_hello_world_comparison(),
        "biomedical": run_biomedical_comparison(),
    }
    print(json.dumps(result, indent=2))
