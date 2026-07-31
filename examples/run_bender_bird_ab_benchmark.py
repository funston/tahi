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

from bender import snapshot_to_world_model
from implementations.bird import (  # noqa: E402
    BirdABBenchmarkRunner,
    BirdBenchmarkAdapter,
    BirdHFWorkspace,
    BirdSQLiteDatabaseLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["local", "huggingface"], default="local")
    parser.add_argument("--bird-root", default="")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--hf-repo-id", default="Sudnya/bird-sql")
    parser.add_argument("--hf-cache-dir", default=".local/bird_hf")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--db", action="append", dest="db_ids")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.source == "local":
        if not args.bird_root:
            raise SystemExit("--bird-root is required when --source local")
        workspace = BirdWorkspace(args.bird_root)
    else:
        workspace = BirdHFWorkspace(
            repo_id=args.hf_repo_id,
            cache_dir=args.hf_cache_dir,
        )
        workspace.ensure_database_cache(split=args.split, force_download=args.force_download)

    tasks = workspace.load_tasks(split=args.split)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]
    if args.limit > 0:
        tasks = tasks[: args.limit]

    loader = BirdSQLiteDatabaseLoader()
    snapshots = {}
    baseline_worlds = {}
    bender_worlds = {}
    for db_id in sorted({task.db_id for task in tasks}):
        snapshot = loader.load(workspace.resolve_local_sqlite_db(db_id, split=args.split), db_id=db_id)
        snapshots[db_id] = snapshot
        baseline_worlds[db_id] = snapshot_to_world_model(snapshot)
        bender_worlds[db_id] = enrich_world_with_bird_metadata(
            snapshot_to_world_model(snapshot),
            db_id=db_id,
            metadata_documents=workspace.load_database_documents(db_id, split=args.split),
        )

    report = BirdABBenchmarkRunner(
        baseline_adapter=BirdBenchmarkAdapter(
            snapshots_by_db=snapshots,
            worlds_by_db=baseline_worlds,
            top_k=8,
        ),
        bender_adapter=BirdBenchmarkAdapter(
            snapshots_by_db=snapshots,
            worlds_by_db=bender_worlds,
            top_k=8,
        ),
        evidence_adapter=BirdBenchmarkAdapter(
            snapshots_by_db=snapshots,
            worlds_by_db=bender_worlds,
            top_k=8,
            include_evidence=True,
        ),
    ).run(tasks)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "markdown_summary": report["markdown_summary"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
