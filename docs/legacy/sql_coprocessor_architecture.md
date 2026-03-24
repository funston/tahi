# BENDER SQL Coprocessor Architecture

## Purpose

This document describes the SQL-oriented coprocessor architecture now present in `src/bender`.

The design principle is:

- the base abstraction is generic SQL schema reasoning,
- database-specific adapters sit underneath it,
- benchmark- or domain-specific layers sit on top of it.

So the architecture is not:

- hard-coded for Spider,
- hard-coded for Pagila,
- or hard-coded for PostgreSQL alone.

It is:

- generic SQL coprocessor base,
- PostgreSQL adapter today,
- Pagila fixture for local development,
- Spider-style schema reasoning as one concrete extension.

## Layering

### 1. Generic SQL schema model

Implemented in:

- `src/bender/database.py`
- `src/bender/sql_coprocessor.py`

Core objects:

- `SQLSchemaSnapshot`
- `SQLTableProfile`
- `SQLColumnProfile`
- `SQLForeignKey`
- `SQLSchemaPlanner`
- `SQLSchemaRuleEngine`
- `SQLSchemaCoprocessor`

Responsibilities:

- represent tables, columns, sample values, and foreign keys
- convert schema metadata into a BENDER world model
- infer candidate tables, columns, join paths, and query intent
- emit a structured coprocessor packet for database questions

This is the reusable base for new SQL-backed domains.

### 2. Database adapter layer

Implemented today in:

- `PostgresSchemaIntrospector` in `src/bender/database.py`

Responsibilities:

- connect to a live PostgreSQL database
- introspect schemas, tables, columns, and foreign keys
- optionally pull sample values
- produce a `SQLSchemaSnapshot`

This is intentionally adapter-shaped. The next adapters could be:

- MySQL
- SQLite
- DuckDB
- BigQuery metadata export
- Snowflake metadata export

### 3. Concrete data source / fixture layer

Implemented today in:

- `build_pagila_fixture_snapshot()` in `src/bender/database.py`

Purpose:

- provide a local repeatable SQL schema fixture
- support tests and demos without requiring a live database import
- act as the first relational coprocessor development target

Pagila is used as a fixture, not as the architecture itself.

### 4. Benchmark- or domain-specific layer

Implemented today in:

- `src/bender/spider.py`

Core objects:

- `SpiderSchemaPlanner`
- `SpiderSchemaRuleEngine`
- `SpiderSchemaCoprocessor`

Responsibilities:

- add Spider-style schema reasoning behavior
- infer likely bridge tables
- bias toward benchmark-relevant join reasoning
- preserve the generic SQL coprocessor underneath

This is where benchmark-specific logic should live.

## Why this abstraction matters

If the base layer were called `Spider` or `Pagila`, the architecture would be backwards.

The right generalization is:

- SQL schema coprocessor is the product layer
- PostgreSQL is one adapter
- Pagila is one dataset
- Spider is one evaluation target

That lets BENDER extend to:

- enterprise Postgres
- warehouse metadata mirrors
- operational databases
- internal analytics marts
- benchmark datasets

without changing the core coprocessor contract.

## Current runnable surfaces

### Generic SQL demo

- `examples/sql_schema_coprocessor_demo.py`

Uses:

- generic SQL coprocessor
- Pagila fixture snapshot

### PostgreSQL / Pagila scaffold demo

- `examples/postgres_pagila_schema_demo.py`

Uses:

- `PostgresSchemaIntrospector` for a live database if `PG*` vars are set
- otherwise the Pagila fixture

### Spider-style schema demo

- `examples/spider_schema_coprocessor_demo.py`

Uses:

- Spider-specific planner/rules
- generic SQL schema base
- Pagila fixture snapshot

## How to extend this

### New SQL-backed enterprise database

1. Build or reuse a schema adapter that returns `SQLSchemaSnapshot`.
2. Feed that snapshot into `SQLSchemaCoprocessor.from_snapshot(...)`.
3. Add domain-specific planner/rules only where needed.

### New benchmark

1. Keep `SQLSchemaCoprocessor` as the base.
2. Create benchmark-specific planner/rules as a thin overlay.
3. Add evaluation harnesses and fixtures separately.

### Data warehouse direction

For a larger enterprise deployment, the likely evolution is:

1. schema metadata into the SQL coprocessor
2. sample value profiles and column statistics
3. business glossary and dbt model docs
4. query logs and common join paths
5. execution-time SQL critique and repair

That is the path from schema coprocessor to a full database world-model coprocessor.

## Current limitations

- retrieval still uses the Phase 1 lightweight embedding/indexing layer
- no live SQL execution critic is implemented yet
- no text-to-SQL generation or repair loop is implemented yet
- no warehouse-scale metadata adapter is implemented yet

Those are next-stage features, not missing prerequisites for the current scaffold.

## Bottom line

The current code now has the right shape:

- generic SQL base,
- PostgreSQL adapter,
- Pagila fixture,
- Spider extension.

That is a reusable foundation for both:

- real database-backed enterprise coprocessors
- and benchmark-facing schema reasoning work.
