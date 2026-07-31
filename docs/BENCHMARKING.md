# Benchmarking

This repo uses a small benchmark surface:

- one primary BIRD benchmark report
- one SQL grounding aggregate report
- one benchmark runbook section here

Everything else belongs in `docs/legacy/`.

## Benchmark Philosophy

Measure BENDER in layers:

1. world-model quality
2. task outcome quality
3. A/B value over simpler baselines

The goal is not to hide behind one aggregate score. The goal is to show where BENDER adds value.

## Cost and Scale Perspective

BENDER benchmarks are cheap to run because BENDER world models are small, structured graphs. A full BIRD schema world model is megabytes, not petabytes. This is fundamentally different from RETRO-style ANN systems that require embedding trillions of tokens and storing them on NVMe arrays.

When comparing BENDER to large-scale retrieval baselines, keep the cost dimension explicit:

- **BENDER cost:** domain curation + standard LLM inference.
- **RETRO/ANN cost:** embedding compute + PB-scale storage + specialized serving hardware.

BENDER should win on correctness-per-dollar in constrained domains, not on raw recall over web-scale corpora.

See [RETRO/ANN vs. BENDER](/Users/richiek/work/bender/docs/RETRO_ANN_VS_BENDER.md) for the full comparison.

## Primary Artifact

Primary BIRD artifact:

- [bird_benchmark_report.html](/Users/richiek/work/bender/benchmarks/bird/bird_benchmark_report.html)

If the question is "what is BENDER's current most serious SQL benchmark artifact?", open this first.

## Full Runs

### Full BIRD Dev

Preferred serious path:

```bash
source .venv/bin/activate
PYTHONPATH=src:. python examples/run_bender_bird_ab_benchmark.py \
  --source huggingface \
  --split dev \
  --hf-repo-id Sudnya/bird-sql \
  --hf-cache-dir .local/bird_hf \
  --output benchmarks/bird/full_dev_grounding_report.json
```

### Full Gretel

```bash
source .venv/bin/activate
PYTHONPATH=src:. python examples/run_bender_gretel_ab_benchmark.py \
  --split test \
  --hf-cache-dir .local/huggingface \
  --output benchmarks/gretel/test_full_grounding_report.json
```

### Render Reports

BIRD-only:

```bash
python examples/render_bird_benchmark_report_html.py \
  --bird-input benchmarks/bird/full_dev_grounding_report.json \
  --output benchmarks/bird/bird_benchmark_report.html
```

Aggregate SQL page:

```bash
python examples/render_sql_benchmark_report_html.py \
  --bird-input benchmarks/bird/full_dev_grounding_report.json \
  --gretel-input benchmarks/gretel/test_full_grounding_report.json \
  --output benchmarks/sql_grounding_report.html
```

## Path To Leaderboard-Level

Current status:

- BENDER has a real full-dev BIRD grounding result
- BENDER does not yet have a leaderboard-comparable BIRD execution result

What has to happen next:

1. add a BIRD execution benchmark runner
2. keep grounding and execution metrics separate
3. use `bender_with_evidence` as the serious default path
4. put a strong SQL generator behind BENDER
5. add repair and reranking
6. publish a BIRD execution HTML report, not just grounding

The important rule is simple:

- grounding accuracy is diagnostic
- execution accuracy is leaderboard-level

Do not compare them directly.

## Current Benchmark Tracks

### BIRD

Runner:

```bash
PYTHONPATH=src python examples/run_bender_bird_ab_benchmark.py --bird-root /path/to/BIRD --output bird_ab.json
```

Current comparison:

- `naive_lexical`
- `schema_only`
- `bender`
- `bender_with_evidence`

Meaning:

- `naive_lexical` is a simple lexical table-matching baseline
- `schema_only` uses the schema coprocessor without enriched metadata documents
- `bender` uses the enriched world model with BIRD metadata documents
- `bender_with_evidence` also injects the task's evidence field into the BENDER query path

Current metrics:

- accuracy where `table_recall == 1.0`
- average table recall
- top-1 hit rate

Tiny local slice result:

| System | Tasks | Accuracy | avg_table_recall | avg_top1_hit |
| --- | --- | --- | --- | --- |
| naive_lexical | 10 | 0.100 | 0.300 | 0.500 |
| schema_only | 10 | 0.900 | 0.950 | 0.800 |
| bender | 10 | 0.900 | 0.950 | 0.800 |
| bender_with_evidence | 10 | 1.000 | 1.000 | 1.000 |

Artifacts:

- [bird_benchmark_report.html](/Users/richiek/work/bender/benchmarks/bird/bird_benchmark_report.html)
- [sql_grounding_report.html](/Users/richiek/work/bender/benchmarks/sql_grounding_report.html)
- [tiny_grounding_report.json](/Users/richiek/work/bender/benchmarks/bird/tiny_grounding_report.json)
- [sql_grounding_report.svg](/Users/richiek/work/bender/benchmarks/sql_grounding_report.svg)

Interpretation:

