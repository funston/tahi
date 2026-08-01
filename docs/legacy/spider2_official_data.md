# Working With Official Spider 2.0 Data

## Recommended target

Start with `Spider 2.0-Lite`, not the full Spider 2.0 benchmark.

Reasons:

- it is the official text-to-SQL setting
- it is self-contained enough for iterative development
- it matches the current OCTO SQL coprocessor direction

## Official file layout to expect

In an official `Spider2` checkout, the key files are:

- `spider2-lite/spider2-lite.jsonl`
- `methods/gold-tables/spider2-lite-gold-tables.jsonl`

Useful related directories:

- `spider2-lite/evaluation_suite/`
- `spider2-lite/evaluation_suite/gold/`

The current OCTO Spider Lite workspace support is written around that layout.

## Task fields OCTO should care about

For planning mode, the important task fields are:

- `instance_id`
- `db` or `db_id`
- `question`
- `external_knowledge`

Optional analysis fields:

- `gold_tables`
- `oracle_tables`
- partial `gold_sql`

## How OCTO uses the official data

The intended workflow is:

1. Load `spider2-lite.jsonl`.
2. Build or register a schema snapshot for each `db_id`.
3. Optionally attach released oracle tables for analysis mode.
4. Run OCTO planning to produce:
 - candidate tables
 - candidate columns
 - candidate join path
 - recommended bridge tables
 - provenance
5. Measure planning quality before attempting full SQL generation.

## Current OCTO support

Current code:

- `src/octo/spider_lite.py`
 - task loading
 - official repo-layout discovery
 - oracle-table attachment
 - snapshot-manifest loading
- `examples/spider_lite_planning_demo.py`
 - demo entrypoint for an official Spider2 checkout
- `scripts/build_spider2_sqlite_snapshots.py`
 - builds `db_id -> snapshot.json` files
- `scripts/build_spider2_world_cache.py`
 - materializes reusable OCTO world caches per `db_id`

## Recommended precache flow

To keep iteration fast, treat Spider 2.0-Lite as a cached set of OCTO worlds.

Recommended sequence:

1. generate `snapshot.json` files from metadata or local `.sqlite` databases
2. build `world.json` cache files from those snapshots
3. reuse the cached worlds during planning and later SQL-agent experiments

That avoids rebuilding schema worlds on every run and makes it easier to compare:

- metadata-derived worlds
- exact local-SQLite worlds
- future enriched worlds with docs and query-log priors

## Recommended next integration step

The next missing piece is per-`db_id` schema snapshot generation for the actual Spider Lite databases.

That should be done with a manifest:

- `db_id -> snapshot.json`

so OCTO can run planning over real Spider Lite tasks without hard-coding benchmark databases into the core runtime.
