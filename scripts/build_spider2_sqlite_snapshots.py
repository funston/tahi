#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bender import (
    SpiderLiteSQLiteDatabaseLoader,
    SpiderLiteSQLiteMetadataLoader,
    SpiderLiteWorkspace,
)


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
        "foreign_keys": [
            {
                "source_schema": fk.source_schema,
                "source_table": fk.source_table,
                "source_column": fk.source_column,
                "target_schema": fk.target_schema,
                "target_table": fk.target_table,
                "target_column": fk.target_column,
                "constraint_name": fk.constraint_name,
            }
            for fk in snapshot.foreign_keys
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--db",
        action="append",
        dest="db_ids",
        help="Spider Lite db_id to export. Repeat for multiple databases. Default: export all SQLite metadata directories.",
    )
    parser.add_argument(
        "--prefer-metadata",
        action="store_true",
        help="Force snapshot generation from Spider Lite metadata even if local .sqlite files are present.",
    )
    args = parser.parse_args()

    workspace = SpiderLiteWorkspace(args.spider2_root)
    metadata_loader = SpiderLiteSQLiteMetadataLoader()
    sqlite_loader = SpiderLiteSQLiteDatabaseLoader()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_ids = args.db_ids or workspace.list_sqlite_metadata_databases()
    manifest = {"snapshots": {}}

    for db_id in db_ids:
        source = "metadata"
        if not args.prefer_metadata:
            try:
                db_path = workspace.resolve_local_sqlite_db(db_id)
            except FileNotFoundError:
                db_path = None
            if db_path is not None:
                snapshot = sqlite_loader.load(db_path, db_id=db_id)
                source = "sqlite"
            else:
                metadata_dir = workspace.resolve_sqlite_metadata_dir(db_id)
                snapshot = metadata_loader.load(metadata_dir, db_id=db_id)
        else:
            metadata_dir = workspace.resolve_sqlite_metadata_dir(db_id)
            snapshot = metadata_loader.load(metadata_dir, db_id=db_id)
        output_path = output_dir / f"{db_id}.json"
        output_path.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2), encoding="utf-8")
        manifest["snapshots"][db_id] = str(output_path.relative_to(workspace.repo_root))
        manifest.setdefault("sources", {})[db_id] = source

    manifest_path = output_dir / "snapshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(str(manifest_path))


if __name__ == "__main__":
    main()
