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

from bender import snapshot_to_world_model
from implementations.bird import (
    BirdBenchmarkAdapter,
    BirdSQLiteDatabaseLoader,
    BirdTaskLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-root", help="Path to a local BIRD checkout.")
    parser.add_argument("--tasks", help="Optional explicit BIRD task file.")
    parser.add_argument("--split", default="mini_dev")
    parser.add_argument("--db", action="append", dest="db_ids")
    args = parser.parse_args()

    if not args.bird_root:
        raise SystemExit("Provide --bird-root.")

    workspace = BirdWorkspace(args.bird_root)
    if args.tasks:
        tasks = BirdTaskLoader().load(args.tasks)
    else:
        tasks = workspace.load_tasks(split=args.split)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]

    db_loader = BirdSQLiteDatabaseLoader()
    snapshots = {}
    worlds = {}
    for db_id in sorted({task.db_id for task in tasks}):
        snapshot = db_loader.load(workspace.resolve_local_sqlite_db(db_id, split=args.split), db_id=db_id)
        snapshots[db_id] = snapshot
        world = snapshot_to_world_model(snapshot)
        worlds[db_id] = enrich_world_with_bird_metadata(
            world,
            db_id=db_id,
            metadata_documents=workspace.load_database_documents(db_id, split=args.split),
        )

    adapter = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=worlds,
        top_k=8,
    )
    results = [adapter.run_task(task) for task in tasks]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
