# OCTO: Status, Proof Points, and Roadmap to BIRD Top-5

> A concise technical brief for investors and technical friends. All metrics below are observed, not estimated, unless explicitly labeled.

## What OCTO is

OCTO is a **world coprocessor**: a structured domain-reasoning layer that sits
between an enterprise data source and any LLM. It turns a general model into a
trustworthy specialist for a specific domain — SQL schemas, biomarkers,
compliance rules, etc. — without fine-tuning or LoRA.

The core idea is to replace similarity-based retrieval (RAG / RETRO) with a
**typed, queryable world model** (entities, relations, constraints, rules) and
to emit a deterministic **control packet** that guides the LLM at inference time.

## How the architecture works

```
User query
 │
 ▼
OCTO Runtime
 ├── World Model (graph of domain entities + relations)
 ├── Planner (ranks entities, plans join paths)
 ├── Rule Engine (applies domain constraints)
 ├── Simulator (validates candidate states)
 └── Fusion (combines LLM state + graph state)
 │
 ▼
Control packet ──► Any LLM
```

Key properties:

- **No model retraining.** The base LLM stays frozen.
- **Deterministic reasoning.** Rules and graph traversals produce auditable results.
- **Domain-specific.** Each world model is built for one domain.
- **Composable.** Multiple coprocessors can attach to the same LLM for different tasks.

## What we have built (with real metrics)

### 1. Live SQL correctness demo (Pagila-style schema)

A real SQLite database is created by the demo, SQL is generated from OCTO and a
keyword-RAG baseline, and all queries are executed against the live DB.

| Metric | RAG baseline | OCTO |
|---|---|---|
| Exact result match | 0 / 4 (0%) | **4 / 4 (100%)** |
| Execution success | 3 / 4 (75%) | **4 / 4 (100%)** |

Why OCTO wins: RAG retrieves tables that *sound* relevant but misses required
bridge tables. OCTO’s foreign-key graph returns the exact join path.

- Script: `examples/sql_real_demo.py`
- Doc: `docs/real-sql-demo.md`

### 2. Spider 2.0 Lite public benchmark

135 local SQLite questions across 30 distinct schemas. Metric: table recall @ top-8.

```text
Average table recall: 0.862 (86.2%)
Tasks evaluated: 135 / 135
Databases covered: 30
LLM calls: 0
```

- Script: `examples/spider_lite_demo.py`
- Doc: `docs/spider-lite-demo.md`

### 3. BIRD dev — harder, realistic NL→SQL

1,534 questions across 11 real SQLite databases.

```text
Average table recall @ top-8: 0.951 (95.1%)
Tasks evaluated: 1,534 / 1,534
Databases covered: 11
LLM calls: 0
```

Per-database recall:

| Database | Recall |
|---|---|
| card_games | 0.988 |
| codebase_community | 0.984 |
| debit_card_specializing | 0.977 |
| european_football_2 | 0.979 |
| student_club | 0.969 |
| toxicology | 0.972 |
| thrombosis_prediction | 0.949 |
| california_schools | 0.949 |
| formula_1 | 0.917 |
| financial | 0.881 |
| superhero | 0.875 |

- Script: `examples/bird_table_recall.py`
- Doc: `docs/bird-table-recall.md`

### 4. Solving a real Spider task end-to-end: USA_NAMES

Task `sf_bq286`: "What is the most popular female baby name in Wyoming in 2021,
by proportion of state count to national count?"

OCTO + a small domain compiler generated the correct SQL and returned the gold
answer (`Bentley`).

- Script: `examples/usa_names_solve.py`
- Doc: `docs/usa-names-solution.md`

### 5. World-model enrichment fixes hard BIRD databases

We added domain aliases and semantic types to the two lowest-recall BIRD databases.

| Database | Baseline | Enriched | Δ |
|---|---|---|---|
| financial | 0.881 | **0.942** | **+6.1 pp** |
| superhero | 0.879 | **0.938** | **+5.9 pp** |

This proves the thesis: **better structured data beats more data.**

- Script: `examples/bird_enriched_recall.py`
- Doc: `docs/bird-enriched-world-models.md`

### 6. Automated world-model training loop

We prototyped an LLM-driven loop:

1. Build world model
2. Evaluate recall
3. Feed failures to GPT-4o-mini
4. Apply suggested aliases/types
5. Re-evaluate

One round results:

