# PLAN

## Current Goal

Recover `USA_NAMES` (`sf_bq286`) on the generic Spider Snow pipeline without reintroducing task-ID hardcoding, and keep pushing two tracks in parallel:

- Spider 2.0 Snow as the full-stack SQL benchmark
- BIRD as the grounding-first benchmark

## Important Context

- This directory is **not** a git repository in the current environment, so there is no `git status`-based checkpoint.
- Local model setup in current use:
  - Ollama on `http://127.0.0.1:11435`
  - ScalarLM on `http://localhost:8000`
- Snowflake access requires escalated execution because the sandbox blocks outbound network/DNS.

## What Changed In This Session

### 1. SQL candidate pipeline

Main files:

- [`src/bender/spider_snow_pipeline.py`](/Users/richiek/work/bender/src/bender/spider_snow_pipeline.py)
- [`src/bender/spider_snow_solve.py`](/Users/richiek/work/bender/src/bender/spider_snow_solve.py)

Implemented:

- task packet + candidate generation + reranking pipeline
- Ollama and ScalarLM candidate generators
- SQLGlot parsing/validation guardrail
- surface normalization for Snowflake qualification/quoting
- candidate attempt metadata capture
- no fallback `SELECT * LIMIT 10`
- no gold leakage during solve

### 2. Generic semantic fixes for `USA_NAMES`

Added generic packet semantics:

- `time_scope`
- `comparison_scope`
- `requires_global_denominator`
- `preferred_table_family`

Added generic logic:

- current-vs-archive table family preference
- semantic year/table mismatch rejection
- reusable `share_of_total` heuristic candidate pattern
- reranker bonuses/penalties for global-denominator queries
- heuristic candidates are now mixed into model-backed generation

This was intended to solve `sf_bq286` generically.

### 3. BIRD grounding track

New files:

- [`src/bender/bird.py`](/Users/richiek/work/bender/src/bender/bird.py)
- [`examples/bird_planning_demo.py`](/Users/richiek/work/bender/examples/bird_planning_demo.py)
- [`examples/run_bender_bird_grounding.py`](/Users/richiek/work/bender/examples/run_bender_bird_grounding.py)
- [`docs/bird_official_data.md`](/Users/richiek/work/bender/docs/bird_official_data.md)
- [`tests/test_bird.py`](/Users/richiek/work/bender/tests/test_bird.py)

Implemented:

- BIRD task loader/workspace
- SQLite DB discovery
- `database_description` ingestion
- BIRD world enrichment
- grounding-first benchmark adapter
- gold-table inference from gold SQL

## Current Test Status

Passed:

- [`tests/test_spider_snow_solve.py`](/Users/richiek/work/bender/tests/test_spider_snow_solve.py)
- [`tests/test_spider_snow.py`](/Users/richiek/work/bender/tests/test_spider_snow.py)
- [`tests/test_render_bender_spider_stats.py`](/Users/richiek/work/bender/tests/test_render_bender_spider_stats.py)
- [`tests/test_bird.py`](/Users/richiek/work/bender/tests/test_bird.py)
- [`tests/test_spider_lite.py`](/Users/richiek/work/bender/tests/test_spider_lite.py)
- [`tests/test_database_coprocessor.py`](/Users/richiek/work/bender/tests/test_database_coprocessor.py)

## Current Benchmark State

### Spider Snow: `USA_NAMES`

There is only one Spider Snow task for `USA_NAMES`:

- `sf_bq286`

Old state:

- [` .tmp_spider_snow_native_full_current.json`](/Users/richiek/work/bender/.tmp_spider_snow_native_full_current.json)
- status: `correct`
- this came from the older handcrafted/native path, not the current generic model-backed pipeline

Current generic runs:

- heuristic:
  - [`.tmp_spider_snow_usa_names_heuristic_v1.json`](/Users/richiek/work/bender/.tmp_spider_snow_usa_names_heuristic_v1.json)
  - status: `wrong`
- Ollama + heuristic augmentation:
  - [`.tmp_spider_snow_usa_names_ollama_v5.json`](/Users/richiek/work/bender/.tmp_spider_snow_usa_names_ollama_v5.json)
  - status: `wrong`

#### Why `USA_NAMES` still fails

Heuristic run chose:

