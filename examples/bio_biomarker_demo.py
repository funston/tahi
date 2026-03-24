import json
import os
import sys
import argparse


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.bio import (  # noqa: E402
    BioInterpretationAdapter,
    BioTargetProfileRequest,
    BioWorkspace,
    build_bio_world_model,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bio-root",
        default=os.path.join(ROOT, "implementations", "bio"),
        help="Path to the bio implementation root containing data/demo_biomarker_kb.json and data/demo_cases.json.",
    )
    parser.add_argument(
        "--mode",
        choices=("biomarker", "target-profile"),
        default="biomarker",
        help="Run the biomarker interpretation flow or the target profile flow.",
    )
    parser.add_argument(
        "--case-id",
        default="demo_her2_breast",
        help="Demo case id to interpret.",
    )
    parser.add_argument(
        "--target",
        default="EGFR",
        help="Target symbol to profile when --mode target-profile is used.",
    )
    parser.add_argument(
        "--disease",
        default="NSCLC",
        help="Disease context for --mode target-profile.",
    )
    args = parser.parse_args()

    workspace = BioWorkspace(args.bio_root)
    knowledge_base = workspace.load_knowledge_base()
    world = build_bio_world_model(knowledge_base)
    adapter = BioInterpretationAdapter(world)
    if args.mode == "biomarker":
        case = next(
            candidate
            for candidate in workspace.load_cases()
            if candidate.case_id == args.case_id
        )
        result = adapter.run_case(case)
    else:
        result = adapter.run_target_profile(
            BioTargetProfileRequest(
                target=args.target,
                disease=args.disease,
                question="Summarize why this target matters in the requested disease and what evidence bridges it to therapy.",
            )
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
