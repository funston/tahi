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
    build_bio_knowledge_base_from_records,
    build_bio_world_model,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bio-root",
        default=os.path.join(ROOT, "implementations", "bio"),
        help="Path to the bio implementation root containing data/demo_evidence_records.jsonl.",
    )
    parser.add_argument("--target", default="BRAF", help="Target to profile after ingest.")
    parser.add_argument("--disease", default="Melanoma", help="Disease context for the target profile.")
    args = parser.parse_args()

    workspace = BioWorkspace(args.bio_root)
    records = workspace.load_evidence_records()
    knowledge_base = build_bio_knowledge_base_from_records(records)
    world = build_bio_world_model(knowledge_base)
    adapter = BioInterpretationAdapter(world)
    result = adapter.run_target_profile(
        BioTargetProfileRequest(
            target=args.target,
            disease=args.disease,
            question="Summarize why this target is relevant in the disease using the ingested evidence records.",
        )
    )
    payload = {
        "record_count": len(records),
        "entity_count": len(knowledge_base.entities),
        "relation_count": len(knowledge_base.relations),
        "source_count": len(knowledge_base.sources),
        "result": result,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
