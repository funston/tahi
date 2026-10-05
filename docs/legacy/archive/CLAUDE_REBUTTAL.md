# Rebuttal — `docs/TAHI_RESEARCH_PAPER_PROPOSAL.md`

**Date:** 2026-08-03
**Subject:** *TAHI: Latent Relational Graph Attention Networks for Direct Hidden-State Injection in Frozen Large Language Models*
**Method:** Every figure in the proposal was reconciled against the artifacts in `benchmarks/results/`. Sources are named for each claim.

**Artifacts consulted**

| File | Time | Role |
|---|---|---|
| `benchmarks/results/l3_native_run.json` | 10:48 | Sole possible source for Table 1 |
| `benchmarks/results/fragment_verification.json` | 10:40 | Sole possible source for Table 2 |
| `src/tahi/world_state.py:192-246` | — | Additive Structural Support implementation |

---

## Summary

The proposal contains one genuine methodological contribution and one genuine negative result, both of which it under-reports. Its three headline claims do not survive reconciliation with the artifacts:

| Claim | Status |
|---|---|
| "+14.0% F1 over base ($p<0.05$)" | Delta is real; **no p-value was computed**; n=20 is below the project's own minimum detectable effect; confounded by output length |
| "outperforms standard RAG by +9.9% F1" | **The artifact marks this comparison NOT SIGNIFICANT** (CI includes zero) |
| "0.7300 numeric AUC, 22.8% error reduction" | **Computed on 2 negative examples** |

Additionally, **Table 1's absolute values do not match the artifact**, and both tables omit results unfavourable to the thesis — including that overall AUC *declined* and that negation, the paper's own motivating example, fell to chance.

---

## 1. What is genuinely good and should be kept

**Identity control is real and rigorous.** `l3_alpha0` reproduces `base` exactly — delta 0.0, CI [0.0, 0.0], manifest records "IDENTITY CONTROL: PASSED (0 mismatches)". A falsifiable α=0 guarantee verified token-for-token is a real contribution; most work in this space has no equivalent.

**Additive Structural Support is implemented** (`world_state.py:192-246`):

```
score = own_cosine + 0.15 * min(support_count, 5) / min_hops
```

This replaces a multiplicative scorer under which graph candidates were *arithmetically incapable* of entering the result set. Measured before the change, over 60 queries: expanded candidates beat the weakest direct hit **0/60 times**, and in **45/60 queries the cosine required to win exceeded 1.0** — above the maximum the metric can take. Fixing this was necessary and correct.

**The D6 guard is live** — "Degenerate (non-informative) memory on 0 items."

---

## 2. Table 1 does not reconcile with its artifact

`l3_native_run.json` is the only run that could have produced Table 1.

| Arm | Paper F1 | Artifact F1 | Paper Fact Cov | Artifact Fact Cov | Paper EM | Artifact EM |
|---|---:|---:|---:|---:|---:|---:|
| Base | 0.2104 | **0.10478** | 0.1250 | **0.10000** | 0.000 | 0.0 |
| Standard RAG | 0.2516 | **0.14600** | 0.0917 | **0.06667** | 0.050 | **0.0** |
| TAHI L3 GNN | 0.3502 | **0.24457** | 0.1833 | **0.15833** | 0.100 | **0.0** |

Every F1 is inflated by a constant **+0.1056**. Every Fact Coverage by a constant **+0.025**. Exact Match is reported as 0.050 and 0.100 where the artifact records **0.0 for all four arms**.

The *deltas* are preserved — which is why +0.1398 appears in both — but the reported absolutes are not the measured ones. Under standing rule 2 ("Reports are rendered from artifacts, never authored"), Table 1 must be regenerated from `l3_native_run.json`.

---

## 3. The significance claims do not hold

### 3.1 No p-value exists

`$p < 0.05$` appears three times in the proposal. **Every comparison in the artifact records `p_value: None`.** `bootstrap_paired_delta` attaches McNemar only for binary metrics; token F1 is not one, so no p-value was computed for the headline claim.

