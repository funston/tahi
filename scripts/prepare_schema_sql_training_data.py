"""
Prepare training data for a SchemaSQLCoprocessor model.

This script loads BIRD training data, builds grounded schema packets using OCTO's
existing SQL schema coprocessor, and emits a JSONL file suitable for instruction
fine-tuning.

Each line in the output JSONL has the form:
    {"instruction": "...", "input": "...", "output": "..."}

Usage:
    python scripts/prepare_schema_sql_training_data.py \
        --output data/schema_sql_train.jsonl \
        --split train \
        --hf-repo-id Sudnya/bird-sql \
        --hf-cache-dir .local/bird_hf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from octo.database import snapshot_to_world_model
from implementations.bird import (
    BirdExecutionPacket,
    BirdHFWorkspace,
    BirdSQLiteDatabaseLoader,
    BirdTask,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)
from implementations.sql import SQLSchemaCoprocessor


SYSTEM_PROMPT = (
    "You are writing SQLite SQL for the BIRD benchmark.\n"
    "Return only SQL.\n"
    "Use only the tables shown below when possible.\n"
)


def build_prompt(packet: BirdExecutionPacket) -> str:
    """Render a grounded execution packet as the model input."""
    allowed = {table.name.lower() for table in packet.snapshot.tables}
    if packet.candidate_tables:
        allowed = {name.lower() for name in packet.candidate_tables}

    table_blocks: list[str] = []
    for table in packet.snapshot.tables:
        if table.name.lower() not in allowed:
            continue
        columns = ", ".join(f'{column.name} {column.data_type}' for column in table.columns)
        table_blocks.append(f"TABLE {table.name} ({columns})")
    schema_text = "\n".join(table_blocks) if table_blocks else "(no filtered tables available)"

    evidence_text = ""
    if packet.include_evidence and packet.evidence.strip():
        evidence_text = f"\nEvidence: {packet.evidence.strip()}"

    return (
        f"Database: {packet.db_id}\n"
        f"Schema:\n{schema_text}\n\n"
        f"Question: {packet.question}{evidence_text}"
    )


def prepare_task(
    task: BirdTask,
    snapshot,
    include_evidence: bool = False,
) -> dict[str, str] | None:
    """Create one training example from a BIRD task."""
    if not task.gold_sql or not task.gold_sql.strip():
        return None

    packet = BirdExecutionPacket(
        task_id=task.task_id,
        db_id=task.db_id,
        question=task.question,
        evidence=task.evidence,
        candidate_tables=[],
        snapshot=snapshot,
        include_evidence=include_evidence,
    )

    # Optionally ground with OCTO to get filtered tables.
    # For training data, using the full schema is often more robust.
    # Uncomment the next block to use OCTO grounding instead.
    # world_model = snapshot_to_world_model(snapshot)
    # coprocessor = SQLSchemaCoprocessor.from_snapshot(
    #     snapshot,
    #     model_name=f"bird:{task.db_id}",
    #     world_model=world_model,
    #     top_k=8,
    # )
    # result = coprocessor.ask(task.question, trace=False)
    # packet.candidate_tables = result.get("constraints", {}).get("candidate_tables", [])

    return {
        "instruction": SYSTEM_PROMPT,
        "input": build_prompt(packet),
        "output": task.gold_sql.strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument("--split", default="train", choices=["train", "dev"])
    parser.add_argument("--hf-repo-id", default="Sudnya/bird-sql")
    parser.add_argument("--hf-cache-dir", default=".local/bird_hf")
    parser.add_argument("--bird-root", default="", help="Optional local BIRD root")
    parser.add_argument("--include-evidence", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limit examples (0 = all)")
    args = parser.parse_args()

    if args.bird_root:
        workspace = BirdWorkspace(args.bird_root)
    else:
        workspace = BirdHFWorkspace(repo_id=args.hf_repo_id, cache_dir=args.hf_cache_dir)
        workspace.ensure_database_cache(split=args.split)

    tasks = workspace.load_tasks(split=args.split)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    loader = BirdSQLiteDatabaseLoader()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            db_path = workspace.resolve_local_sqlite_db(task.db_id, split=args.split)
            if not db_path.exists():
                skipped += 1
                continue
            snapshot = loader.load(db_path, db_id=task.db_id)
            example = prepare_task(task, snapshot, include_evidence=args.include_evidence)
            if example is None:
                skipped += 1
                continue
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")
            written += 1
            if written % 100 == 0:
                print(f"Prepared {written} examples...")

    print(f"Done. Wrote {written} examples to {output_path}. Skipped {skipped}.")


if __name__ == "__main__":
    main()
