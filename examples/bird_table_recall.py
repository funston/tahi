"""BIRD validation table-recall evaluation for OCTO.

This script evaluates OCTO's SQL schema coprocessor on the real BIRD dev set
(1,534 questions across 11 SQLite databases). It parses the gold SQL to obtain
the relevant tables, runs the coprocessor, and reports table recall.

Run:
    python examples/bird_table_recall.py
    python examples/bird_table_recall.py --db-id financial
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pyarrow.ipc as ipc
import sqlglot

from implementations.spider.spider import SpiderSchemaCoprocessor
from implementations.spider.spider_lite import SpiderLiteTask, SpiderLiteTaskLoader
from implementations.spider.spider_lite import SpiderLiteSQLiteDatabaseLoader
from octo.database import SQLSchemaSnapshot, snapshot_to_world_model


BIRD_ARROW = (
    ROOT
    / ".local"
    / "bird_hf"
    / "hf_datasets"
    / "Sudnya___bird-sql"
    / "default"
    / "0.0.0"
    / "7877a1bfee6b3794f5026b1f00fcc4dd43e529be"
    / "bird-sql-validation.arrow"
)
BIRD_DB_ROOT = ROOT / ".local" / "bird_hf" / "dev" / "dev_databases"


def load_bird_tasks() -> list[SpiderLiteTask]:
    with open(BIRD_ARROW, "rb") as handle:
        reader = ipc.open_stream(handle)
        table = reader.read_all()

    tasks: list[SpiderLiteTask] = []
    for row in table.to_pylist():
        record = {
            "instance_id": str(row["question_id"]),
            "db": str(row["db_id"]),
            "db_id": str(row["db_id"]),
            "question": str(row["question"]),
            "evidence": str(row["evidence"] or ""),
            "gold_sql": str(row["SQL"] or ""),
        }
        tasks.append(SpiderLiteTask.from_record(record))
    return tasks


def gold_tables_from_sql(sql: str) -> list[str]:
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except Exception:
        try:
            parsed = sqlglot.parse_one(sql, dialect="sqlite")
        except Exception:
            return []
    if parsed is None:
        return []
    return sorted({table.name for table in parsed.find_all(sqlglot.exp.Table)})


def attach_gold_tables(tasks: list[SpiderLiteTask]) -> list[SpiderLiteTask]:
    enriched: list[SpiderLiteTask] = []
    for task in tasks:
        tables = gold_tables_from_sql(task.gold_sql)
        enriched.append(
            SpiderLiteTask(
                task_id=task.task_id,
                db_id=task.db_id,
                question=task.question,
                dialect=task.dialect,
                evidence=task.evidence,
                gold_sql=task.gold_sql,
                gold_tables=tables,
                external_knowledge_files=list(task.external_knowledge_files),
                raw_record=dict(task.raw_record),
            )
        )
    return enriched


def build_db_assets(
    db_ids: set[str],
) -> tuple[dict[str, SQLSchemaSnapshot], dict[str, Any]]:
    loader = SpiderLiteSQLiteDatabaseLoader()
    snapshots: dict[str, SQLSchemaSnapshot] = {}
    worlds: dict[str, Any] = {}
    for db_id in sorted(db_ids):
        db_path = BIRD_DB_ROOT / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            print(f"Warning: database not found for {db_id}")
            continue
        snapshot = loader.load(db_path, db_id=db_id, sample_limit=3)
        world_model = snapshot_to_world_model(snapshot)
        snapshots[db_id] = snapshot
        worlds[db_id] = world_model
    return snapshots, worlds


def evaluate(
    tasks: list[SpiderLiteTask],
    snapshots: dict[str, SQLSchemaSnapshot],
    worlds: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    per_task: list[dict[str, Any]] = []
    per_db: dict[str, dict[str, Any]] = {}
    total_with_gold = 0
    total_recall = 0.0

    for task in tasks:
        if task.db_id not in snapshots:
            continue
        snapshot = snapshots[task.db_id]
        world_model = worlds[task.db_id]
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"bird:{task.db_id}",
            top_k=top_k,
            world_model=world_model,
        )
        result = coprocessor.ask(task.question, trace=False)
        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])

        recall = None
        if task.gold_tables:
            normalized_gold = {t.lower() for t in task.gold_tables}
            normalized_predicted = {t.lower().split(".")[-1] for t in candidate_tables}
            matched = normalized_gold & normalized_predicted
            recall = len(matched) / max(1, len(normalized_gold))

        per_task.append(
            {
                "task_id": task.task_id,
                "db_id": task.db_id,
                "question": task.question,
                "gold_tables": task.gold_tables,
                "candidate_tables": candidate_tables,
                "table_recall": recall,
            }
        )

        bucket = per_db.setdefault(
            task.db_id,
            {
                "db_id": task.db_id,
                "tasks": 0,
                "tasks_with_gold_tables": 0,
                "_total": 0.0,
            },
        )
        bucket["tasks"] += 1
        if recall is not None:
            bucket["tasks_with_gold_tables"] += 1
            total_with_gold += 1
            total_recall += recall
            bucket["_total"] += recall

    for bucket in per_db.values():
        if bucket["tasks_with_gold_tables"]:
            bucket["average_table_recall"] = (
                bucket["_total"] / bucket["tasks_with_gold_tables"]
            )
        else:
            bucket["average_table_recall"] = None
        bucket.pop("_total", None)

    return {
        "tasks_evaluated": len(per_task),
        "tasks_with_gold_tables": total_with_gold,
        "average_table_recall": total_recall / total_with_gold
        if total_with_gold
        else None,
        "per_db": sorted(per_db.values(), key=lambda item: item["db_id"]),
        "tasks": per_task,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BIRD dev table-recall evaluation for OCTO"
    )
    parser.add_argument(
        "--db-id",
        type=str,
        default=None,
        help="If set, evaluate only this database",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Number of candidate tables returned",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file for per-task results",
    )
    args = parser.parse_args()

    if not BIRD_ARROW.exists():
        raise FileNotFoundError(f"BIRD dataset not found: {BIRD_ARROW}")

    tasks = attach_gold_tables(load_bird_tasks())
    if args.db_id:
        tasks = [t for t in tasks if t.db_id == args.db_id]

    db_ids = {task.db_id for task in tasks}
    snapshots, worlds = build_db_assets(db_ids)

    results = evaluate(tasks, snapshots, worlds, args.top_k)

    print(f"BIRD dev — {results['tasks_evaluated']} tasks evaluated")
    print(f"Tasks with gold tables: {results['tasks_with_gold_tables']}")
    avg = results["average_table_recall"]
    print(
        f"Average table recall @ top-{args.top_k}: {avg:.3f}"
        if avg is not None
        else "Average table recall: N/A"
    )
    print()
    print("Per-database breakdown:")
    for bucket in results["per_db"]:
        recall = bucket["average_table_recall"]
        recall_str = f"{recall:.3f}" if recall is not None else "N/A"
        print(
            f" {bucket['db_id']:<25} "
            f"tasks={bucket['tasks']:>4} "
            f"recall={recall_str}"
        )

    if args.output:
        args.output.write_text(
            json.dumps(results, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nDetailed results written to {args.output}")


if __name__ == "__main__":
    main()
