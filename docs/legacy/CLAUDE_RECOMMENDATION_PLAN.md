# OCTO — Investment Recommendation & Exact Next Steps

**Date:** 2026-08-03
**Question addressed:** Is this project worth further investment, and if so, what exactly happens next?
**Basis:** `l3_native_run.json` (n=500), `fragment_verification.json`, `checkpoints/gcca/gcca_epoch2.pt`, runner source, and `RAG with ANN.txt` (RETRO-v2 spec).

---

## 1. Recommendation in one line

**Not as currently constructed — but do not stop yet, because one cheap diagnostic separates "architecture is wrong" from "training regime was never implemented," and the evidence now points hard at the second.**

---

## 2. What changed today

Every previous null in this project was *uninterpretable* — broken instruments, inert graphs, hash embeddings substituted for real ones. Failure could not be distinguished from measurement error.

That is no longer true. At n=500, with length-matched decoding and a passing identity control:

```
base        token_f1 0.0749
l3_trained  token_f1 0.0733     delta -0.0016  CI [-0.0045, +0.0007]  includes zero
rag_prompt  token_f1 0.1277     l3 vs rag: -0.0544  CI [-0.0690, -0.0394]  EXCLUDES zero
```

L3 is indistinguishable from base and significantly worse than prompt RAG. **This is the first trustworthy answer the project has produced.**

The measurement apparatus also killed its own most attractive result: the n=20 pilot's +0.1398 lift vanished to −0.0016 once output tokens were matched (48.2 → 10.4). That is the harness working correctly, and it is the project's most durable asset.

---

## 3. Why the L3 null is not yet a verdict on the architecture

Comparing OCTO's Level 3 against the RETRO-v2 specification in `RAG with ANN.txt` — which shares the same core mechanism — reveals that OCTO implemented the **gating skeleton** and none of the **training regime** that makes it work:

| Ingredient | RETRO-v2 spec | OCTO as run |
|---|---|---|
| Alignment examples | 100,000 triplets; 1B–5B tokens | **350 examples** |
| Salient Span Masking | REALM-style: mask entities/dates so the gate *must* open | **absent** |
| Hard-negative distractors | 20% injected, teaches gate to suppress noise | **absent** |
| Retrieval cadence | every 64 tokens during decoding | **once per request** |
| 1-chunk causal offset | `C_i` attends to `R_{i-1}` | **no chunking at all** |
| Chunking | Late Chunking (256-parent / 64-child) | whole-document embeddings |
| RETRO++ hybrid | top-1 in prompt + rest via CCA (+8.6 EM published) | either/or |

**Salient Span Masking is the most likely single cause of α ≈ 0.02.** Without it, the model can answer from parametric memory, so gradient descent has no pressure to open the gate. A near-zero α is the *correct* optimum when the injected memory is never required. Adding more epochs under that regime will drive α toward zero, not away from it.

Compounding this: `supporting_fact_recall` is **0.0395**, so the memory tensor holds near-irrelevant documents; and no GNN is in the path (`run_l3_native.py:287` omits `gnn_encoder`), so the arm named for the RGAT does not contain it.

**Conclusion:** the architecture has not been given a fair test. That is not the same as saying it will work.

---

## 4. The retrieval thesis is in worse shape

Unlike L3, graph retrieval *has* had a fair test. The additive-support fix removed the arithmetic barrier that made expansion impossible — and results still did not improve:

| Family | n | Vector RAG | OCTO Graph |
|---|---:|---:|---:|
| **Overall** | 50 | **0.5744** | **0.5220** |
| Negation | 15 | 0.6227 | 0.4987 |
| Entity | 11 | 0.5400 | 0.4509 |
| Swap | 22 | 0.5518 | 0.5545 |
| Numeric | 2 | 0.6500 | 0.7300 |

Worse on the aggregate and on three of four families; expansion alters results in roughly 1 query in 40. The mechanism now runs and does not help.

The likely reason is upstream: the graph is built from directory names and two regexes, with no facts, no entity resolution, and `participant` + `mentions` (both regex-derived) making up 48% of all edges. **Do not invest further in graph retrieval until extraction is real** — and do not invest in extraction until L3 shows signal, because extraction is the expensive part.

---

## 5. Exact next steps