- On the tiny local BIRD slice, plain BENDER world enrichment alone matches the schema-only grounding baseline.
- When BENDER consumes BIRD's own task evidence field, it improves from `0.90` to `1.00` grounding accuracy on that slice.
- The human-facing benchmark report now also includes external BIRD leaderboard references, clearly labeled as execution-accuracy context rather than directly comparable grounding scores.

Full-dev artifact:

- [bird_benchmark_report.html](/Users/richiek/work/bender/benchmarks/bird/bird_benchmark_report.html)
- [full_dev_grounding_report.json](/Users/richiek/work/bender/benchmarks/bird/full_dev_grounding_report.json)

Full-dev result:

| System | Tasks | Accuracy | avg_table_recall | avg_top1_hit |
| --- | --- | --- | --- | --- |
| naive_lexical | 1534 | 0.334 | 0.524 | 0.636 |
| schema_only | 1534 | 0.864 | 0.932 | 0.761 |
| bender | 1534 | 0.864 | 0.932 | 0.761 |
| bender_with_evidence | 1534 | 0.926 | 0.964 | 0.746 |

### Mass Spec

Runner:

```bash
PYTHONPATH=src python examples/run_bender_mass_spec_benchmark.py --output mass_spec_ab.json
```

Current comparison:

- `retrieval_only`
- `bender`

Meaning:

- `retrieval_only` uses retrieval ranking without deterministic peak-assignment logic
- `bender` uses the full mass-spec adapter with adduct, polarity, and mass-constraint reasoning

Current metrics:

- top-1 exact assignment accuracy
- average top-1 mass error for BENDER

### Gretel Synthetic Text-to-SQL

Runner:

```bash
PYTHONPATH=src python examples/run_bender_gretel_ab_benchmark.py --input-json .tmp_gretel_train_100.json --output gretel_ab.json
```

Or, with direct dataset access:

```bash
PYTHONPATH=src python examples/run_bender_gretel_ab_benchmark.py --split 'train[:100]' --output gretel_ab.json
```

Current comparison:

- `naive_lexical`
- `schema_only`
- `bender`

Meaning:

- `naive_lexical` is a simple lexical table-matching baseline
- `schema_only` uses only parsed schema context from the Gretel sample
- `bender` enriches the world model with Gretel domain, task-type, and explanation metadata

Current metrics:

- accuracy where `table_recall == 1.0`
- average table recall
- top-1 hit rate

100-row sample result:

| System | Tasks | Accuracy | avg_table_recall | avg_top1_hit |
| --- | --- | --- | --- | --- |
| naive_lexical | 100 | 0.590 | 0.635 | 0.680 |
| schema_only | 100 | 0.770 | 0.800 | 0.820 |
| bender | 100 | 0.770 | 0.800 | 0.820 |

Artifacts:

- [sql_grounding_report.html](/Users/richiek/work/bender/benchmarks/sql_grounding_report.html)
- [train_100_input.json](/Users/richiek/work/bender/benchmarks/gretel/train_100_input.json)
- [train_100_grounding_report.json](/Users/richiek/work/bender/benchmarks/gretel/train_100_grounding_report.json)
- [sql_grounding_report.svg](/Users/richiek/work/bender/benchmarks/sql_grounding_report.svg)

Interpretation:

- Gretel is a fast add-on benchmark for schema grounding over synthetic SQL tasks.
- On the current 100-row sample, BENDER metadata enrichment matches the schema-only grounding baseline instead of beating it.
- That still gives a useful reference point: BENDER is not getting a free win from synthetic dataset decoration alone.
- Because no public official Gretel leaderboard was found, the report uses Gretel's own dataset-card quality evidence as the external reference point instead.

## Output Shape

Both runners emit the same high-level JSON shape:

- `benchmark_name`
- `systems`
  - `system`
  - `tasks_evaluated`
  - `accuracy`
  - `metrics`
  - `results`
- `markdown_summary`

This is designed to support:

- saved benchmark artifacts
- blog tables
- chart generation
- later CI regression tracking

## Report Renderers

Use the shared report renderers to turn benchmark JSON into one human-readable HTML page and, optionally, one combined SVG artifact:

```bash
python examples/render_sql_benchmark_report_html.py \
  --bird-input benchmarks/bird/tiny_grounding_report.json \
  --gretel-input benchmarks/gretel/train_100_grounding_report.json \
  --output benchmarks/sql_grounding_report.html

python examples/render_sql_benchmark_report.py \
  --bird-input benchmarks/bird/tiny_grounding_report.json \
  --gretel-input benchmarks/gretel/train_100_grounding_report.json \
  --output benchmarks/sql_grounding_report.svg
```

## Important Limits

These benchmarks are useful now, but they are not yet the final public benchmark story:

- BIRD currently measures grounding quality, not full end-to-end SQL execution accuracy
- mass spec currently uses a retrieval-only baseline as the "RAG-like" comparison, not a live external LLM baseline
- Gretel currently measures grounding quality from synthetic schema contexts, not end-to-end execution
- native coprocessor mode is still a backend-specific path

## Current Focus

For SQL credibility, BIRD is the main benchmark to improve now.

Gretel remains a secondary add-on dataset, not the headline proof.