- `USA_1910_CURRENT`
- but ranked a simple Wyoming count/ranking query above the new `share_of_total` candidate

Ollama run:

- first model candidate was correctly rejected by semantic validation because it tried to join `USA_1910_2013` for year `2021`
- second candidate used `USA_1910_CURRENT` but still ordered by `c.number DESC` instead of the state-vs-global ratio

So the current state is:

- table-family selection improved
- semantic validator improved
- but top-1 candidate selection is still wrong for `sf_bq286`

### BIRD grounding baseline

Local tiny BIRD-style dataset staged under:

- [`.tmp_bird_tiny`](/Users/richiek/work/bender/.tmp_bird_tiny)

Outputs:

- raw summary:
  - [`.tmp_bird_tiny_grounding_current.json`](/Users/richiek/work/bender/.tmp_bird_tiny_grounding_current.json)
- runner output:
  - [`.tmp_bird_tiny_grounding_runner_current.json`](/Users/richiek/work/bender/.tmp_bird_tiny_grounding_runner_current.json)
- markdown:
  - [`bender_bird_tiny_grounding_stats.md`](/Users/richiek/work/bender/bender_bird_tiny_grounding_stats.md)

Current result:

- `10` tasks evaluated
- `10` with inferred gold tables
- average table recall: `0.95`

Worst current case:

- `cs_semester_0006`
- question: `How many research assistants does Sauveur Skyme have?`
- recall: `0.5`
- missing table: `prof`

## Exact Remaining Work

### Immediate next step for `USA_NAMES`

The next session should fix `sf_bq286` by changing ranking/selection, not by adding a task-specific compiler.

Most likely fix:

1. Make the `share_of_total` candidate outrank plain ranking when:
   - `requires_global_denominator = True`
   - `comparison_scope = scoped_vs_global`
2. Penalize candidates that:
   - sort by raw metric instead of ratio
   - apply state filter only in the outer query but never project/order by the ratio
3. Add a targeted regression test proving:
   - the generated `share_of_total` candidate for `sf_bq286` is ranked above the simple ranking candidate
4. Rerun:
   - heuristic `sf_bq286`
   - Ollama `sf_bq286`

### Next step after `USA_NAMES`

Run a fresh Ollama slice on Spider Snow with the improved semantic reranker:

- start with `4` or `8` tasks
- use `--max-candidates 2`
- keep SQLGlot validation enabled

### Parallel BIRD work

Use the new BIRD runner on a larger local BIRD checkout when available:

- keep it grounding-first
- measure table recall, join path quality, and grounding coverage before full SQL generation

## Useful Commands

### Tests

```bash
cd /Users/richiek/work/bender
PYTHONPATH=src python3 tests/test_spider_snow_solve.py
PYTHONPATH=src python3 tests/test_spider_snow.py
PYTHONPATH=src python3 tests/test_render_bender_spider_stats.py
PYTHONPATH=src python3 tests/test_bird.py
```

### Re-run `USA_NAMES`

Heuristic:

```bash
cd /Users/richiek/work/bender
source .venv/bin/activate
PYTHONPATH=src python examples/run_bender_spider_snow_solve.py \
  --task-id sf_bq286 \
  --candidate-generator heuristic \
  --output .tmp_spider_snow_usa_names_heuristic_v1.json
```

Ollama:

```bash
cd /Users/richiek/work/bender
source .venv/bin/activate
PYTHONPATH=src python examples/run_bender_spider_snow_solve.py \
  --task-id sf_bq286 \
  --max-candidates 2 \
  --candidate-generator ollama \
  --base-url http://127.0.0.1:11435 \
  --model qwen2.5-coder:latest \
  --output .tmp_spider_snow_usa_names_ollama_v5.json
```

### Run BIRD grounding

```bash
cd /Users/richiek/work/bender
PYTHONPATH=src python3 examples/run_bender_bird_grounding.py \
  --bird-root .tmp_bird_tiny \
  --split mini_dev \
  --output .tmp_bird_tiny_grounding_runner_current.json
```

## Summary For A New Session

If a new Claude session starts:

1. Read this file first.
2. Focus first on fixing top-1 candidate ranking for `sf_bq286`.
3. Do not reintroduce task-ID/domain compiler special cases.
4. Keep Spider as the SQL stress test.
5. Keep BIRD as the grounding-first benchmark track.
