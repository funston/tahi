# OCTO on BIRD Dev — Real, Harder Benchmark Metrics

## What this is

`examples/bird_table_recall.py` evaluates OCTO's SQL schema coprocessor on
the full **BIRD dev set**: 1,534 natural-language-to-SQL questions across **11
real SQLite databases**. It measures **table recall @ top-8**: did OCTO's
candidate tables include every table the gold SQL uses?

BIRD is harder than Spider Lite because:

- Questions often require domain evidence (e.g., "eligible free rate").
- Schemas are realistic and irregular.
- Column names are verbose and sometimes contain spaces.
- Some databases have many tables and no foreign-key constraints.

## Dataset

| Property | Value |
|---|---|
| Benchmark | BIRD dev |
| Tasks evaluated | 1,534 |
| Databases | 11 distinct SQLite schemas |
| Gold signal | Gold SQL → parsed table names |
| Metric | Table recall = \|gold ∩ predicted\| / \|gold\| |

## Run it

```bash
# Full dev set
python examples/bird_table_recall.py

# Single database (e.g., the hardest one)
python examples/bird_table_recall.py --db-id superhero
```

## Observed results

Run with `top_k=8`:

```text
BIRD dev — 1534 tasks evaluated
Tasks with gold tables: 1534
Average table recall @ top-8: 0.951
```

### Per-database recall

| Database | Tasks | Avg. table recall |
|---|---|---|
| california_schools | 89 | 0.949 |
| card_games | 191 | 0.988 |
| codebase_community | 186 | 0.984 |
| debit_card_specializing | 64 | 0.977 |
| european_football_2 | 129 | 0.979 |
| financial | 106 | 0.881 |
| formula_1 | 174 | 0.917 |
| student_club | 158 | 0.969 |
| superhero | 129 | 0.875 |
| thrombosis_prediction | 163 | 0.949 |
| toxicology | 145 | 0.972 |

## What the metrics mean

- **Table recall @ top-8** — Of the tables used in the gold SQL, what fraction
 appear in OCTO's top-8 candidate tables?
- These are **observed** by running the coprocessor against every BIRD dev
 question, not estimated.
- No LLM calls are made; the coprocessor runs from the schema world model.

## Honest limitations

- **Table selection, not full SQL generation.** The script measures whether
 OCTO retrieves the right tables. It does not generate or execute the final
 SQL.
- **financial and superhero are harder.** These two databases have the lowest
 recall (88.1% and 87.5%). They are good targets for improving the world model
 with domain aliases and evidence documents.
- **Foreign keys are sparse.** Many BIRD SQLite files declare no foreign keys,
 so the world model has fewer join-path edges than in Pagila or Spider Lite.

## Why this matters

BIRD is a recognized, realistic NL→SQL benchmark. Getting **95.1% table recall**
across 11 diverse schemas without fine-tuning or LLM calls shows that OCTO's
world-model approach generalizes to harder, real-world schemas. The remaining
~5% is a concrete improvement target, not hand-waving.

## Files

- Demo script: `examples/bird_table_recall.py`
- Spider Lite demo: `docs/spider-lite-demo.md`
- Investor slide: `docs/investor-proof-slide.md`
