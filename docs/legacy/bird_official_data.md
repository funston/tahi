# Working With BIRD Data

## Recommended target

Start with `mini_dev`, not a full BIRD evaluation run.

Reasons:

- it is small enough to iterate on OCTO grounding quickly
- it exercises real BIRD SQLite schemas and evidence fields
- it lets us measure schema grounding before claiming end-to-end SQL generation

## File layout OCTO expects

The current OCTO BIRD workspace support looks for layouts like:

- `mini_dev/dev.json`
- `mini_dev/dev_databases/<db_id>/<db_id>.sqlite`
- `mini_dev/dev_databases/<db_id>/database_description/*`

Fallback layouts are also supported:

- `dev.json`
- `dev_databases/<db_id>/<db_id>.sqlite`
- `databases/<db_id>/<db_id>.sqlite`

## What OCTO uses from BIRD

For grounding-first experiments, the important task fields are:

- `question_id`
- `db_id`
- `question`
- `evidence`
- `SQL`

Optional analysis fields:

- `difficulty`
- `gold_tables`
- `external_knowledge`

## Current OCTO support

Current code:

- `src/octo/bird.py`
 - BIRD task loading
 - official-ish repo-layout discovery
 - SQLite database discovery
 - `database_description` document loading
 - world enrichment from BIRD metadata docs
- `examples/bird_planning_demo.py`
 - planning-only grounding demo over a local BIRD checkout

## Recommended workflow

1. Load `mini_dev/dev.json`.
2. Introspect each SQLite database into a schema snapshot.
3. Enrich the OCTO world with `database_description` documents.
4. Run planning first:
 - candidate tables
 - candidate join path
 - bridge tables
 - provenance
5. Only after grounding quality is acceptable, layer SQL generation on top.

## Why this track matters

This BIRD path is intentionally grounding-first.

The immediate question is not "Can OCTO beat the leaderboard end-to-end today?"
The immediate question is "Can OCTO compress and structure large database context well enough to make downstream SQL generation easier and cheaper?"