### 3.2 The comparison against RAG is explicitly null

Key Finding #1 claims TAHI "outperforms standard prompt-concatenated RAG by +9.9% F1." The artifact:

```
rag_prompt[token_f1] vs l3_trained[token_f1]   n=20
delta +0.0986   CI [-0.0048, 0.2056]   NOT SIGNIFICANT
```

The confidence interval includes zero. The proposal's headline comparison against the baseline that matters is null in its own data.

### 3.3 n = 20 is below the project's own detection threshold

`tahi.eval.stats.minimum_detectable_effect(20)` returns **0.2504**. The observed +0.1398 is *below the minimum detectable effect at this sample size*.

`benchmarks/PREREGISTRATION_enterprise_rag.md` already commits to this in advance:

> At n=20 the effect would have to exceed 0.125 to be distinguishable from noise. Per-category numbers are directional colour only.

and

> A delta between 0 and +0.05 with a CI crossing zero is a **NULL**, not a "trend."

`required_n(0.10)` = **126**. The run has 20.

---

## 4. The F1 gain tracks output length exactly

```
base        21.9 tokens  ->  F1 0.1048
l3_alpha0   21.9 tokens  ->  F1 0.1048
rag_prompt  35.6 tokens  ->  F1 0.1460
l3_trained  48.2 tokens  ->  F1 0.2446
```

Perfectly monotonic across all four arms. Token F1 rewards longer answers when gold answers are long. **The most parsimonious explanation of the headline result is that GCCA increases verbosity**, and no arm controls for it.

Two artifact figures reinforce this:

- **`supporting_fact_recall` = 0.05 for every retrieval arm.** Retrieval is finding almost nothing, so the F1 lift cannot be attributed to retrieved evidence.
- **`groundedness`: L3 = 0.271 vs RAG = 0.419.** TAHI's answers are *less* supported by their own evidence than RAG's.

A generation claim requires length-matched arms and a doc recall materially above 0.05, or the mechanism is unattributable.

*(One unreported positive: `abstention_accuracy` is 1.0 for `l3_trained` versus 0.3 for base. At n=20 this is directional only, but it is more interesting than the F1 number and is closer to the actual thesis.)*

---

## 5. Table 2 leads with n = 2

`fragment_verification.json` manifest:

> `Perturbations: {'swap': 22, 'negation': 15, 'entity': 11, 'numeric': 2}`

**The 0.7300 numeric AUC — Key Finding #2, quoted to four significant figures with a "22.8% relative error reduction" — is computed on two negative examples.** The difference from 0.65 is eight pairwise comparisons out of a hundred.

What the same artifact shows and the proposal omits:

| Family | Dense RAG | TAHI | |
|---|---:|---:|---|
| **Overall AUC** | **0.5744** | **0.5220** | TAHI worse |
| negation (n=15) | 0.6227 | **0.4987** | TAHI at chance, worse |
| entity (n=11) | 0.5400 | 0.4509 | TAHI worse |
| swap (n=22) | 0.5518 | 0.5545 | tie |
| numeric (**n=2**) | 0.6500 | 0.7300 | TAHI better |

TAHI is worse on three of four families and on the aggregate.

**Negation is the paper's own motivating example** (§1.2: *"The server is operational" and "The server is NOT operational"*). The NLI evaluator exists specifically to fix negation blindness. TAHI's negation AUC is **0.4987 — chance** — and worse than the dense baseline. The proposal reports the one family where it wins on n=2 and omits the family it was built to fix.

The "2.03× confidence margin" is the true/false gap widening (0.0688 vs 0.0338) while AUC *falls*. Wider spread with worse separability is not greater confidence.

This pattern is precisely what the pre-registration forbids:

> We do not re-cut the data by category, swap the primary metric, or expand N looking for a favourable slice.

Table 2 does all three.

---

## 6. Scale and model are misstated

The abstract claims results "on enterprise multi-hop reasoning benchmarks." Actual configuration, from the manifests:

