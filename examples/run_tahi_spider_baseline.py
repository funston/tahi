import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

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
    SpiderSnowflakeMetadataLoader,
    SpiderSnowSQLBenchmarkAdapter,
    SpiderSnowWorkspace,
)


def _load_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks", [])
    return {str(row["task_id"]): row for row in tasks if row.get("task_id")}


def _save_results(path: Path, *, benchmark: str, tasks: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmark": benchmark,
                "tasks": tasks,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def _failed_task_result(task: Any, exc: Exception) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "db_id": task.db_id,
        "question": task.question,
        "matched_gold": None,
        "execution_success": False,
        "execution_error": str(exc),
        "error": str(exc),
    }


def _supplement_spider_snow_snapshots(
    workspace: SpiderSnowWorkspace,
    tasks: list[Any],
    snapshots: dict[str, Any],
) -> dict[str, Any]:
    loader = SpiderSnowflakeMetadataLoader()
    completed = dict(snapshots)
    for db_id in sorted({task.db_id for task in tasks}):
        if db_id in completed:
            continue
        try:
            metadata_dir = workspace.resolve_database_metadata_dir(db_id)
        except FileNotFoundError:
            continue
        completed[db_id] = loader.load(metadata_dir, db_id=db_id)
    return completed


def _run_spider_lite_sql(args: argparse.Namespace, cache_path: Path) -> None:
    workspace = SpiderLiteWorkspace(args.spider2_root)
    tasks = SpiderLiteTaskLoader().load(args.tasks) if args.tasks else workspace.load_tasks()
    if args.use_oracle_tables:
        tasks = workspace.attach_oracle_tables(tasks)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]

    snapshots = workspace.load_snapshot_manifest(args.snapshot_manifest)
    worlds = workspace.load_world_cache_index(args.world_cache_index) if args.world_cache_index else None
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
        top_k=args.top_k,
        max_repairs=args.max_repairs,
    )

    existing = _load_existing_results(cache_path) if args.resume else {}
    for task in tasks:
        if args.resume and task.task_id in existing:
            continue
        try:
            result = adapter.run_task(task, workspace=workspace)
        except Exception as exc:  # noqa: BLE001
            result = _failed_task_result(task, exc)
        existing[task.task_id] = result
        _save_results(
            cache_path,
            benchmark="spider-lite-sql",
            tasks=sorted(existing.values(), key=lambda row: str(row.get("task_id", ""))),
        )


def _run_spider_snow_sql(args: argparse.Namespace, cache_path: Path) -> None:
    workspace = SpiderSnowWorkspace(args.spider2_root)
    tasks = workspace.attach_oracle_tables(workspace.load_tasks())
    if args.task_ids:
        allowed_task_ids = set(args.task_ids)
        tasks = [task for task in tasks if task.task_id in allowed_task_ids]
    if args.db_ids:
        allowed_db_ids = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed_db_ids]

    snapshots = workspace.load_snapshot_manifest(args.snapshot_manifest)
    snapshots = _supplement_spider_snow_snapshots(workspace, tasks, snapshots)
    worlds = workspace.load_world_cache_index(args.world_cache_index)
    adapter = SpiderSnowSQLBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        credentials_path=args.credentials_path,
        top_k=args.top_k,
    )

    existing = _load_existing_results(cache_path) if args.resume else {}
    for task in tasks:
        if args.resume and task.task_id in existing:
            continue
        try:
            result = adapter.run_task(task, workspace=workspace)
        except Exception as exc:  # noqa: BLE001
            result = _failed_task_result(task, exc)
        existing[task.task_id] = result
        _save_results(
            cache_path,
            benchmark="spider-snow-sql",
            tasks=sorted(existing.values(), key=lambda row: str(row.get("task_id", ""))),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=["spider-lite-sql", "spider-snow-sql"], required=True)
    parser.add_argument("--spider2-root", default="/Users/richiek/work/Spider2")
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument("--world-cache-index")
    parser.add_argument("--credentials-path", default="/Users/richiek/work/tahi/snowflake_creds.json")
    parser.add_argument("--tasks")
    parser.add_argument("--use-oracle-tables", action="store_true")
    parser.add_argument("--db", action="append", dest="db_ids")
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--max-repairs", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--cache-path", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    cache_path = Path(args.cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if args.benchmark == "spider-lite-sql":
        _run_spider_lite_sql(args, cache_path)
        return
    _run_spider_snow_sql(args, cache_path)


if __name__ == "__main__":
    main()
