"""Real-world Spider 2.0 Lite table-recall evaluation for TAHI.

This script evaluates TAHI's SQL schema coprocessor on the 135 SQLite
(local*) tasks from the Spider 2.0 Lite benchmark. It reports table
recall: the fraction of gold-relevant tables that appear in the
coprocessor's top-k candidate table list. No LLM calls are made; the
coprocessor runs entirely from the schema world model.

Expected usage:
 python examples/spider_lite_demo.py
 python examples/spider_lite_demo.py --output results.json

The dataset is assumed to live at:
 /Users/richiek/work/Spider2/spider2-lite
Gold-relevant tables are read from:
 /Users/richiek/work/Spider2/methods/gold-tables/spider2-lite-gold-tables.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow the script to run from the repo root without a package install.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from implementations.spider.spider_lite import (
    SpiderLiteSQLiteMetadataLoader,
    SpiderLiteTask,
    SpiderLiteTaskLoader,
    SpiderLiteWorkspace,
    SpiderLiteBenchmarkAdapter,
    enrich_world_with_spider_sqlite_metadata,
)
from tahi.database import snapshot_to_world_model
from tahi.world_state import WorldModel


def load_local_tasks_with_gold(
    tasks_path: Path,
    gold_tables_path: Path,
) -> list[SpiderLiteTask]:
    """Load the local Spider 2.0 Lite tasks and attach oracle gold tables."""
    loader = SpiderLiteTaskLoader()
    tasks = [t for t in loader.load(tasks_path) if str(t.task_id).startswith("local")]

    if not gold_tables_path.exists():
        raise FileNotFoundError(f"Gold-tables file not found: {gold_tables_path}")

    oracle_map = {
        t.task_id: list(t.gold_tables)
        for t in loader.load(gold_tables_path)
        if t.gold_tables
    }

    enriched: list[SpiderLiteTask] = []
    for task in tasks:
        if task.gold_tables:
            enriched.append(task)
            continue
        tables = oracle_map.get(task.task_id, [])
        enriched.append(
            SpiderLiteTask(
                task_id=task.task_id,
                db_id=task.db_id,
                question=task.question,
                dialect=task.dialect,
                evidence=task.evidence,
                gold_sql=task.gold_sql,
                gold_tables=list(tables),
                external_knowledge_files=list(task.external_knowledge_files),
                raw_record=dict(task.raw_record),
            )
        )
    return enriched


def build_db_assets(
    workspace: SpiderLiteWorkspace,
    db_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build SQLSchemaSnapshot + WorldModel for each database used by the tasks."""
    snapshots: dict[str, Any] = {}
    worlds: dict[str, Any] = {}
    metadata_loader = SpiderLiteSQLiteMetadataLoader()

    for db_id in sorted(db_ids):
        metadata_dir = workspace.resolve_sqlite_metadata_dir(db_id)
        snapshot = metadata_loader.load(metadata_dir, db_id=db_id)
        world_model = snapshot_to_world_model(snapshot)
        metadata_documents = workspace.load_sqlite_metadata_documents(db_id)
        world_model = enrich_world_with_spider_sqlite_metadata(
            world_model,
            db_id=db_id,
            metadata_documents=metadata_documents,
        )
        snapshots[db_id] = snapshot
        worlds[db_id] = world_model

    return snapshots, worlds


def main() -> None:
    parser = argparse.ArgumentParser(description="Spider 2.0 Lite TAHI table-recall demo")
    parser.add_argument(
        "--spider2-root",
        type=Path,
        default=Path("/Users/richiek/work/Spider2"),
        help="Root directory of the Spider2 repository (parent of spider2-lite/)",
    )
    parser.add_argument(
        "--gold-tables",
        type=Path,
        default=None,
        help="Path to spider2-lite-gold-tables.jsonl (default: <spider2-root>/methods/gold-tables/spider2-lite-gold-tables.jsonl)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Number of candidate tables the coprocessor may return",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If set, evaluate only the first N local tasks (for quick smoke tests)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file to write detailed per-task results",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Also evaluate a keyword/heuristic-only baseline (no world model)",
    )
    args = parser.parse_args()

    tasks_path = args.spider2_root / "spider2-lite" / "spider2-lite.jsonl"
    if not tasks_path.exists():
        raise FileNotFoundError(f"Tasks file not found: {tasks_path}")

    gold_tables_path = args.gold_tables or (
        args.spider2_root / "methods" / "gold-tables" / "spider2-lite-gold-tables.jsonl"
    )

    tasks = load_local_tasks_with_gold(tasks_path, gold_tables_path)
    if args.limit is not None:
        tasks = tasks[: args.limit]

    db_ids = {task.db_id for task in tasks}
    workspace = SpiderLiteWorkspace(args.spider2_root)
    snapshots, worlds = build_db_assets(workspace, db_ids)

    adapter = SpiderLiteBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        top_k=args.top_k,
    )

    results = adapter.evaluate_tasks(tasks)

    baseline_results = None
    if args.compare_baseline:
        empty_worlds = {db_id: WorldModel() for db_id in snapshots}
        baseline_adapter = SpiderLiteBenchmarkAdapter(
            snapshots_by_db=snapshots,
            worlds_by_db=empty_worlds,
            top_k=args.top_k,
        )
        baseline_results = baseline_adapter.evaluate_tasks(tasks)

    # Print a concise, investor-friendly summary.
    print(f"Spider 2.0 Lite (local SQLite) — {results['tasks_evaluated']} tasks evaluated")
    print(f"Tasks with gold tables: {results['tasks_with_gold_tables']}")
    avg_recall = results["average_table_recall"]
    if avg_recall is not None:
        print(f"Average table recall @ top-{args.top_k}: {avg_recall:.3f}")
    else:
        print("Average table recall: N/A (no gold tables)")

    if baseline_results is not None:
        baseline_avg = baseline_results["average_table_recall"]
        if baseline_avg is not None and avg_recall is not None:
            delta = avg_recall - baseline_avg
            print(f"Keyword/heuristic-only baseline recall: {baseline_avg:.3f} (delta: +{delta:.3f})")
        else:
            print("Keyword/heuristic-only baseline recall: N/A")

    print()
    print("Per-database breakdown:")
    for bucket in results["per_db"]:
        recall = bucket["average_table_recall"]
        recall_str = f"{recall:.3f}" if recall is not None else "N/A"
        baseline_str = ""
        if baseline_results is not None:
            baseline_bucket = next(
                (b for b in baseline_results["per_db"] if b["db_id"] == bucket["db_id"]),
                None,
            )
            if baseline_bucket and baseline_bucket["average_table_recall"] is not None:
                baseline_str = f" baseline={baseline_bucket['average_table_recall']:.3f}"
        print(
            f" {bucket['db_id']:<35} "
            f"tasks={bucket['tasks']:>3} "
            f"recall={recall_str}{baseline_str}"
        )

    if args.output:
        payload = {
            "tahi": results,
            "baseline": baseline_results,
            "top_k": args.top_k,
        }
        args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nDetailed results written to {args.output}")


if __name__ == "__main__":
    main()
