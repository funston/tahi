# SQL Grounding Benchmark Report

Primary artifact:

- [sql_grounding_report.html](/Users/richiek/work/bender/benchmarks/sql_grounding_report.html)
- [sql_grounding_report.svg](/Users/richiek/work/bender/benchmarks/sql_grounding_report.svg)

Included benchmarks:

- [benchmarks/bird/tiny_grounding_report.json](/Users/richiek/work/bender/benchmarks/bird/tiny_grounding_report.json)
- [benchmarks/gretel/train_100_grounding_report.json](/Users/richiek/work/bender/benchmarks/gretel/train_100_grounding_report.json)

The JSON files are the reproducibility layer. The HTML report is the human-facing artifact.

Headline results:

- BIRD tiny:
  - `naive_lexical`: `0.100`
  - `schema_only`: `0.900`
  - `bender`: `0.900`
  - `bender_with_evidence`: `1.000`
- Gretel train `[:100]`:
  - `naive_lexical`: `0.590`
  - `schema_only`: `0.770`
  - `bender`: `0.770`

Interpretation:

- BIRD shows a real BENDER win when the system consumes the task evidence field through the world-coprocessor path.
- Gretel is a useful fast add-on benchmark, but on the current sample BENDER matches the schema-only grounding baseline rather than exceeding it.
- These are grounding benchmarks, not end-to-end SQL execution benchmarks.

External reference points:

- BIRD official overall leaderboard:
  - AskData + GPT-4o: `77.64` dev / `81.95` test execution accuracy
  - human performance: `92.96` dev
- BIRD official single-model leaderboard:
  - Q-SQL: `72.99` dev / `76.47` test execution accuracy
  - Gemini-SQL: `72.62` dev / `76.63` test execution accuracy
- Gretel:
  - no public official leaderboard was found
  - dataset card evidence instead:
    - `105,851` records
    - `100,000` train / `5,851` test
    - GPT-4 judge comparison vs `b-mc2/sql-create-context` reports `+54.6%` SQL standards, `+34.5%` SQL correctness, and `+8.5%` adherence

Important:

- the BIRD official numbers above are execution accuracy
- this BENDER report is currently grounding accuracy
- they are not directly comparable

Legend:

- `naive_lexical`: simple lexical table matching baseline with no world model
- `schema_only`: BENDER schema coprocessor over parsed schema only, with no enriched world metadata
- `bender`: BENDER world-model grounding with enriched metadata/documents, but no extra task evidence injected
- `bender_with_evidence`: BENDER world-model grounding plus the dataset's task evidence field injected into the query path
