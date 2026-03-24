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

from bender import build_pagila_fixture_snapshot
from implementations.spider import SpiderLiteBenchmarkAdapter, SpiderLiteTaskLoader, SpiderLiteWorkspace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", help="Path to a Spider Lite-style JSON or JSONL task file.")
    parser.add_argument(
        "--spider2-root",
        help="Path to an official Spider2 checkout. If set, the demo will load spider2-lite.jsonl automatically.",
    )
    parser.add_argument(
        "--use-oracle-tables",
        action="store_true",
        help="If available in the Spider2 checkout, attach released oracle tables for analysis mode.",
    )
    parser.add_argument(
        "--snapshot-manifest",
        help="JSON manifest mapping Spider Lite db_id values to SQL snapshot JSON files.",
    )
    args = parser.parse_args()

    snapshot_registry = {"pagila_fixture": build_pagila_fixture_snapshot()}
    if args.spider2_root:
        workspace = SpiderLiteWorkspace(args.spider2_root)
        if args.tasks:
            tasks = SpiderLiteTaskLoader().load(args.tasks)
        else:
            tasks = workspace.load_tasks()
        if args.use_oracle_tables:
            tasks = workspace.attach_oracle_tables(tasks)
        if args.snapshot_manifest:
            snapshot_registry.update(workspace.load_snapshot_manifest(args.snapshot_manifest))
    elif args.tasks:
        tasks = SpiderLiteTaskLoader().load(args.tasks)
    else:
        raise SystemExit("Provide either --tasks or --spider2-root.")

    adapter = SpiderLiteBenchmarkAdapter(
        snapshots_by_db=snapshot_registry,
        top_k=8,
    )

    results = []
    for task in tasks:
        if task.db_id not in snapshot_registry:
            continue
        results.append(adapter.run_task(task))

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
