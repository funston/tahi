# Full Benchmark Runs

This document describes how to run the serious benchmark passes for BENDER's current SQL grounding evaluations.

These are the benchmarks that should exist before claiming the project is benchmarked in a serious way.

Important scope:

- these are **grounding benchmarks**
- they measure table grounding quality, not end-to-end SQL execution accuracy
- do not present them as Spider/BIRD execution scores

## Prerequisites

From the repo root:

```bash
source .venv/bin/activate
```

Use this Python path for all commands below:

```bash
PYTHONPATH=src:.
```

## Outputs

Human-facing artifacts:

- `benchmarks/sql_grounding_report.html`
- `benchmarks/sql_grounding_report.svg`

Machine-readable artifacts:

- `benchmarks/bird/*.json`
- `benchmarks/gretel/*.json`

## 1. Full BIRD Grounding Run

Preferred mode:

- `--source huggingface`

Fallback mode:

- `--source local`

### Recommended Hugging Face BIRD Run

The BENDER BIRD runner now supports a Hugging Face-backed source modeled on the generalized `bird_dev` path from `superalignment`.

Recommended command:

```bash
PYTHONPATH=src:. python examples/run_bender_bird_ab_benchmark.py \
  --source huggingface \
  --split dev \
  --hf-repo-id Sudnya/bird-sql \
  --hf-cache-dir .local/bird_hf \
  --output benchmarks/bird/full_dev_grounding_report.json
```

What this does:

- loads BIRD problems from Hugging Face
- maps BIRD `dev` to the HF `validation` split
- downloads and extracts the matching database zip into `.local/bird_hf`
- runs the grounding benchmark over that split

You can also force a fresh database download:

```bash
PYTHONPATH=src:. python examples/run_bender_bird_ab_benchmark.py \
  --source huggingface \
  --split dev \
  --hf-repo-id Sudnya/bird-sql \
  --hf-cache-dir .local/bird_hf \
  --force-download \
  --output benchmarks/bird/full_dev_grounding_report.json
```

### Local Tree BIRD Layout

The BIRD runner expects a local root containing one of these layouts:

```text
/path/to/BIRD/
  dev.json
  dev_databases/
```

or:

```text
/path/to/BIRD/
  dev/
    dev.json
    dev_databases/
```

Optional metadata layout:

```text
dev_databases/<db_id>/database_description/
```

The BIRD workspace resolution logic is implemented in:

- [bird.py](/Users/richiek/work/bender/implementations/bird/bird.py)

### Local Tree Command

```bash
PYTHONPATH=src:. python examples/run_bender_bird_ab_benchmark.py \
  --source local \
  --bird-root /path/to/BIRD \
  --split dev \
  --output benchmarks/bird/full_dev_grounding_report.json
```

### What It Runs

- `naive_lexical`
- `schema_only`
- `bender`
- `bender_with_evidence`

### What Those Mean

- `naive_lexical`
  - simple lexical table matching baseline
- `schema_only`
  - BENDER schema coprocessor over parsed schema only
- `bender`
  - BENDER world-model grounding with enriched metadata/documents
- `bender_with_evidence`
  - BENDER world-model grounding plus the dataset evidence field injected into the query path

### Current Local-Tree Blocker

This workspace does **not** currently contain a full local BIRD checkout.

Only this tiny local slice exists:

- [`.tmp_bird_tiny`](/Users/richiek/work/bender/.tmp_bird_tiny)

That blocker is why the new Hugging Face-backed mode is the preferred serious path.

## 2. Full Gretel Grounding Run

### Dataset

The runner uses the Hugging Face dataset:

- `gretelai/synthetic_text_to_sql`

### Full Train Run

```bash
PYTHONPATH=src:. python examples/run_bender_gretel_ab_benchmark.py \
  --split train \
  --hf-cache-dir .local/huggingface \
  --output benchmarks/gretel/train_full_grounding_report.json
```

### Full Test Run

```bash
PYTHONPATH=src:. python examples/run_bender_gretel_ab_benchmark.py \
  --split test \
  --hf-cache-dir .local/huggingface \
  --output benchmarks/gretel/test_full_grounding_report.json
```

### Notes

- `--hf-cache-dir .local/huggingface` is important
- it keeps the dataset cache inside the repo workspace
- this avoids permission problems with `~/.cache/huggingface`

### Optional Full Per-Task Output

If you want every case result included in the JSON:

```bash
PYTHONPATH=src:. python examples/run_bender_gretel_ab_benchmark.py \
  --split test \
  --hf-cache-dir .local/huggingface \
  --include-results \
  --output benchmarks/gretel/test_full_grounding_report.json
```

Use that only if you explicitly want a large detailed report.

For normal publication runs, the summary-only JSON is better.

## 3. Render The Human Report

Once you have the full BIRD and Gretel outputs, build the browser-readable report:

```bash
python examples/render_sql_benchmark_report_html.py \
  --bird-input benchmarks/bird/full_dev_grounding_report.json \
  --gretel-input benchmarks/gretel/test_full_grounding_report.json \
  --output benchmarks/sql_grounding_report.html
```

Optional single-image artifact:

```bash
python examples/render_sql_benchmark_report.py \
  --bird-input benchmarks/bird/full_dev_grounding_report.json \
  --gretel-input benchmarks/gretel/test_full_grounding_report.json \
  --output benchmarks/sql_grounding_report.svg
```

## 4. Publication Checklist

Before using the results publicly:

- confirm the BIRD run used a full local dataset, not the tiny slice
- confirm the Gretel run used the full intended split
- confirm the report labels the work as a grounding benchmark
- confirm the HTML report includes the legend and interpretation
- confirm the output paths are under `benchmarks/`

## 5. Known Limits

- BIRD benchmark currently measures grounding, not final SQL execution
- Gretel benchmark currently measures grounding from synthetic schema context
- Gretel is useful as a broad add-on benchmark, but it is not the same kind of realism as BIRD
- these benchmarks do not yet demonstrate native coprocessor mode

## 6. Next Serious Step After These Runs

After the full BIRD and Gretel grounding runs are complete, the next serious benchmark step should be:

1. add an execution-level SQL benchmark
2. keep the grounding benchmark as a diagnostic layer
3. separate grounding wins from execution wins in every public claim
