import argparse
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.mass_spec import (  # noqa: E402
    MassSpecAnalyteProfileRequest,
    MassSpecInterpretationAdapter,
    MassSpecWorkspace,
    build_mass_spec_world_model,
    render_mass_spec_rag_baseline,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mass-spec-root",
        default=os.path.join(ROOT, "implementations", "mass_spec"),
        help="Path to the mass_spec implementation root.",
    )
    parser.add_argument(
        "--mode",
        choices=("spectrum", "analyte-profile", "rag-baseline"),
        default="spectrum",
        help="Which demo flow to run.",
    )
    parser.add_argument("--case-id", default="demo_glucose_sodium", help="Spectrum case id.")
    parser.add_argument("--analyte", default="Caffeine", help="Analyte name for profile mode.")
    parser.add_argument("--polarity", default="positive", help="Polarity filter for analyte profile.")
    args = parser.parse_args()

    workspace = MassSpecWorkspace(args.mass_spec_root)
    knowledge_base = workspace.load_knowledge_base()
    world = build_mass_spec_world_model(knowledge_base)
    adapter = MassSpecInterpretationAdapter(world)

    if args.mode == "spectrum":
        case = next(candidate for candidate in workspace.load_cases() if candidate.case_id == args.case_id)
        result = adapter.run_spectrum_case(case)
    elif args.mode == "analyte-profile":
        result = adapter.run_analyte_profile(
            MassSpecAnalyteProfileRequest(
                analyte=args.analyte,
                polarity=args.polarity,
                question="Summarize likely ion forms and why they matter for this analyte.",
            )
        )
    else:
        case = next(candidate for candidate in workspace.load_cases() if candidate.case_id == args.case_id)
        result = render_mass_spec_rag_baseline(case)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
