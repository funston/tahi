# OCTO Real SQL Demo — Honest Metrics

## What this is

`examples/sql_real_demo.py` is a **real, executable** demonstration of OCTO's SQL schema coprocessor. It builds a live SQLite database, generates SQL from natural language using OCTO's schema graph, executes the SQL, and compares the results against gold queries.

No toy metrics. No hand-tuned paths. No fake RAG strawman.

## How it works

1. **Build a live database.** The script creates `/tmp/pagila_real.db` from the existing Pagila fixture snapshot plus deterministic synthetic data (customers, rentals, payments, films, actors, categories, stores, addresses).
2. **Ask real questions.** Four natural-language questions that require multi-table joins.
3. **Generate SQL with OCTO.** The `SQLSchemaCoprocessor` reads the schema graph and emits candidate tables + join paths. A small deterministic generator turns the control packet into SQL.
4. **Generate SQL with a keyword-RAG baseline.** The baseline retrieves top-k tables by keyword overlap and naively chains them. This is a real baseline, not a deliberately broken one.
5. **Execute everything.** Gold SQL, OCTO SQL, and RAG SQL are all run against the live database.
6. **Report observed metrics.** Execution success, exact result-set match, row-count match.

## The questions

| # | Question | Why it is hard |
|---|---|---|
| 1 | How many customers have rented films? | Needs `customer → rental` bridge. |
| 2 | How many actors have appeared in comedy films? | Needs `actor → film_actor → film → film_category → category`. |
| 3 | How many rentals have a payment recorded? | Needs `rental → payment` join. |
| 4 | How many customers live at the same address as a store? | Needs `customer → address ← store` bridge. |

## Run it

```bash
PYTHONPATH=src:. python examples/sql_real_demo.py --rebuild
```

## Observed results

```text
OCTO exact match: 4 / 4 (100%)
RAG exact match: 0 / 4 (0%)
OCTO execution: 4 / 4 (100%)
RAG execution: 3 / 4 (75%)
```

OCTO generates SQL that returns the **exact same result** as the gold query on every question. The RAG baseline either fails to form a join or generates SQL with invalid columns.

## What the metrics actually mean

| Metric | Meaning |
|---|---|
| **Exact match** | The generated query returned the same rows/columns as the gold query. |
| **Execution success** | The generated query ran without a SQL error. |
| **Row-count match** | The generated query returned the same number of rows as the gold query. |

These are **observed**, not estimated or extrapolated. The comparison is done by executing the SQL, not by string similarity.

## Honest limitations

- **Synthetic data.** The database is generated, not the full Pagila dataset. It is large enough to exercise joins but small enough to run instantly.
- **Curated questions.** The four questions were chosen because they require bridge tables that keyword retrieval typically misses.
- **Schema-grounding focus.** The demo measures whether OCTO finds the right tables and join paths. It does not claim open-ended natural-language SQL generation on arbitrary schemas.
- **Deterministic generator.** The SQL generator is small and rule-based. In a production system the control packet would guide an LLM that writes the final SQL.

## Why this is better than the old tier-0 test

The old `scripts/claude_tier0_test.py` was a 3-node hand-built graph with a fake keyword baseline and a hard-coded two-hop walk. It proved the *idea* of graph traversal but was not evidence.

This demo proves the *implementation*: OCTO reads a real schema, plans real joins, and produces SQL that executes correctly against real data.
