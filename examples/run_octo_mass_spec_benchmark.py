import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.mass_spec import (  # noqa: E402
    MassSpecABBenchmarkRunner,
    MassSpecInterpretationAdapter,
    MassSpecWorkspace,
    build_mass_spec_world_model,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mass-spec-root",
        default=os.path.join(ROOT, "implementations", "mass_spec"),
        help="Path to the mass_spec implementation root.",
    )
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    workspace = MassSpecWorkspace(args.mass_spec_root)
    knowledge_base = workspace.load_knowledge_base()
    cases = workspace.load_cases()
    if args.case_ids:
        allowed = set(args.case_ids)
        cases = [case for case in cases if case.case_id in allowed]
    report = MassSpecABBenchmarkRunner(
        adapter=MassSpecInterpretationAdapter(build_mass_spec_world_model(knowledge_base))
    ).run(cases)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "markdown_summary": report["markdown_summary"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
