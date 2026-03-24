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

from implementations.spider import (
    SpiderLiteSQLBenchmarkAdapter,
    SpiderLiteTaskLoader,
    SpiderLiteWorkspace,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", required=True)
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument(
        "--world-cache-index",
        help="Optional world cache index JSON for prebuilt BENDER worlds.",
    )
    parser.add_argument(
        "--tasks",
        help="Optional JSON/JSONL task file. Defaults to official spider2-lite.jsonl.",
    )
    parser.add_argument(
        "--use-oracle-tables",
        action="store_true",
        help="Attach released oracle tables if available.",
    )
    parser.add_argument(
        "--db",
        action="append",
        dest="db_ids",
        help="Restrict evaluation to specific db_id values.",
    )
    parser.add_argument("--max-repairs", type=int, default=2)
    args = parser.parse_args()

    workspace = SpiderLiteWorkspace(args.spider2_root)
    tasks = SpiderLiteTaskLoader().load(args.tasks) if args.tasks else workspace.load_tasks()
    if args.use_oracle_tables:
        tasks = workspace.attach_oracle_tables(tasks)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]

    snapshots = workspace.load_snapshot_manifest(args.snapshot_manifest)
    worlds = (
        workspace.load_world_cache_index(args.world_cache_index)
        if args.world_cache_index
        else None
    )
    sqlite_paths: dict[str, str] = {}
    for db_id in snapshots:
        try:
            sqlite_paths[db_id] = str(workspace.resolve_local_sqlite_db(db_id))
        except FileNotFoundError:
            continue

    adapter = SpiderLiteSQLBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        sqlite_db_paths_by_db=sqlite_paths,
        top_k=8,
        max_repairs=args.max_repairs,
    )
    result = adapter.evaluate_tasks(tasks, workspace=workspace)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
