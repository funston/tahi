# Legal & Drug-Enforcement Coprocessor Evaluation

Date: 2026-08-01
Model: GPT-4o via `OCTO_LLM_PROVIDER=openai`

## What we built

Two new OCTO world-model coprocessors:

1. **`implementations/legal/`** — legal-reasoning coprocessor built from statutes,
   cases, and regulations. Evaluated on a sample of statutory-reasoning questions.
2. **`implementations/drug_enforcement/`** — controlled-substance coprocessor built
   from DEA schedules, substances, Federal Register scheduling actions, and
   analogue relationships.

Both coprocessors compare:

- **RAG baseline**: dense vector retrieval over chunks + LLM answer.
- **OCTO**: dense retrieval + graph expansion over citations, statutory structure,
  scheduling actions, and analogue relationships + LLM answer.

## Test status

```
python -m pytest tests/
119 passed, 2 warnings
```

New test files:

- `tests/test_legal_coprocessor.py`
- `tests/test_drug_enforcement_coprocessor.py`
- `tests/test_llm_client.py`

## Legal evaluation (n=8)

| Method     | LLM Accuracy | Retrieval Recall |
|------------|-------------:|-----------------:|
| RAG        | 8/8 (100%)   | 3/8 (37.5%)      |
| OCTO       | 8/8 (100%)   | 3/8 (37.5%)      |

The legal sample is small and the questions are straightforward; both methods
answer correctly because the relevant statute is retrieved. The corpus needs to
be enlarged and the questions hardened before this becomes a meaningful
 differentiator.

## Drug-enforcement evaluation (n=8)

| Method     | LLM Accuracy | Retrieval Recall |
|------------|-------------:|-----------------:|
| RAG        | 6/8 (75.0%)  | 5/8 (62.5%)      |
| OCTO       | 7/8 (87.5%)  | 5/8 (62.5%)      |

OCTO improves LLM accuracy by **12.5 points** on this set. The single RAG
failure was a question about fentanyl's schedule; the plain vector retriever did
not surface the `Schedule II` schedule node, while graph expansion in OCTO did.

## Honest caveats

- **Small n**: 8 questions per domain. These are proof-of-concept numbers, not
  leaderboard claims.
- **No hidden test set**: Both evals use questions we authored from public data.
- **Retrieval recall is coarse**: It measures whether the expected answer text
  appears in retrieved evidence, not whether the LLM reasons correctly.
- **Legal questions are too easy**: Need to add harder multi-hop statutory
  reasoning and case-law citation questions.

## How to reproduce

```bash
# Legal
PYTHONPATH=$(pwd):$(pwd)/src python -c \
  "from implementations.legal import evaluate_legal_coprocessor; \
   import json; print(json.dumps(evaluate_legal_coprocessor(), indent=2))"

# Drug enforcement
PYTHONPATH=$(pwd):$(pwd)/src python -c \
  "from implementations.drug_enforcement import evaluate_drug_coprocessor; \
   import json; print(json.dumps(evaluate_drug_coprocessor(), indent=2))"
```

The LLM provider is controlled by environment variables:

```bash
export OPENAI_API_KEY="..."        # or ANTHROPIC_API_KEY
export OCTO_LLM_MODEL="gpt-4o"     # or claude-3-5-sonnet-20241022, etc.
export OCTO_LLM_PROVIDER="openai"  # or anthropic, ollama
```

## Next steps to make this investor-grade

1. **Scale the legal corpus**: ingest real LegalBench tasks (statutory reasoning,
   citation prediction, overruling) instead of our 8-question sample.
2. **Scale the DEA corpus**: scrape Federal Register notices for all scheduling
   actions since 2010; add real HIDTA seizure/formulary data under partner agreement.
3. **Harder questions**: add adversarial questions where the correct answer
   requires combining a schedule action with an analogue relationship.
4. **Add a deterministic baseline**: compare OCTO retrieval recall against BM25
   and against the LLM with no retrieval at all.
5. **Cost benchmark**: measure embedding cost, storage, and query latency versus
   naive RAG and versus fine-tuning a specialist model.
