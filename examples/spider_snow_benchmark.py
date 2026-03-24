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
    SpiderSnowSQLBenchmarkAdapter,
    SpiderSnowWorkspace,
)


DEFAULT_TASK_IDS = [
    "sf_bq286",    # USA_NAMES
    "sf_bq284",    # BBC
    "sf_local007", # BASEBALL
    "sf_local028", # BRAZILIAN_E_COMMERCE
    "sf_bq006",    # AUSTIN
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", default="/Users/richiek/work/Spider2")
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument("--world-cache-index", required=True)
    parser.add_argument("--credentials-path", default="/Users/richiek/work/bender/snowflake_creds.json")
    parser.add_argument(
        "--task-id",
        action="append",
        dest="task_ids",
        help="Restrict benchmark to specific Spider Snow task ids. Repeat for multiple tasks.",
    )
    args = parser.parse_args()

    workspace = SpiderSnowWorkspace(args.spider2_root)
    tasks = workspace.attach_oracle_tables(workspace.load_tasks())
    allowed = set(args.task_ids or DEFAULT_TASK_IDS)
    tasks = [task for task in tasks if task.task_id in allowed]

    snapshots = workspace.load_snapshot_manifest(args.snapshot_manifest)
    worlds = workspace.load_world_cache_index(args.world_cache_index)
    adapter = SpiderSnowSQLBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        credentials_path=args.credentials_path,
        top_k=8,
    )

    results = [adapter.run_task(task, workspace=workspace) for task in tasks]
    summary = {
        "tasks_evaluated": len(results),
        "execution_successes": sum(1 for row in results if row["execution_success"]),
        "gold_matches": sum(1 for row in results if row["matched_gold"] is True),
        "tasks": results,
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
