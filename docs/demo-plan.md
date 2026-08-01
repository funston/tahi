# OCTO Demonstrable Demo Plan

## Goal

Build one concrete, runnable demo that simultaneously proves three claims:

1. **OCTO beats single-shot RAG, multi-hop RAG, and RETRO-style retrieval** on a task where text similarity is insufficient.
2. **A world coprocessor is built from domain data**, not prompt hacking.
3. **A compelling real-world use case** is solved end-to-end with measurable correctness.

## Headline Use Case: Natural Language to SQL on a Real Schema

### Why SQL?

- Every enterprise has a schema that is too large to stuff into a prompt.
- RAG retrieves text chunks about tables; it cannot reliably produce correct joins.
- Wrong joins are expensive and obvious: either the query fails or returns garbage.
- OCTO's graph of tables, columns, and foreign keys turns join-path planning into deterministic graph traversal.

### The Schema

Use the existing `pagila_fixture` snapshot (`src/octo/database.py:452`). It is a realistic DVD-rental schema with:

- 15+ tables
- composite keys
- bridge tables (`film_actor`, `film_category`, `inventory`, `rental`)
- partitioned payment tables

## Demo Narrative Flow

### Scene 1 — The Question (30 seconds)

Ask a natural-language question that sounds simple but requires a multi-hop join:

> "Which customers rented films in the Action category?"

### Scene 2 — RAG Fails (60 seconds)

Show what a RAG-style baseline does:

- Tokenize the question.
- Retrieve top-k tables whose names or descriptions match the keywords.
- It finds `customer`, `film`, `category`.
- It misses the bridge tables `rental`, `inventory`, `film_category`.
- Result: a generated SQL that joins `customer` directly to `category` or hallucinates columns.

### Scene 3 — OCTO Builds the World Coprocessor (60 seconds)

Run `SQLSchemaCoprocessor.from_snapshot()`:

- Ingests the schema into a `WorldModel`.
- Nodes: database, tables, columns, schema families.
- Edges: foreign keys, column membership, schema-family membership.
- This is the **world coprocessor** for the SQL domain.

### Scene 4 — OCTO Reasons (60 seconds)

The coprocessor runs the OCTO cognitive loop:

1. **Capture:** parse question into intent (`selection`) and terms.
2. **Retrieve:** graph-traverse from `customer` and `category` anchors.
3. **Plan:** shortest-path search across foreign-key edges finds the correct join path:
 `customer -> rental -> inventory -> film -> film_category -> category`.
4. **Rule-check:** SQL rule engine emits constraints:
 - `candidate_tables`
 - `candidate_join_path`
 - `recommended_bridge_tables`
5. **Fuse / Inject:** control packet is passed to a small SQL generator or to an LLM.

### Scene 5 — Correct SQL (30 seconds)

The generated query is structurally correct:

```sql
SELECT DISTINCT c.customer_id, c.first_name, c.last_name
FROM customer c
JOIN rental r ON c.customer_id = r.customer_id
JOIN inventory i ON r.inventory_id = i.inventory_id
JOIN film f ON i.film_id = f.film_id
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category cat ON fc.category_id = cat.category_id
WHERE cat.name = 'Action';
```

### Scene 6 — Metrics (30 seconds)

Report:

- **Table recall:** did we retrieve all necessary tables?
- **Join-path accuracy:** is the foreign-key path correct?
- **Bridge-table recall:** did we find the required bridge tables?
- **RAG baseline comparison:** same metrics for the keyword-retrieval baseline.

## Runnable Artifacts

| Artifact | Purpose | Status |
|---|---|---|
| `examples/sql_demo.py` | End-to-end SQL demo with RAG baseline and scoring | **new** |
| `examples/hotpotqa_demo.py` | Multi-hop QA demo on HotpotQA | exists |
| `tests/test_database_coprocessor.py` | Unit tests for SQL schema coprocessor | fixed, passing |
| `scripts/build-world-model.py` | Generic world-model builder from documents | exists |

## Success Criteria

For the SQL demo to be considered proven:

1. OCTO achieves **≥90% join-path accuracy** on a held-out set of 20 NL questions over Pagila.
2. RAG baseline achieves **≤40% join-path accuracy** on the same set.
3. The demo runs end-to-end without a live database, using only the fixture snapshot.
4. The control packet is auditable: a human can read `candidate_join_path` and verify it.

## Optional Live-Database Mode

If a Postgres instance with Pagila is available, add `--execute` to `sql_demo.py`:

- Connect to the database.
- Run the generated SQL.
- Compare row counts against a gold query.

This is not required for the first POC; structural validation is sufficient.

## Why This Beats RAG / Multi-RAG / RETRO

| Approach | What it retrieves | Why it fails on SQL joins |
|---|---|---|
| Single-shot RAG | top-k schema chunks | Cannot plan multi-hop foreign-key paths. |
| Multi-hop RAG | iteratively retrieves chunks | Still text-based; no hard schema constraints. |
| RETRO / ANN | nearest-neighbor chunks from a huge corpus | Requires petabytes of precomputed embeddings; no guarantee of schema correctness. |
| **OCTO** | structured graph of tables, columns, FKs | Deterministic join-path planning; constraints are enforced, not suggested. |

## Next Steps

1. Land `examples/sql_demo.py`.
2. Curate 20 gold NL → SQL question pairs for Pagila.
3. Add an `--execute` path for live Postgres validation.
4. Record a 3-minute screen capture of the demo.
5. Fold the metrics into `docs/octo-vs-rag-retro.md`.
