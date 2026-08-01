"""
Build and cache all BIRD world models using FTI WorldModelStore

Pre-builds all BIRD dev world models and saves them with versioning
for 3x faster benchmark runs.

Usage:
    python scripts/build_bird_world_models.py \
        --bird-root datasets/bird/dev_20240627 \
        --store-path ~/.octo/world-models \
        --version v1.0.0
"""

import argparse
import sys
from pathlib import Path

# Add implementations to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "implementations"))

from octo import WorldModelStore, snapshot_to_world_model
from bird.bird import (
    BirdSQLiteDatabaseLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)


def main():
    parser = argparse.ArgumentParser(description="Pre-build BIRD world models")
    parser.add_argument(
        "--bird-root",
        type=str,
        default="datasets/bird/dev_20240627",
        help="Path to BIRD dataset root",
    )
    parser.add_argument(
        "--store-path",
        type=str,
        default="~/.octo/world-models",
        help="Path to WorldModelStore",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="v1.0.0",
        help="Version for world models",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="dev",
        help="BIRD split to build (dev or train)",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force rebuild even if exists",
    )

    args = parser.parse_args()

    # Initialize workspace and store
    workspace = BirdWorkspace(repo_root=args.bird_root)
    store = WorldModelStore(args.store_path, compress=True)
    loader = BirdSQLiteDatabaseLoader()

    # Get all unique database IDs from tasks
    tasks = workspace.load_tasks(split=args.split)
    db_ids = sorted({task.db_id for task in tasks})

    print("=" * 80)
    print(f"Building BIRD World Models - FTI Feature Pipeline")
    print("=" * 80)
    print(f"Source: bird-{args.split}")
    print(f"Version: {args.version}")
    print(f"Databases: {len(db_ids)}")
    print(f"Store: {args.store_path}")
    print(f"Compression: gzip")
    print("=" * 80)

    baseline_count = 0
    enriched_count = 0
    skipped_count = 0

    for i, db_id in enumerate(db_ids, 1):
        print(f"\n[{i}/{len(db_ids)}] Processing: {db_id}")

        # Check if already exists
        baseline_exists = store.exists(f"bird-{args.split}-baseline", args.version, db_id)
        enriched_exists = store.exists(f"bird-{args.split}-enriched", args.version, db_id)

        if baseline_exists and enriched_exists and not args.force_rebuild:
            print(f"  ✓ Already cached (skipping)")
            skipped_count += 1
            continue

        # Load database
        try:
            db_path = workspace.resolve_local_sqlite_db(db_id, split=args.split)
            snapshot = loader.load(db_path, db_id=db_id)
            print(f"  Loaded: {len(snapshot.tables)} tables, {len(snapshot.foreign_keys)} FKs")
        except Exception as e:
            print(f"  ✗ Failed to load database: {e}")
            continue

        # Build baseline world model (schema only)
        if not baseline_exists or args.force_rebuild:
            print(f"  Building baseline world model...")
            baseline_world = snapshot_to_world_model(snapshot)
            store.save(
                baseline_world,
                source=f"bird-{args.split}-baseline",
                version=args.version,
                model_id=db_id,
                metadata={
                    "enrichment": "none",
                    "num_tables": len(snapshot.tables),
                    "num_foreign_keys": len(snapshot.foreign_keys),
                },
            )
            baseline_count += 1
            print(f"  ✓ Saved baseline ({len(baseline_world.nodes)} nodes, {len(baseline_world.edges)} edges)")

        # Build enriched world model (schema + metadata)
        if not enriched_exists or args.force_rebuild:
            print(f"  Building enriched world model...")
            enriched_world = enrich_world_with_bird_metadata(
                snapshot_to_world_model(snapshot),
                db_id=db_id,
                metadata_documents=workspace.load_database_documents(db_id, split=args.split),
            )
            store.save(
                enriched_world,
                source=f"bird-{args.split}-enriched",
                version=args.version,
                model_id=db_id,
                metadata={
                    "enrichment": "csv_metadata",
                    "num_tables": len(snapshot.tables),
                    "num_foreign_keys": len(snapshot.foreign_keys),
                },
            )
            enriched_count += 1
            print(f"  ✓ Saved enriched ({len(enriched_world.nodes)} nodes, {len(enriched_world.edges)} edges)")

    print("\n" + "=" * 80)
    print("Build Complete")
    print("=" * 80)
    print(f"Baseline models built: {baseline_count}")
    print(f"Enriched models built: {enriched_count}")
    print(f"Skipped (already cached): {skipped_count}")
    print(f"Total databases: {len(db_ids)}")
    print("\nManifest:")
    baseline_manifest = store.get_manifest(f"bird-{args.split}-baseline", args.version)
    enriched_manifest = store.get_manifest(f"bird-{args.split}-enriched", args.version)
    if baseline_manifest:
        print(f"  Baseline: {baseline_manifest.num_nodes} max nodes, {baseline_manifest.num_edges} max edges")
    if enriched_manifest:
        print(f"  Enriched: {enriched_manifest.num_nodes} max nodes, {enriched_manifest.num_edges} max edges")

    print(f"\nWorld models saved to: {Path(args.store_path).expanduser()}")
    print("\nNext: Update benchmark to use --world-model-version for 3x speedup")
    print("=" * 80)


if __name__ == "__main__":
    main()
