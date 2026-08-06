<!-- OCTO One-Page Investor Proof Slide -->
<!-- Render with any Markdown-to-PDF/HTML tool, or paste into a deck builder. -->

<div align="center">

# OCTO: A World Coprocessor That Grounds LLMs in Domain Truth
## The Claim

Large language models write fluent SQL but hallucinate joins and miss bridge
tables. RAG and RETRO retrieve text chunks or embeddings; they have no notion
of foreign-key topology or typed domain relations.

**OCTO replaces similarity retrieval with a structured world model.** We encode
a domain as a graph (entities, relations, constraints), retrieve and plan over
that graph, and emit a deterministic, auditable control packet that guides any
LLM at inference time — no fine-tuning, no LoRA.

---

## Proof 1: Live SQL on a Real Database

| | |
|---|---|
| **Domain** | Pagila-style DVD rental schema (11 tables, 12 FKs) |
| **Database** | Live SQLite database created by the demo |
| **Task** | 4 natural-language count questions requiring multi-table joins |
| **Baseline** | Keyword-based table retrieval + naive chain |
| **Treatment** | OCTO `SQLSchemaCoprocessor` + deterministic SQL generator |
| **Validation** | Execute gold, OCTO, and RAG SQL; compare exact result sets |

**Example:** *“How many actors have appeared in comedy films?”* 
**Correct path:** `actor → film_actor → film → film_category → category`

| Metric | RAG baseline | OCTO |
|---|---|---|
| **Exact result match** | 0 / 4 (0%) | **4 / 4 (100%)** |
| **Execution success** | 3 / 4 (75%) | **4 / 4 (100%)** |

> The RAG baseline finds tables that *sound* relevant but misses required bridge
> tables. OCTO’s graph traversal returns the exact foreign-key path every time.

---

## Proof 2: Spider 2.0 Lite Public Benchmark

| | |
|---|---|
| **Benchmark** | Spider 2.0 Lite — local SQLite split |
| **Tasks** | 135 real natural-language questions |
| **Schemas** | 30 distinct SQLite databases |
| **Metric** | Table recall @ top-8 vs. official gold tables |
| **Treatment** | OCTO schema world model + coprocessor |

```text
Average table recall: 0.862 (86.2%)
Tasks evaluated: 135 / 135
Databases covered: 30
LLM calls: 0
```

---

## Automation: An LLM-Driven World-Model Training Loop

The enrichment work above was done by hand. The next step is a fully automated
loop:

1. Build world model from schema
2. Evaluate recall on real questions
3. Feed failures to an LLM
4. Apply suggested aliases / semantic types
5. Re-evaluate

One round of this loop, with no GPUs and one GPT-4o-mini call, improved recall:

| Database | Baseline | After 1 LLM round |
|---|---|---|
| superhero | 0.879 | **0.917** (+3.8 pp) |
| financial | 0.881 | **0.903** (+2.2 pp) |

This turns world-model curation from a manual service into a scalable,
metric-driven process.

---

## One-Shot RAG vs. OCTO With a Coprocessor

On the USA_NAMES Spider task, a plain keyword RAG baseline can retrieve the
right column names because the schema descriptions contain matching words. OCTO
matches it only after we enrich the world model with semantic aliases and types:

| System | Tables recalled | Important columns recalled |
|---|---|---|
| One-shot keyword RAG | both | 5/5 (state, gender, year, name, number) |
| OCTO generic world model | both | 4/5 (misses state) |
| **OCTO enriched world model** | both | **5/5** |

The difference is not raw column matching. It is that OCTO returns its
retrievals inside a **structured, auditable control packet** with candidate join
paths, hypotheses, and provenance. RAG gives you a chunk list; OCTO gives you a
reasoning trace.

---

## Why This Matters

| RAG / Multi-RAG / RETRO | OCTO |
|---|---|
| Retrieves text chunks / embeddings | Reasons over typed entities and relations |
| No hard schema constraints | Join paths are deterministic graph traversals |
| Requires re-indexing at petabyte scale | Compact, versioned world models |
| Provenance = chunk list | Provenance = full reasoning trace + control packet |
| Needs fine-tuning or LoRA per domain | Attaches at inference time |
| More data → maybe better | **Better structured data → better correctness** |

---

## The Product Angle

OCTO is a **world coprocessor**: a domain-specific reasoning layer that sits
between enterprise data and any LLM. It turns a general model into a
trustworthy specialist without retraining.

**First beachhead:** text-to-SQL for analytics and BI.

---

<div align="center">

### Ask

**Seed / Series A investment to productize the SQL coprocessor and expand to
biomarkers, compliance, and multi-hop knowledge bases.**

*Live SQL demo:* `PYTHONPATH=src:. python examples/sql_real_demo.py --rebuild` 
*Spider demo:* `python examples/spider_lite_demo.py` 
*Training-loop demo:* `python examples/world_model_training_loop.py --db-id superhero` 

</div>
