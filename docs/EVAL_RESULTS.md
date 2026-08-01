# OCTO Evaluation Results

Date: 2026-08-01

## Test status

```
python -m pytest tests/
166 passed, 2 warnings
```

## Evaluations

| Eval | Module | Runner | Output |
|---|---|---|---|
| Legal | `implementations/legal/` | `examples/run_legal_eval.py` | `./results/legal.json` |
| Drug enforcement | `implementations/drug_enforcement/` | `examples/run_dea_eval.py` | `./results/dea.json` |
| HotpotQA | `implementations/hotpotqa/` | `examples/run_hotpotqa_eval.py` | `./results/hotpotqa.json` |
| MuSiQue | `implementations/musique/` | `examples/run_musique_eval.py` | `./results/musique.json` |
| FRAMES | `implementations/frames/` | `examples/run_frames_eval.py` | `./results/frames.json` |

Each runner compares:

- **RAG baseline**: dense vector retrieval over chunks/paragraphs + LLM answer.
- **OCTO**: dense retrieval + graph expansion over citations, structure, and
  relationships + LLM answer.

**Methodology note**: The DEA benchmark was audited and fixed to remove
asymmetric keyword boosting, fix per-question recall reporting, include
negative/distractor examples, and embed all node attributes (common names,
pharmacology, chemical features). A dedicated unit-test suite
(`tests/test_drug_enforcement_scoring.py`, 30 edge cases) now guards the
scorer and retrieval-recall logic.

**Fairness note**: The RAG baseline is now a fully independent
`StandaloneRAG` pipeline (`src/octo/baseline_rag.py`) using
sentence-transformers + FAISS over the same raw documents. It has zero access
to the coprocessor graph, node types, or edge expansion.

## Current results (small bundled samples)

| Eval | n | RAG Accuracy | OCTO Accuracy | Delta | Notes |
|---|---|---:|---:|---:|---|
| Legal | 8 | 100% | 100% | 0.0% | Sample too easy; needs harder statutory reasoning. |
| Drug enforcement | 21 | 85.7% | **90.5%** | **+4.8%** | Expanded corpus with distractors and multi-hop questions; standalone RAG baseline. |
| HotpotQA | 3 | 100% | 100% | 0.0% | Bundled sample only; full HF dataset available. |
| MuSiQue | 3 | 66.7% | 33.3% | -33.3% | Tiny sample; graph expansion added noise here. |
| FRAMES | 3 | 100% | 100% | 0.0% | Tiny sample; needs full dataset. |

**Honest caveats**: these are tiny proof-of-concept samples, not leaderboard
claims. The DEA delta of **+4.8%** comes from adding distractor substances and
multi-hop questions that require traversing analogue/class/action edges. On
simple single-fact questions the standalone RAG baseline already performs well;
the graph advantage appears when vector similarity alone is ambiguous.

## How to reproduce

```bash
# vLLM / local model (recommended for cost)
export OCTO_LLM_PROVIDER=vllm
export VLLM_BASE_URL=http://your-dgx-ip:8000/v1
export OCTO_LLM_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
export VLLM_API_KEY=not-needed

python examples/run_dea_eval.py
python examples/run_legal_eval.py
python examples/run_hotpotqa_eval.py --max-samples 50
python examples/run_musique_eval.py --max-samples 50
python examples/run_frames_eval.py --max-samples 50
```

Or with a cloud provider:

```bash
export OPENAI_API_KEY="..."
export OCTO_LLM_MODEL=gpt-4o
export OCTO_LLM_PROVIDER=openai
python examples/run_dea_eval.py
```

## Dataset notes

- **HotpotQA**: loaded automatically from HuggingFace (`hotpot_qa/distractor`).
  Falls back to a bundled sample if HF is unavailable.
- **MuSiQue**: not on HuggingFace. The runner uses a bundled sample by default.
  Download the full dataset from https://github.com/StonyBrookNLP/musique and
  pass `--path /path/to/musique.json`.
- **FRAMES**: not on HuggingFace. The runner uses a bundled sample by default.
  Download the full dataset from the FRAMES release page and pass
  `--path /path/to/frames.json`.

## Next steps to make this investor-grade

1. **Run full public datasets**: HotpotQA dev (7,405 questions), MuSiQue, FRAMES.
2. **Scale the legal corpus**: ingest real LegalBench tasks instead of the
   8-question sample.
3. **Scale the DEA corpus**: scrape all Federal Register scheduling actions
   since 2010; add HIDTA data under partner agreement.
4. **Tune graph expansion**: MuSiQue suggests too-aggressive expansion can hurt
   on tiny corpora; add per-domain expansion limits and edge-type filtering.
5. **Add deterministic baselines**: compare against BM25 and no-retrieval LLM.
6. **Cost benchmark**: measure embedding cost, storage, and query latency versus
   naive RAG and versus fine-tuning a specialist model.
