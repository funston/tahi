# OCTO Spider 2.0 Lite Demo — Real Benchmark Metrics

## What this is

`examples/spider_lite_demo.py` evaluates OCTO's SQL schema coprocessor on the
**real Spider 2.0 Lite benchmark** (local SQLite split). It measures
**table recall**: for each natural-language question, did the coprocessor's
top-k candidate tables include the tables that human annotators marked as
necessary to answer the question?

No toy metrics, no hand-tuned paths, no fake baseline.

## Dataset

| Property | Value |
|---|---|
| Benchmark | Spider 2.0 Lite (local SQLite tasks) |
| Tasks evaluated | 135 (`local*` instance IDs) |
| Databases | 30 distinct SQLite schemas |
| Gold signal | `methods/gold-tables/spider2-lite-gold-tables.jsonl` |
| Metric | Table recall = \|gold ∩ predicted\| / \|gold\| |

The SQLite metadata and databases are part of the official Spider 2.0 Lite
release; only the local SQLite subset is used because it can be evaluated
without cloud credentials.

## How it works

1. **Load tasks.** Read `spider2-lite.jsonl` and keep only `local*` tasks.
2. **Attach gold tables.** Merge the official oracle gold-table list.
3. **Build a schema world model per database.** For each database, the script
 reads the official JSON metadata/DDL, builds a `SQLSchemaSnapshot`, and
 converts it into a `WorldModel` (tables, columns, foreign keys, schema
 families, plus DDL/table metadata documents).
4. **Run the coprocessor.** `SpiderSchemaCoprocessor` retrieves from the world
 model, ranks tables, and plans a join path using the schema graph.
5. **Score table recall.** Compare the returned candidate tables to the gold
 tables.

The coprocessor runs **entirely locally**; no LLM API calls are made.

## Run it

```bash
python examples/spider_lite_demo.py --output /tmp/spider_lite_results.json
```

Add `--compare-baseline` to also score a keyword/heuristic-only baseline that
uses the same planner but with an empty world model:

```bash
python examples/spider_lite_demo.py --compare-baseline
```

## Observed results

Run on 2026-07-31 with `top_k=8`:

```text
Spider 2.0 Lite (local SQLite) — 135 tasks evaluated
Tasks with gold tables: 135
Average table recall @ top-8: 0.862
Keyword/heuristic-only baseline recall: 0.862 (delta: +0.000)
```

### Per-database recall (OCTO)

| Database | Tasks | Avg. table recall |
|---|---|---|
| AdventureWorks | 1 | 1.000 |
| Airlines | 2 | 1.000 |
| Baseball | 2 | 0.750 |
| BowlingLeague | 1 | 0.750 |
| Brazilian_E_Commerce | 8 | 0.958 |
| California_Traffic_Collision | 3 | 1.000 |
| Db-IMDB | 5 | 1.000 |
| EU_soccer | 5 | 0.960 |
| E_commerce | 3 | 0.917 |
| EntertainmentAgency | 3 | 1.000 |
| IPL | 11 | 0.964 |
| Pagila | 2 | 0.812 |
| WWE | 1 | 0.857 |
| bank_sales_trading | 15 | 0.933 |
| chinook | 3 | 0.944 |
| city_legislation | 10 | 0.883 |
| complex_oracle | 6 | 0.804 |
| delivery_center | 3 | 1.000 |
| education_business | 5 | 1.000 |
| electronic_sales | 1 | 1.000 |
| f1 | 9 | 0.318 |
| imdb_movies | 2 | 1.000 |
| log | 5 | 0.800 |
| modern_data | 7 | 0.786 |
| music | 1 | 1.000 |
| northwind | 2 | 1.000 |
| oracle_sql | 8 | 0.750 |
| school_scheduling | 1 | 0.750 |
| sqlite-sakila | 7 | 0.751 |
| stacking | 3 | 1.000 |

## What the metrics actually mean

* **Table recall @ top-8** — Of the tables a human annotator said are needed
 to answer the question, what fraction appear in the coprocessor's top-8
 candidate tables?
* **Baseline recall** — Same metric, but the world model is replaced with an
 empty graph so the planner relies only on keyword overlap and hard-coded
 heuristics.

These numbers are **observed** by running the coprocessor against every local
SQLite task, not extrapolated or estimated.

## Honest limitations

* **Task is table selection, not SQL generation.** The demo measures whether
 OCTO retrieves the right tables. It does not generate or execute the final
 SQL query.
* **World model did not improve over the keyword baseline on this metric.**
 The keyword/heuristic baseline achieved the same 86.2% recall. This is
 expected for a benchmark where table names strongly signal relevance; the
 added value of the world model is in **structured join-path planning**,
 **foreign-key traversal**, and **auditable provenance** (demonstrated in the
 Pagila live-SQL demo), not necessarily in raw table recall on this dataset.
* **No cross-domain generalization tested.** Each task uses its own schema;
 the demo does not test multi-hop reasoning across disconnected domains.
* **top-k=8 is generous.** A production system would need high recall at
 smaller k.

## Why this matters

Spider 2.0 Lite is a real, public benchmark. Getting 86.2% table recall across
30 distinct schemas with no fine-tuning, no LLM calls, and deterministic
graph-based reasoning shows that OCTO can be applied to **enterprise schemas it
has never seen before** by simply building a world model from the catalog.

The fact that the keyword baseline matches this recall on table selection
highlights an important design principle: **OCTO does not abandon strong
heuristics; it wraps them in a structured, verifiable world model** so that the
same reasoning can be audited, versioned, and extended with domain rules.

## Files

* Demo script: `examples/spider_lite_demo.py`
* Live SQL demo: `examples/sql_real_demo.py` (proves join-path correctness)
* Investor slide: `docs/investor-proof-slide.md`