### Step 0 — Read α from the run currently training (free, today)

α is the readout. The training loop already produces it.

```bash
.venv/bin/python -c "
import torch, math, glob
for p in sorted(glob.glob('checkpoints/gcca/gcca_epoch*.pt')):
    ck=torch.load(p, map_location='cpu', weights_only=False)
    sd=ck['gcca_state_dict']
    al=[float(sd[k].flatten()[0]) for k in sd if 'alpha' in k.lower()]
    print(p, 'max|tanh(a)|=%.4f' % max(abs(math.tanh(a)) for a in al))
"
```

Baseline to beat: **0.0199** at epoch 2.

- **α rises across epochs** → the optimizer is finding signal. Proceed to Step 2.
- **α flat or falling** → gradient descent is reporting that the memory is useless. Go to Step 1 before spending anything further.

### Step 1 — Oracle-memory ablation (~1 day)

The decisive experiment, and the highest-information one available.

Replace the retrieved memory tensor with embeddings of the **gold documents** (`expected_doc_ids`), then retrain the GCCA adapters briefly.

- **α grows** → the bridge works; the bottleneck is retrieval quality (`doc_recall` 0.0395). The architecture is alive.
- **α stays near zero** → a perfect memory tensor cannot open the gate. The injection mechanism is dead on this configuration. **Stop, and write the negative result.**

This single test separates the two hypotheses that "needs more training" currently conflates. Nothing else should be funded before it runs.

### Step 2 — Fix the training regime (~2–3 days), only if Step 0 or 1 is positive

In priority order, from the RETRO-v2 spec:

1. **Salient Span Masking** in `scripts/build_gcca_training_data.py` — mask factual entities and dates in the prompt so the answer is unreachable without the memory. This is the mechanism that forces the gate open.
2. **20% hard-negative distractors** in training batches, so the gate learns suppression rather than blanket trust.
3. **Scale the alignment set** from 350 examples upward. The spec calls for 100,000; even 5,000–10,000 is a 15–30× improvement over current.

### Step 3 — Decision point

If α will not open with oracle memory, salient span masking, and 10× the data, **Level 3 is falsified on this setup**. Publish the negative and stop.

### Parallel track — the methods paper (independent of all the above)

Roughly 80% earned already, needs no GPU, no corpus, and does not depend on whether OCTO works:

- The identity-control protocol (α=0 reproduces base token-for-token, 0 mismatches)
- The length-control result that killed the project's own headline
- Negation-invariance: `fact_coverage` delta of exactly 0.0000 under full negation, ceiling 0.779
- NLI evidence-invariance: +0.826 with *and* without supporting evidence past 512 tokens
- The admissibility finding: expanded candidates won 0/60 queries; required cosine > 1.0 in 45/60

Estimated 5–7 weeks. Venues: NeurIPS D&B, ACM REP, Insights from Negative Results. See `docs/CLAUDE_PAPER_PROPOSAL.md`.

---

## 6. What NOT to spend on yet

| Item | Why not |
|---|---|
| Typed extraction / entity resolution | Weeks of LLM time; unjustified until L3 shows signal |
| Full 511,962-document corpus | Current runs use 10,000; corpus size is not the bottleneck |
| Qwen2.5-72B | Larger model will not open a gate that a 1.5B keeps shut for the same reason |
| Training the RGAT | Pointless while the GNN is not passed to `build_memory_tensor` and memory quality is the binding constraint |
| Graph retrieval improvements | Fair test already run; it did not help |

---

## 7. The harder framing

If the underlying idea is right — structural memory in hidden-state cross-attention is a genuinely unoccupied niche — **this instantiation is not positioned to prove it.** It would need a domain where a real knowledge graph already exists (biomedical ontologies, legal citation networks, code call graphs) rather than one reconstructed from directory names, plus orders of magnitude more bridge-training data.

That is a different project, and worth knowing before funding more of this one.

---

## 8. Bottom line

Finish the training run and read α. Run the oracle-memory ablation. Write the methods paper in parallel, because it is earned regardless of outcome. Spend nothing on extraction, corpus scale, or the 72B until α demonstrates the model can hear the memory at all.

That is roughly **one week to a decisive answer**, against months for the alternative of continuing to build on an unverified foundation.
