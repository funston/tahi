# Feedback: "Where OCTO Wins" Summary

**Date:** 2026-08-03
**Subject:** Review of the plain-English summary claiming OCTO wins on (1) fact retrieval and (2) Level 1 prompting, with Level 3 "needing more training."
**Method:** Each claim checked against `benchmarks/results/*.json`, `checkpoints/gcca/gcca_epoch2.pt`, and the runner source. Provenance given for every counter-figure.

---

## Verdict

| Claim | Verdict |
|---|---|
| 1. Kùzu graph engine finds better information than vector RAG | **Contradicted** — OCTO is worse on the aggregate and on 3 of 4 perturbation families; the cited win rests on n=2 |
| 2. OCTO Level 1 prompting beats base (0.075 → 0.128 F1) | **Numbers correct, attribution wrong** — that arm is the dense baseline, and the run contains no graph-vs-no-graph contrast |
| 3. Level 3 needs more training | **Right conclusion, unverified diagnosis, major omission** — L3 is also *significantly worse than RAG*, and there is no GNN in the Level 3 path at all |
| — | **Omitted entirely:** the n=500 run falsified the pilot's headline result |

Three of the four headline numbers do not survive contact with the artifacts.

---

## Claim 1 — "OCTO's graph engine finds better, more accurate information"

**Cited:** 0.7300 AUC on numeric claims vs 0.6500 for vector RAG (+8.0%, "22.8% error reduction"), and a "2.03× wider margin."

**The numeric AUC is computed on two negative examples.** From the `fragment_verification.json` manifest:

> `Perturbations: {'swap': 22, 'negation': 15, 'entity': 11, 'numeric': 2}`

The full table from the same artifact:

| Family | n | Vector RAG AUC | OCTO Graph AUC | |
|---|---:|---:|---:|---|
| **Overall** | 50 | **0.5744** | **0.5220** | OCTO worse |
| Negation | 15 | 0.6227 | 0.4987 | OCTO worse, at chance |
| Entity | 11 | 0.5400 | 0.4509 | OCTO worse |
| Swap | 22 | 0.5518 | 0.5545 | tie |
| Numeric | **2** | 0.6500 | 0.7300 | OCTO better |

OCTO loses on the aggregate and on three of four families. The single win is the smallest sample in the file. Selecting it and omitting the rest is the exact practice `benchmarks/PREREGISTRATION_enterprise_rag.md` forbids in advance:

> We do not re-cut the data by category, swap the primary metric, or expand N looking for a favourable slice.

**The "2.03× confidence gap" inverts its own meaning.** The true/false gap widened (0.0338 → 0.0688) while **AUC fell** (0.5744 → 0.5220). AUC *is* the discrimination measure. Wider spread with worse ranking is not better fact-finding — it is a broader distribution that separates less well.

**Independent corroboration that the graph is barely acting:** measured earlier, 39 of 40 queries returned identical result sets with and without graph expansion, and 100 of 100 fragments scored bit-identically across the two arms.

---

## Claim 2 — "OCTO Text Prompt RAG: 0.128 F1 vs 0.075 base"

**The numbers are correct.** From `l3_native_run.json` (n=500):

```
base        token_f1 0.0749
rag_prompt  token_f1 0.1277
delta +0.0528   CI [+0.0378, +0.0675]   excludes zero
```

That is a real, significant, well-powered result.

**But it is the baseline's result, not OCTO's.** `benchmarks/run_l3_native.py:18` defines the arm in its own docstring:

> `rag_prompt   dense top-k pasted into the prompt   (Level 1 baseline)`

Further, all four arms share a **single** retrieval call (`run_l3_native.py:287`), so this run contains no dense-only versus graph-expanded contrast. There is nothing in it that can attribute any part of the gain to the graph.

Combined with Claim 1's finding that graph expansion alters retrieval in roughly 1 query in 40, the honest reading is: **retrieval beats no retrieval.** That is the founding result of RAG (Lewis et al., 2020), and relabelling the dense baseline as "OCTO RAG" claims the baseline's win for the product.

---

## Claim 3 — "Level 3 needs more training"

**The conclusion is right.** L3 is indistinguishable from base at n=500:

```
base       token_f1 0.0749
l3_trained token_f1 0.0733
delta -0.0016   CI [-0.0045, +0.0007]   includes zero
structural pool (n=170): delta exactly 0.0000
```

**The α claim checks out.** Read directly from `checkpoints/gcca/gcca_epoch2.pt`:

