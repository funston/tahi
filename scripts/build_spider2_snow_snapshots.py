#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tahi import SpiderSnowflakeMetadataLoader, SpiderSnowWorkspace


def snapshot_to_dict(snapshot):
    return {
        "database_name": snapshot.database_name,
        "tables": [
            {
                "schema": table.schema,
                "name": table.name,
                "description": table.description,
                "row_estimate": table.row_estimate,
                "columns": [
                    {
                        "schema": column.schema,
                        "table": column.table,
                        "name": column.name,
                        "data_type": column.data_type,
                        "is_nullable": column.is_nullable,
                        "ordinal_position": column.ordinal_position,
                        "description": column.description,
                        "sample_values": list(column.sample_values),
                    }
                    for column in table.columns
                ],
            }
            for table in snapshot.tables
        ],
        "foreign_keys": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--db",
        action="append",
        dest="db_ids",
        help="Spider Snow db_id to export. Repeat for multiple databases.",
    )
    args = parser.parse_args()

    workspace = SpiderSnowWorkspace(args.spider2_root)
    loader = SpiderSnowflakeMetadataLoader()
    tasks = workspace.load_tasks()
    db_ids = args.db_ids or sorted({task.db_id for task in tasks})

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"snapshots": {}, "sources": {}}
    for db_id in db_ids:
        snapshot = loader.load(workspace.resolve_database_metadata_dir(db_id), db_id=db_id)
        output_path = output_dir / f"{db_id}.json"
        output_path.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2), encoding="utf-8")
        manifest["snapshots"][db_id] = str(output_path.relative_to(workspace.repo_root))
        manifest["sources"][db_id] = "snowflake_metadata"

    manifest_path = output_dir / "snapshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(str(manifest_path))


if __name__ == "__main__":
    main()
