# ROCTO (joint validation harness) + OCTO Endgame Plan

**Date:** 2026-08-03
**Two questions answered:**
1. Is there a codebase we can bring to the RETRO/ANN company to validate their architecture before $10M of hardware?
2. What exactly brings OCTO home — to success or to validated failure?

---

# Part 1 — ROCTO: what we can actually bring

## Short answer

**Yes — but the asset is the verification harness, not the architecture.** We cannot hand them a RETRO implementation. We can hand them the apparatus that tells them whether theirs works, plus documented proof it catches false positives.

## Their Stage 1 asks for three verification tests. We have one, working.

From `RAG with ANN.txt`, Stage 1 "Unit Verification Suite":

| Their test | Status here |
|---|---|
| **Test 1 — Zero-Disruption Identity Check** (α=0 → logits identical to stock base) | ✅ **Built, asserted, and passing at n=500.** 0 mismatches |
| Test 2 — 1-Chunk Offset Leak Check | ❌ Requires chunking; **absent** |
| Test 3 — O(1) KV Memory Bound | ❌ Requires chunking; **absent** |

`benchmarks/run_l3_native.py:22` states the invariant exactly as they'd want it:

> `l3_alpha0` is not filler. `h + tanh(0) * attn == h` exactly, so it MUST equal `base` token for token. If it does not, the harness is wrong and every other [number is void].

Measured at n=500: `l3_alpha0` vs `base`, delta 0.0, CI [0.0, 0.0], across every metric.

## What transfers

| Asset | Location | Value to them |
|---|---|---|
| Verified identity control | `run_l3_native.py`, `gcca_layer.py` | Their Stage 1 Test 1, done |
| 4-arm ablation harness | `run_l3_native.py` | Their "dynamic ablation toggling" requirement |
| Frozen-base adapter training | `scripts/train_gcca.py` | <5% trainable, no catastrophic forgetting |
| Fail-loud preflight | `octo/eval/preflight.py` | Refuses to run degraded |
| Degraded-artifact refusal | `octo/eval/manifest.py` | `validate()` won't write a compromised result |
| Paired bootstrap + power | `octo/eval/stats.py` | CIs, McNemar, `required_n` |
| **Defect taxonomy** | `docs/archive/` | The specific ways this class of system fakes a win |

## The credential that matters

The harness **killed its own most attractive result**:

```
n=20  pilot:  L3 vs base  +0.1398   CI [+0.0484, +0.2376]   "significant"
n=500 length-matched:      -0.0016   CI [-0.0045, +0.0007]   null
                           output tokens equalised 48.2 -> 10.4
```

The entire effect was a verbosity confound. That is a documented case of the apparatus catching a false positive that would otherwise have shipped into a paper. **That is the pitch** — not "we built your thing," but "we have the instrument that tells you if yours works, and here is proof it catches errors."

Add the four failure modes we can show them, each of which would bite them directly:

- **Type-compatible semantic substitution** — a hash embedding matched the encoder's dimensionality, so semantic retrieval was silently replaced by hash retrieval. Nothing raised.
- **Verbosity confound in token F1** — see above.
- **NLI judges going support-invariant past 512 tokens** — +0.826 with *and* without supporting evidence. Their faithfulness metrics will do this.
- **Admissibility failure** — expanded candidates won 0/60 retrieval slots; required cosine exceeded 1.0 in 45/60.

## What ROCTO still needs to build

| Component | Effort | Why |
|---|---|---|
| Chunked CCA + 1-chunk causal offset (`C_i ← R_{i-1}`) | 1–2 weeks | The core of RETRO; genuinely absent (0 references to chunking in `gcca_layer.py`) |
| O(1) KV bound verification | days after chunking | Their Test 3 |
| **Tier 0 harness** — iterative vs single-shot RAG on multi-hop | ~1 week | The kill test nobody has run |
| Salient span masking + 20% distractors | days | Required or the gate has no reason to open |
| **Memory-source toggle: text-ANN vs KG/GNN** | days | `build_memory_tensor(..., gnn_encoder=...)` already provides the seam |

That last row is the elegant part. **ROCTO = one harness, one GCCA, two memory backends.** Same architecture, swap what fills the memory tensor. That is precisely the experiment neither party has run, and it answers both questions at once:

- Does GCCA beat prompt-RAG? (their Claim A, our L3 thesis — *identical risk*)
- Does curated memory beat scale? (our thesis vs their $10M premise)

