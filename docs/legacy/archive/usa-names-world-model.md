# Building a Better USA_NAMES World Model

## The problem

On the real Spider task `sf_bq286` (USA_NAMES), the generic TAHI world model
retrieves:

```text
Tables: ['usa_1910_2013', 'usa_1910_current']
Columns: ['number', 'number', 'year', 'name', 'name', 'year', 'gender', 'gender']
```

It finds `gender` because the column description mentions "Sex (M=male or
F=female)", but it **misses `state`**. The query asks about *Wyoming*, and the
schema has a `state` column, but the base world model has no semantic bridge
between the value "Wyoming" and that column.

## The fix: enrich the world model

We add three kinds of metadata to the automatically generated world model:

1. **Semantic type tags** on columns (`gender`, `us_state`, `year`, `person_name`, `count`).
2. **Aliases** that map natural-language values to column names.
 - `state` gets aliases like `"state", "state code"` plus all US state names and codes.
 - `gender` gets aliases like `"sex", "male", "female", "boy", "girl"`.
 - `number` gets aliases like `"count", "occurrences", "frequency"`.
3. **Plain-language summaries** that explicitly mention the values a user might ask about.

The enrichment function lives in
`examples/usa_names_world_model_compare.py`.

## Result

After enrichment, TAHI retrieves all five important columns:

```text
Tables: ['usa_1910_2013', 'usa_1910_current']
Columns: ['number', 'number', 'state', 'state', 'name', 'name', 'year', 'year', 'gender', 'gender']
Important columns found: ['gender', 'name', 'number', 'state', 'year'] (5/5)
```

## Comparison: one-shot RAG vs. TAHI with coprocessor

We also implemented a simple one-shot keyword RAG baseline that retrieves schema
chunks (table summaries + column summaries) by token overlap:

```text
1) One-shot keyword RAG
 Tables: ['USA_1910_2013', 'USA_1910_CURRENT']
 Columns: ['number', 'year', 'name', 'gender', 'state']
 Important columns found: ['gender', 'name', 'number', 'state', 'year'] (5/5)

2) TAHI generic world model
 Tables: ['usa_1910_2013', 'usa_1910_current']
 Columns: ['number', 'number', 'year', 'name', 'name', 'year', 'gender', 'gender']
 Important columns found: ['gender', 'name', 'number', 'year'] (4/5)

3) TAHI enriched world model
 Tables: ['usa_1910_2013', 'usa_1910_current']
 Columns: ['number', 'number', 'state', 'state', 'name', 'name', 'year', 'year', 'gender', 'gender']
 Important columns found: ['gender', 'name', 'number', 'state', 'year'] (5/5)
```

### What this shows

- **Plain keyword RAG can retrieve the right columns** when column descriptions
 happen to contain matching words. It has no structured reasoning, no join
 planning, and no provenance.
- **TAHI with a generic world model is slightly worse** than keyword RAG here
 because the simple hash-based retrieval does not exploit the column
 descriptions as directly as token overlap.
- **TAHI with an enriched world model matches RAG on recall** while keeping the
 structured graph, foreign-key reasoning, hypotheses, and control packet.

The coprocessor value is not raw column retrieval on a trivial schema; it is
that the same architecture scales to multi-table schemas where RAG would miss
bridge tables and join paths.

## The bigger point: world models as labeled, supervised data

Building the coprocessor is analogous to an ML data pipeline:

| ML pipeline step | TAHI world-model step |
|---|---|
| **Crawl** | Connect to database, schema dump, document store, or API |
| **Parse** | Introspect tables, columns, foreign keys, types |
| **Clean / normalize** | Canonicalize identifiers, resolve aliases, compress schema families |
| **Label / supervise** | Add semantic types, domain aliases, evidence documents, rules |
| **Embed / index** | Build graph index + optional ANN embeddings |
| **Evaluate** | Run benchmark tasks, compute recall / execution accuracy |
| **Iterate** | Add more aliases, rules, or documents where the model fails |

The LLM is **decoupled** from the world model. Improve the embeddings, improve
the rules, or improve the ontology, and every LLM that attaches to the
coprocessor gets better — without retraining or LoRA.

## Run the comparison

```bash
python examples/usa_names_world_model_compare.py
```

## Next step

Turn the grounded columns into SQL. With `state`, `gender`, `year`, `name`, and
`number` reliably retrieved, the remaining work is a generic SQL generator that
understands "proportion of X in state S vs total X." That generator can be
written once and reused for any similar demographic table.
