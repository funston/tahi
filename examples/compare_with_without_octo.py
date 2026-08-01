import json

from octo import (
    BlackBoxIntegration,
    ComparisonCase,
    WorldModel,
    comparison_suite_to_dict,
    evaluate_comparison_suite,
    wrap_llm,
)
from octo.demo_worlds import (
    build_biomedical_world_model,
    build_hello_world_animal_model,
)


def build_empty_world_model(domain: str) -> WorldModel:
    return WorldModel(domain=f"{domain}_baseline")


def run_hello_world_comparison() -> dict:
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

    cases = [
        ComparisonCase(
            name="penguin_exception",
            query="Can a penguin fly?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=4,
            required_with_octo_hypothesis_substrings=(
                "penguin-specific exception overrides the default flying capability",
            ),
            forbidden_without_octo_hypothesis_substrings=("penguin-specific exception",),
            expected_with_octo_integration="black_box",
        ),
        ComparisonCase(
            name="antarctic_fish_eaters",
            query="What animals in Antarctica eat fish?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=4,
            required_with_octo_constraints={
                "antarctic_fish_eaters": ["penguin", "seal"],
            },
            required_with_octo_hypothesis_substrings=(
                "animals in antarctica that eat fish include penguin, seal",
            ),
            forbidden_without_octo_hypothesis_substrings=("penguin, seal",),
            expected_with_octo_integration="black_box",
        ),
    ]
    return comparison_suite_to_dict(
        evaluate_comparison_suite(
            "hello_world_with_vs_without_octo",
            with_octo_model=with_octo,
            without_octo_model=without_octo,
            cases=cases,
        )
    )


def run_biomedical_comparison() -> dict:
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

    cases = [
        ComparisonCase(
            name="marine_bacteria_screening",
            query="Can marine bacteria produce antimalarial compounds for screening?",
            expected_entity_gain=2,
            expected_retrieval_gain=2,
            expected_provenance_gain=5,
            required_with_octo_constraints={"screening_priority": "natural_products"},
            required_with_octo_hypothesis_substrings=(
                "plausible sources of antimalarial compounds worth screening",
            ),
            forbidden_without_octo_hypothesis_substrings=(
                "antimalarial compounds worth screening",
            ),
            expected_with_octo_integration="black_box",
        ),
        ComparisonCase(
            name="plasmodium_assay_target",
            query="Can marine bacteria produce antimalarial compounds for Plasmodium falciparum screening?",
            expected_entity_gain=3,
            expected_retrieval_gain=3,
            expected_provenance_gain=6,
            required_with_octo_constraints={"assay_target": "plasmodium_falciparum"},
            required_with_octo_hypothesis_substrings=(
                "testing marine-derived metabolites against plasmodium falciparum assays",
            ),
            forbidden_without_octo_hypothesis_substrings=(
                "plasmodium falciparum assays",
            ),
            expected_with_octo_integration="black_box",
        ),
    ]
    return comparison_suite_to_dict(
        evaluate_comparison_suite(
            "biomedical_with_vs_without_octo",
            with_octo_model=with_octo,
            without_octo_model=without_octo,
            cases=cases,
        )
    )


if __name__ == "__main__":
    result = {
        "hello_world": run_hello_world_comparison(),
        "biomedical": run_biomedical_comparison(),
    }
    print(json.dumps(result, indent=2))