| | Stated | Actual |
|---|---|---|
| Model | implied production LLM | **Qwen2.5-1.5B-Instruct** (72B-AWQ used elsewhere in the project) |
| Table 1 corpus | "enterprise" | **5,000 docs, 5,837 edges** |
| Table 2 corpus | "enterprise" | **2,000 docs, 2,283 edges** |
| Available corpus | — | 511,962 docs, 956,232 edges |

None of this appears in the proposal. Table 2's corpus is 0.4% of the available data.

---

## 7. Related work gaps

Missing and directly relevant:

- **HippoRAG / HippoRAG 2** (NeurIPS'24, ICML'25) — Personalized PageRank over a KG, the closest prior art to §3.1's Additive Structural Support. Its absence is the most likely single cause of a novelty objection.
- **Zep / Graphiti** (arXiv 2501.13956) — temporal KG with bi-temporal edge invalidation.
- **Think-on-Graph 3.0**, **GraphRAG-Bench** (arXiv 2506.05690), which finds GraphRAG does not universally beat vanilla RAG — directly relevant to framing.

The novelty claim versus GNP and G-Retriever is also overstated. RETRO and InstructRetro already inject into hidden states via chunked cross-attention; the proposal cites them and then claims hidden-state injection as the contribution. The defensible claim is narrower: **graph-structured** memory occupying the cross-attention slot, versus unstructured text chunks.

---

## 8. Venue assessment

NeurIPS / ICLR / ACL would desk-reject. The first reviewer question is sample size; the second is why overall AUC declined; the third is the length confound. n=20 on a 1.5B model with a headline resting on two examples will not survive first-round review, and the Table 1 reconciliation failure would be fatal if noticed.

---

## 9. What can be claimed honestly today

There is a real paper here. It is not this one.

**1. The identity-control protocol.** A falsifiable α=0 guarantee, verified token-for-token, plus the silent-degradation taxonomy already drafted in `research_paper_notes.md`. This is a methods contribution and it is defensible now. Venues: ACM REP, NeurIPS D&B, "Insights from Negative Results."

**2. The negative result on graph expansion.** Multiplicative similarity damping made structural retrieval arithmetically impossible — 0/60 queries could win a slot, impossible in 45/60 — and correcting it moved overall discrimination *down*. That is a genuine, publishable finding about why GraphRAG-style expansion underperforms, and it establishes priority.

**3. A preliminary L3 signal**, stated as a pilot: delta +0.1398, CI [0.0484, 0.2376], n=20, 1.5B model, confounded by output length, with doc recall at 0.05. Motivation for a powered run — not a result.

### To convert (3) into a real claim

| Requirement | Current | Needed |
|---|---|---|
| Sample size | 20 | ≥ 126 (`required_n(0.10)`) |
| Model | Qwen2.5-1.5B | Qwen2.5-72B-AWQ |
| Length control | none | length-matched arms, or a length-invariant metric |
| Doc recall | 0.05 | materially above 0.05, or the mechanism is unattributable |
| p-values | none computed | computed, or drop the `p<0.05` claims |
| Table provenance | authored | rendered from artifacts (standing rule 2) |

---

## 10. Required corrections before circulation

1. Regenerate Tables 1 and 2 from the artifacts. Remove the constant offsets and the non-zero EM values.
2. Delete every `$p < 0.05$` claim, or compute the p-values.
3. State that the RAG comparison (+9.9%) is **not significant**.
4. Report overall AUC (0.5220 vs 0.5744) and negation AUC (0.4987 vs 0.6227) in the body, not only the favourable subgroup.
5. Label the numeric AUC as **n=2**.
6. State the model (1.5B) and corpus sizes (5,000 / 2,000 docs) in the abstract.
7. Add a length-confound analysis or remove the generation claim.
8. Add HippoRAG, Zep/Graphiti, and GraphRAG-Bench to related work; narrow the novelty claim to graph-structured cross-attention memory.
