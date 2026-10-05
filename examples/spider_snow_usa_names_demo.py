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

from tahi import snapshot_to_world_model
from implementations.spider import (
    SpiderSnowSQLBenchmarkAdapter,
    SpiderSnowWorkspace,
    SpiderSnowflakeMetadataLoader,
    enrich_world_with_spider_snow_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", default="/Users/richiek/work/Spider2")
    parser.add_argument("--task-id", default="sf_bq286")
    parser.add_argument("--credentials-path", default="/Users/richiek/work/tahi/snowflake_creds.json")
    args = parser.parse_args()

    workspace = SpiderSnowWorkspace(args.spider2_root)
    tasks = workspace.attach_oracle_tables(workspace.load_tasks())
    task = next(task for task in tasks if task.task_id == args.task_id)

    loader = SpiderSnowflakeMetadataLoader()
    snapshot = loader.load(workspace.resolve_database_metadata_dir(task.db_id), db_id=task.db_id)
    world = snapshot_to_world_model(snapshot)
    world = enrich_world_with_spider_snow_metadata(
        world,
        db_id=task.db_id,
        metadata_documents=workspace.load_metadata_documents(task.db_id),
    )

    adapter = SpiderSnowSQLBenchmarkAdapter(
        snapshots_by_db={task.db_id: snapshot},
        worlds_by_db={task.db_id: world},
        credentials_path=args.credentials_path,
    )
    result = adapter.run_task(task, workspace=workspace)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
