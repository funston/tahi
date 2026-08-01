#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from octo import SpiderLiteWorkspace, snapshot_to_world_model
from octo.spider_lite import enrich_world_with_spider_sqlite_metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", required=True)
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--enrich-sqlite-metadata",
        action="store_true",
        help="Attach Spider SQLite metadata documents such as DDL.csv and per-table JSON summaries.",
    )
    args = parser.parse_args()

    workspace = SpiderLiteWorkspace(args.spider2_root)
    snapshots = workspace.load_snapshot_manifest(args.snapshot_manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index = {"worlds": {}}
    for db_id, snapshot in snapshots.items():
        world = snapshot_to_world_model(snapshot)
        if args.enrich_sqlite_metadata:
            try:
                metadata_documents = workspace.load_sqlite_metadata_documents(db_id)
            except FileNotFoundError:
                metadata_documents = {}
            if metadata_documents:
                world = enrich_world_with_spider_sqlite_metadata(
                    world,
                    db_id=db_id,
                    metadata_documents=metadata_documents,
                )
        output_path = output_dir / f"{db_id}.world.json"
        world.save_json(output_path)
        index["worlds"][db_id] = str(output_path.relative_to(workspace.repo_root))

    index_path = output_dir / "world_cache_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(str(index_path))


if __name__ == "__main__":
    main()