```
7 alpha params: 0.00828, 0.01096, 0.00899, 0.01059, 0.01080, 0.01200, -0.01986
max |tanh(alpha)| = 0.0199        (~2% gate)
```

### What the summary omits

**1. L3 is significantly *worse* than prompt RAG**, not merely equal to base:

```
rag_prompt vs l3_trained   token_f1        delta -0.0544  CI [-0.0690, -0.0394]  excludes zero
rag_prompt vs l3_trained   fact_coverage   delta -0.0425  CI [-0.0602, -0.0257]  excludes zero
```

**2. There is no GNN in the Level 3 path.** `benchmarks/run_l3_native.py:287`:

```python
memory = build_memory_tensor(state, wm, max_slots=args.max_slots,
                             device=args.device)
```

No `gnn_encoder` argument. It defaults to `None` (`src/octo/native/memory.py:43`), the guard at `memory.py:117` is false, and the function returns L2-normalised **sentence-transformer embeddings**. The manifest confirms: `encoder = "sentence-transformers (d=384)"`.

The summary describes Level 3 as injecting "graph vectors" into hidden layers. It injects dense text embeddings. `SubgraphRGATEncoder` remains referenced only by its own file, its own test, and an unused parameter — and still has no training script.

### Why "needs more training" is unverified

It is one hypothesis among at least four, and the artifacts do not distinguish them:

1. Under-training (the summary's claim).
2. **The GNN is absent** — the arm is not testing the architecture it is named after.
3. **`supporting_fact_recall` = 0.0395** — retrieval finds almost nothing, so the memory tensor holds near-irrelevant documents. A perfectly trained bridge over useless memory still yields nothing.
4. **α may be small because training found the memory unhelpful.** A near-zero gate is the correct optimum when the injected signal carries no usable information. Under this reading, more epochs would drive α further toward zero, not away.

Distinguishing (1) from (4) requires an oracle-memory ablation — inject gold-document embeddings and check whether α grows. Until that runs, "needs more training" is an assumption.

---

## The omission that matters most

**The n=500 run falsified the pilot's headline result.**

| | Pilot (n=20) | Current (n=500) |
|---|---:|---:|
| L3 vs base, token F1 | **+0.1398**, CI [+0.0484, +0.2376] | **−0.0016**, CI [−0.0045, +0.0007] |
| Base output tokens | 21.9 | 10.404 |
| L3 output tokens | 48.2 | 10.366 |

In the pilot, token F1 tracked output length monotonically across all four arms. Once decoding length was matched — the control specified in the paper's own §5.3 — **the entire effect vanished.**

This is a clean, well-powered confirmation that the pilot result was a verbosity artifact. It is genuinely good science: the harness caught its own false positive before publication, which is more than most projects manage. It belongs at the top of any honest summary, and it is absent from this one.

---

## Honest scorecard

| Component | Status |
|---|---|
| Graph retrieval | **Not supported.** Worse overall AUC (0.5220 vs 0.5744), worse on 3/4 families, alters results in ~1/40 queries |
| Level 1 prompt RAG | **Works — and it is the baseline.** Retrieval beats no retrieval; no graph attribution is available from this run |
| Level 3 GCCA | **Falsified as configured.** Indistinguishable from base, significantly worse than RAG, at n=500 |
| Identity control | **Genuinely solid.** 0 mismatches; α=0 reproduces base token-for-token |
| RGAT / GNN | **Not built.** Untrained, unwired, and absent from the arm named after it |
| Measurement discipline | **Improved and working.** The length control did its job and killed a false positive |

---

## What would have to be true for the summary's claims to hold

| Claim | Requirement |
|---|---|
| Graph finds better information | Overall AUC above the vector baseline, with per-family n ≥ 30. Currently 0.5220 vs 0.5744 with n=2 on the cited family |
| Level 1 is an OCTO win | A dense-only arm alongside the graph-expanded arm, with the delta attributable to expansion. Currently one shared retrieval call |
| Level 3 needs more training | An oracle-memory ablation showing α grows when the memory is known-good. Otherwise (3) and (4) above remain live |

None of these are expensive. The oracle-memory ablation in particular is the highest-information experiment available and would settle the Level 3 question in roughly a week.

---

## Closing note

The measurement apparatus is now doing its job — it caught and killed the project's own most attractive result. That is the asset worth protecting. Summaries that read every branch in the most favourable direction available spend that asset, because the artifacts are in the repository and anyone can open them.
