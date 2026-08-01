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

from octo import snapshot_to_world_model
from implementations.bird import (
    BirdBenchmarkAdapter,
    BirdSQLiteDatabaseLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-root", required=True)
    parser.add_argument("--split", default="mini_dev")
    parser.add_argument("--db", action="append", dest="db_ids")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    workspace = BirdWorkspace(args.bird_root)
    tasks = workspace.load_tasks(split=args.split)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]

    loader = BirdSQLiteDatabaseLoader()
    snapshots = {}
    worlds = {}
    for db_id in sorted({task.db_id for task in tasks}):
        snapshot = loader.load(workspace.resolve_local_sqlite_db(db_id, split=args.split), db_id=db_id)
        snapshots[db_id] = snapshot
        worlds[db_id] = enrich_world_with_bird_metadata(
            snapshot_to_world_model(snapshot),
            db_id=db_id,
            metadata_documents=workspace.load_database_documents(db_id, split=args.split),
        )

    adapter = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        top_k=8,
    )
    summary = adapter.evaluate_tasks(tasks)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "summary": summary}, indent=2, default=str))


if __name__ == "__main__":
    main()