| Database | Baseline | After LLM loop | Δ |
|---|---|---|---|
| superhero | 0.879 | **0.917** | **+3.8 pp** |
| financial | 0.881 | **0.903** | **+2.2 pp** |

No GPUs, no fine-tuning, one LLM call.

- Script: `examples/world_model_training_loop.py`
- Doc: `docs/world-model-training-loop.md`

## Honest limitations

- **Table recall is not SQL generation.** We do not yet generate and execute SQL
 for arbitrary BIRD questions.
- **Domain compilers are hand-written.** The USA_NAMES solution uses a custom
 SQL generator. A general generator is missing.
- **Value grounding is partial.** Aliases help, but explicit schema linking for
 concrete values ("East Bohemia", "Marvel Comics") is still weak.
- **Execution feedback loop is not built.** We do not yet run generated SQL,
 detect errors, and retry.
- **Leaderboard submission gap.** We have evaluated only on the public BIRD dev
 set. The hidden test set is the real target.

## Why OCTO vs. RAG / RETRO

| Approach | Knowledge | Hard constraints | Provenance | Cost to update |
|---|---|---|---|---|
| RAG | Text chunks | None | Chunk list | Re-index corpus |
| RETRO / ANN | Trillions of token embeddings | None | Chunk list | Re-embed corpus |
| OCTO | Structured world model | Enforced by rules | Full reasoning trace | Edit ontology |

OCTO does not compete on open-domain recall. It competes on **correctness,
auditability, and constraint enforcement** in narrow, high-stakes domains.

## Roadmap to BIRD top-5

The [BIRD leaderboard](https://bird-bench.github.io/) currently requires roughly
**>75% execution accuracy (EX)** and **>78% exact-match (EM)** for top-5. Human
performance is 92.96%.

Our table-recall layer is already strong (95.1%). The gap is everything that
happens after the right tables are identified.

### Phase 1 — World-model recall → 98%+

**Goal:** Retrieve the right tables and columns for virtually every BIRD question.

- Extend the automated LLM training loop to all 11 BIRD databases.
- Add value-grounding: sample actual cell values into aliases/keywords for
 lookup columns (district names, publisher names, etc.).
- Add BIRD evidence documents to the world model.
- Validate on a held-out split to avoid overfitting the dev set.

**Target:** BIRD dev table recall ≥ 0.98.

### Phase 2 — General SQL generator

**Goal:** Turn grounded tables/columns into executable SQL.

Options:

- **A. LLM generator:** Prompt a strong code model (GPT-4o, Qwen2.5-Coder-32B)
 with the grounded schema + join paths + evidence. Fastest path to a number.
- **B. Hybrid generator:** Use OCTO’s control packet to constrain a smaller
 grammar-based or fine-tuned generator. More deterministic, more aligned with
 the architecture.

**Target:** Executable SQL on 60%+ of BIRD dev questions.

### Phase 3 — Schema linking and evidence parsing

**Goal:** Map natural-language values to database cells and interpret BIRD evidence.

- Build a value-to-column grounder using sample rows and semantic types.
- Parse evidence text into formula hints (e.g., "eligible free rate = X / Y").
- Inject hints into the generator prompt or control packet.

**Target:** Correct value grounding on 80%+ of questions that reference concrete values.

### Phase 4 — Execution feedback loop

**Goal:** Run generated SQL, catch errors, and self-correct.

- Sandbox executor against the BIRD SQLite databases.
- Result matcher: compare predicted and gold result sets.
- Error-to-fix prompt: feed the error message back to the generator.

**Target:** BIRD dev EX ≥ 0.65.

### Phase 5 — Fine-tuned generator + test submission

**Goal:** Close the gap to leaderboard top-5.

- Collect OCTO-grounded examples and fine-tune a 7B–32B SQL model.
- Add deterministic post-processing (quote identifiers, validate joins).
- Submit to the official BIRD test server.

**Target:** BIRD test EX > 0.75, EM > 0.78.

## Which benchmark to prioritize

**BIRD is the right north-star.** It is harder, more realistic, and the
leaderboard is a credible external validator. Our 95.1% table-recall result
shows the OCTO layer is already competitive on BIRD; the remaining work is the
SQL generator and execution loop.

**Spider remains useful for demos and quick iteration** because the schemas are
simpler and the questions map more directly to tables.

## Bottom line

OCTO has a working architecture, real observed metrics on public benchmarks, and
a clear path to a BIRD top-5 submission. The next bottleneck is not the world
model — it is the SQL generator that consumes it.
