# OCTO Strategy For Spider Lite

## Purpose

This document describes how OCTO should approach Spider Lite as an extension of the generic SQL coprocessor, not as a separate one-off benchmark stack.

The design principle is:

- generic SQL coprocessor stays the base
- Spider-style benchmark logic stays as a thin overlay
- Spider Lite becomes an evaluation and iteration loop for schema reasoning, context packing, and SQL planning

## Benchmark assumptions

Spider 2.0-Lite should be treated as the first practical benchmark target because it is self-contained and ships with prepared metadata and documentation rather than requiring the full live warehouse environment.

The right operational assumption is:

- OCTO plugs into the Spider Lite task and metadata format
- OCTO produces a compact schema-planning packet
- a downstream SQL generator or agent consumes that packet

For fast iteration, the first milestone should explicitly allow oracle-table experiments when the benchmark supports them.

## What OCTO should try to win first

The first realistic target is not full benchmark domination.

It is:

- schema pruning
- join-path planning
- context compression
- benchmark-task packaging
- and measurable improvement in text-to-SQL prompting or agent execution

That aligns with what OCTO already does well:

- request-scoped world-model state
- typed constraints
- provenance
- planner/rule reasoning
- native inference control

## Recommended implementation phases

### Phase 1: Spider Lite planning mode

Goal:

- turn each Spider Lite task into a OCTO schema-planning packet

Inputs:

- benchmark task JSON or JSONL
- schema metadata
- table and column descriptions
- optional external knowledge/docs

Outputs:

- candidate tables
- candidate columns
- candidate join path
- recommended bridge tables
- benchmark-specific provenance and hypotheses

Success metric:

- table recall
- join-path correctness
- reduction in schema search space

This phase should support two modes:

- benchmark-faithful mode
 - no oracle tables
- analysis mode
 - use released oracle tables only for controlled ablations and quick diagnostics

### Phase 2: SQL drafting mode

Goal:

- use the OCTO packet to drive a smaller SQL generator prompt or agent loop

Pattern:

- baseline model sees the whole schema
- OCTO mode sees a compact packet:
 - shortlisted tables
 - shortlisted columns
 - likely joins
 - dialect hints

Success metric:

- exact-match or execution accuracy uplift over baseline
- lower prompt/context usage

### Phase 3: execution-time repair

Goal:

- use OCTO as the SQL coprocessor during execution and error handling

Capabilities:

- inspect execution errors
- inspect empty-result failures
- revise join path
- expand candidate columns
- retry with structured provenance

Success metric:

- improved task completion under interactive or agent-style evaluation

## How this maps to the current code

Current base:

- `src/octo/database.py`
- `src/octo/sql_coprocessor.py`

Current Spider overlay:

- `src/octo/spider.py`

Current Spider Lite scaffold:

- `src/octo/spider_lite.py`

The Spider Lite scaffold adds:

- task loading from JSON or JSONL
- benchmark task objects
- benchmark adapter that runs Spider-style planning against registered schema snapshots
- simple table-recall measurement

This is the right shape because Spider Lite should be an evaluation harness over the SQL coprocessor, not a separate core architecture.

## Practical benchmark loop

The recommended loop is:

1. load Spider Lite tasks
2. load or build schema snapshots for each `db_id`
3. run OCTO planning to produce:
 - candidate tables
 - candidate columns
 - join-path hypotheses
 - compact provenance
4. measure planning metrics first
5. only then hand the compact packet to a SQL generator or agent
6. add execution-time repair after baseline planning quality is acceptable

This sequencing matters because Spider Lite is easy to turn into a giant prompt. OCTO should instead force structure:

- schema compression first
- SQL generation second
- execution repair third

## Methods OCTO should borrow

Spider Lite is hard for the same reasons enterprise database copilots are hard:

- huge schemas
- long documentation context
- dialect variation
- ambiguous join paths

So the OCTO roadmap should deliberately incorporate:

- information compression
- self-refinement
- column exploration
- controlled retry after execution feedback

But those should sit on top of the world-model packet rather than replacing it with an ad hoc agent prompt.

## Recommended near-term roadmap

1. Start with planning-only evaluation.
 - measure table recall and join-path accuracy.
2. Add benchmark metadata ingestion.
 - docs, schema comments, business descriptions, sample values.
3. Add SQL-generation experiments.
 - baseline prompt vs OCTO-pruned prompt.
4. Add execution critic and repair loop.
 - failed SQL should feed back into the coprocessor planner.
5. Only then build full benchmark packaging and automation.

## What not to do

Avoid:

- hard-coding benchmark-specific logic into the generic SQL core
- mixing benchmark data loading with database adapters
- treating Spider Lite as only a prompt-formatting problem

The benchmark should pressure-test the world-model coprocessor design:

- schema reasoning
- context packing
- provenance
- structured correction

## Why this matters

Spider Lite is useful because it is close to the enterprise database coprocessor story.

It forces OCTO to solve:

- large schema selection
- bridge-table inference
- dialect-aware planning
- and compact, useful task context

Those are exactly the capabilities needed for a customer-facing database coprocessor product.