## Honest caveats before pitching

- We have **no chunked cross-attention**. Do not imply we have a RETRO implementation.
- Everything runs at 1.5B on ≤10k documents. Nothing at their scale.
- The repo's history contains many retracted results. Presented naively that is a liability; presented as "here is how we found and killed our own false positives" it is the entire credential. Lead with it.

---

# Part 2 — OCTO endgame: 6 weeks to a definitive answer

Four gates. Each is pre-registered before running. **Every outcome, pass or fail, is publishable.** No gate is skipped — skipping Tier 0 and Tier 1 and jumping to Tier 2 is exactly how the project got here.

## Week 0 (1 day) — Fix the instrument

Windowed max-pooling in `nli_evaluator.score_pair` instead of `truncation=True, max_length=512`. Without this, Gate D cannot be measured at all.

**Check:** support-present and support-absent must produce different scores. They are currently identical at +0.826.

## Week 1 — GATE A: Can GCCA use a *perfect* memory?

The decisive architecture test. Two changes:

1. Replace retrieved memory with embeddings of the **gold documents** (`expected_doc_ids`) — a perfect truth layer.
2. Add **salient span masking** to `scripts/build_gcca_training_data.py` — mask entities and dates so the answer is unreachable without the memory. Without this there is no gradient pressure to open the gate, and α ≈ 0.02 is the correct optimum.

Retrain adapters. Read α.

| Outcome | Meaning |
|---|---|
| **PASS** — α materially above 0.02, and `l3_trained` > `base` on the structural pool with CI excluding zero | Architecture works. Memory quality is the bottleneck. Proceed |
| **FAIL** — α stays near zero with perfect memory | GCCA cannot use even ideal input. **OCTO L3 is dead, and RETRO-v2's premise is damaged with it.** Stop and publish |

This is the highest-information experiment available and it costs a week.

## Week 2 — GATE B: Tier 0, the test that was never run

`docs/archive/retro-v2-review.md` §6 specified this as the *first* step and it was skipped.

Build a small Wikipedia entity-graph world model. Evaluate on HotpotQA / MuSiQue / 2WikiMultiHopQA against four arms: base, single-shot RAG, iterative RAG, OCTO graph traversal.

| Outcome | Meaning |
|---|---|
| **PASS** — iterative or graph beats single-shot, CI excludes zero | Continuous retrieval is validated. Proceed |
| **FAIL** | Re-retrieving during reasoning does not help. **Both OCTO and RETRO-v2 lose their foundation.** Publish |

## Weeks 3–5 — GATE C: Can a real truth layer be built?

Only if A and B pass. Typed extraction with an ontology and entity resolution, on a scoped corpus (~30–50k documents: all gold docs, dense top-50 per question, plus a distractor sample).

**Gate:** `doc_recall` on the structural pool rises from **0.0395 to > 0.30**. That single number decides whether the truth layer actually holds the answers.

**FAIL** → extraction cannot produce a usable truth layer at acceptable cost. The thesis fails on economics rather than architecture. Publish.

## Week 6 — GATE D: The full thesis

Pre-registered before running. L3 with real extracted memory vs `rag_prompt`, n ≥ 200, length-matched decoding, `nli_fact_coverage` as primary, paired bootstrap 10k, seed 0.

| Verdict | Criterion |
|---|---|
| SUCCESS | delta ≥ +0.05, CI excludes zero |
| NULL | CI includes zero |
| FAILURE | delta ≤ −0.05, CI excludes zero |

Publish either way.

## What NOT to do during these six weeks

| Item | Why |
|---|---|
| Train the RGAT | Pointless until Gate A shows the gate can open; and it still isn't passed to `build_memory_tensor` |
| Scale to 511,962 documents | Corpus size is not the bottleneck; `doc_recall` is |
| Move to Qwen2.5-72B | A larger model will not open a gate a 1.5B keeps shut for the same reason |
| Improve graph retrieval scoring | Already fair-tested after the additive fix; it did not help |

## Why this is bounded

Every gate has a **failure branch that ends the project with a result**, not with another round of remediation. The failure mode this project has repeated — "the measurement was broken, fix it and retest" — is closed off, because the instrument is fixed in Week 0 and each gate is pre-registered before it runs.

Six weeks. Success, or validated failure. Both publishable.
