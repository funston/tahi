# TAHI — Analysis

**Date:** 2026-08-03
**Scope:** State of the system, why every measurement to date is uninformative, and the ordered plan to fix it.
**Method:** Every number below was produced by running code in this repo during the analysis. Claims that were inferred rather than measured are marked as such.

---

## Bottom line

TAHI's thesis is that a structured world model makes an LLM assert fewer false things than plain vector RAG.

For that to be **testable**, three things must be true:

1. There is a real knowledge structure.
2. Retrieval actually uses it.
3. There is a valid instrument for "false things."

**All three are false today.** That is why every number in this project's history is void or null. Not one has been a test of the thesis.

The three failures are **independent**. Fixing any one alone still yields an uninterpretable number — which is why past results kept needing retraction.

---

## Architecture decision: OWL removed, Graph Neural Network adopted

W3C semantic-web tooling (OWL 2, SHACL, RDF triplestores) was evaluated and **rejected**. It was briefly implemented, never wired into the runtime, and has been removed.

**Why it was rejected:**

- Ontology engineering is the documented cost sink of exactly this kind of project — and the architecture docs already name it as TAHI's dominant cost.
- OWL RL materialisation does not survive the corpus scale here (5–20M triples).
- It solves formal consistency, which was never the bottleneck. The bottleneck is retrieval and representation.

**Removed:**

| Item | Size |
|---|---|
| `src/tahi/graph/owl_ontology.py` | 85 L |
| `tests/test_owl_ontology.py` | 51 L |
| `data/ontologies/enterprise_rag.ttl` | 54 L |
| packages `pyshacl`, `rdflib`, `owlrl`, `prettytable` | ad hoc, never declared in `requirements.txt` |

Blast radius was zero — grep across `src`, `tests`, `benchmarks`, `scripts`, `implementations` found these referenced only by the two files deleted.

**Replaced with:** an AI-driven Graph Neural Network architecture.

```
Unstructured corpus ──► auto-extracted subgraph ──► Kùzu graph engine
                                                          │
                                                          ▼
                                       Relational Graph Attention Network (RGAT)
                                            src/tahi/graph/gnn_encoder.py
                                                          │
                                                          ▼
                                       Topological memory tensor [1, K, d]
                                            src/tahi/native/memory.py
                                                          │
                                                          ▼
                                       GCCA cross-attention (Level 3)
                                            src/tahi/native/gcca_layer.py
```

This is the right target because Level 1 — graph content compiled into the prompt — is commodity GraphRAG, shipped by Microsoft, LlamaIndex, Neo4j, Glean and Onyx. `INVESTMENT_ANALYSIS_TAHI_GARDENS.md` already concedes this. Injecting graph *structure* into hidden states via cross-attention is the part nobody ships.

The design is a published pattern, not a bet: **Graph Neural Prompting** (AAAI'24) is nearly the same diagram, and supplies the training objective — self-supervised **link prediction**, so the 956,232 existing edges are the training set and no labels are required. **G-Retriever** and **GraphToken** are the same family; the literature splits them into projector-based and cross-attention-based, and GCCA is the cross-attention branch.

---

## Precondition 1 — The knowledge structure is not one

Edges come from filesystem layout plus two regexes (`implementations/enterprise_rag/world_model.py:36-39`):

```python
TICKET_RE  = re.compile(r"\b([A-Z][A-Z0-9]{1,9})-(\d{1,6})\b")
SPEAKER_RE = re.compile(r"^([A-Z][a-zA-Z]{1,20})(?=:\s)", re.MULTILINE)
```

- `participant` and `mentions` — **48% of all 956,232 edges** — come from `^Name:` and `[A-Z]+-\d+`. They are the two lowest-precision edge types and the largest.
- **There are no facts.** `dst` is always a node id, never a value (`kuzu_store.py:70-78`). Attribute values live in a Python dict outside the graph.
- **No entity resolution.** `person::Marco` (Slack speaker regex) and `marco@corp.com` (gmail container) are two different nodes, so cross-source joins — the entire multi-source premise — silently fail.
- **Relation type is discarded at scoring time** (`world_state.py:170,176` — `_rel` is unused). An `in_project` edge is weighted identically to a regex-derived `participant` edge.

---

## Precondition 2 — Retrieval cannot use the graph

**This is the root cause of every null result, and it predates and outlives defect D1.**

Two different quantities are sorted in one list. A direct hit keeps its FAISS score (`0.7·1/(1+L2) + 0.3·token_overlap`). An expanded candidate is scored (`world_state.py:199`):

```python
scored.append((node_id, sim * candidates[node_id]))
# candidates[node_id] = seed_score × decay      (1 hop)
#                     = seed_score × decay²     (2 hops through an entity)
```

So `expanded_score = own_cosine × seed_score × decay`. Since `seed_score` is itself a direct-hit score (~0.5) and `decay` is 0.9, **every expanded candidate is multiplied by ~0.45 before competing against unscaled direct scores.**

### Measured, 3,000 docs / 6,782 edges (2.3 edges/doc — the graph is not degenerate)

```
direct top-5 scores : 0.497, 0.453, 0.444, 0.425, 0.425
expansion candidates: 5 produced, best 0.178, then 0.138, 0.136, 0.135, 0.128

40 queries: identical result sets 39/40
            total slots gained by expansion: 3
```

Expansion **does** produce candidates. They lose, and not marginally — the best expanded candidate is 2.4× below the *weakest* direct hit. For that query, winning a slot required cosine ≥ 0.950.

### Generalised over 60 queries — the finding is definitive

```
queries with expansion candidates : 60 / 60
mean weakest DIRECT slot score    : 0.474
mean best EXPANDED candidate score: 0.185
expanded beat weakest direct      : 0 / 60
mean required cosine to win       : 0.992
required cosine > 1.0 (IMPOSSIBLE): 45 / 60
```

Every query produced expansion candidates. **Not one of 60 ever beat even the weakest direct hit.**

And in **45 of 60 queries the required cosine exceeds 1.0** — above the maximum value cosine similarity can take. In three quarters of queries, no graph-reached document can win a retrieval slot *no matter how relevant it is*. This is not a tuning problem or a weak effect. It is arithmetically impossible for the graph to influence retrieval.

### It is a trap, not a mis-tuned threshold

The graph's purpose is to surface documents relevant *because of structure* — the Slack thread and the Jira ticket joined by `INC-2026-0142`, sharing no vocabulary with the question. But the score is dominated by the candidate's own similarity to the query:

- **Similar to the query** → dense retrieval already found it → excluded as a duplicate. Expansion adds nothing.
- **Not similar to the query** → low cosine → `cosine × 0.45` is tiny → loses every slot.

Both branches lose. The only documents expansion can contribute are ones dense retrieval would have found anyway.

Tuning cannot fix it. Setting `decay = 1.0` removes only the 0.9; the `seed_score` factor still demands ~2× the similarity. Dropping `seed_score` too leaves a raw cosine compared against FAISS scores on a different scale. **The formula has to change shape, not value.**

### Where it came from

The docstring states the intent plainly (`world_state.py:157-165`): candidates are damped "so an expanded candidate can only outrank a direct vector hit when it is genuinely similar to the query," added because a hub entity "would otherwise flood the results; that is the shape of the `conflicting_info` collapse (doc_recall 0.450 -> 0.175)."

That was a real fix for a real problem — hub flooding from the regex edges. But the cure was to make expansion unable to compete. **D1's fix made edges produce candidates; the anti-flooding guard added in the same change guaranteed they lose.** Net retrieval effect: unchanged from before D1 was "fixed."

---

## Precondition 3 — There is no valid instrument

### The lexical metric is polarity-blind

`fact_coverage` is content-word set overlap (`src/tahi/eval/faithfulness.py:81-102`). Measured over all 500 questions:

| Check | Result |
|---|---|
| Gold answer scored against its own `answer_facts` | **0.779** — fails 22% of the time on a provably perfect answer |
| Same, on the pre-registered structural pool (n=170) | 0.754 |
| Same, after negating every gold answer (`is` → `is not`) | **0.7792 — delta exactly 0.0000** |

`not` is both a stopword and ≤2 characters, so it is stripped twice over. **This affects the pre-registered *primary* metric, not only the secondary** — a wider scope than previously recorded.

### The NLI replacement is support-blind on real inputs

`src/tahi/eval/nli_evaluator.py` tokenizes with `truncation=True, max_length=512`. Measured:

```
support present, ~1900 tok  ->  truth_score +0.826
support ABSENT,  ~1900 tok  ->  truth_score +0.826   <- identical
support absent,  short      ->  truth_score -0.001   <- correct
```

Past ~512 tokens **the score is invariant to whether the evidence supports the claim.** The model is correct on short inputs and degenerates to a fixed value on the inputs this benchmark actually feeds it (5 docs × 1500 chars ≈ 1900 tokens).

### What the re-run therefore says

| | lexical (prev) | NLI (now) |
|---|---:|---:|
| **overall AUC** | 0.5617 | **0.4812** ← below chance |
| negation | 0.4492 | **0.6107** |
| numeric | 0.5805 | 0.3900 |
| entity | 0.5938 | 0.3800 |
| swap | 0.5938 | 0.4518 |

`mean_true = −0.080`, and **100/100 fragments scored bit-identically across the graph and no-graph arms** (delta 0.0, CI [0.0, 0.0]).

NLI genuinely helps on negation — the first time polarity has been visible at all. Everything else is unsafe until the windowing defect is fixed.

The run is also underpowered: n=100 (was 300), 10k docs (was 40k), with per-family negatives of numeric **2**, entity 11, negation 15. The numeric AUC of 0.39 is computed on two items.

---

## Status of what has landed

| Component | Tests | Reachable from runtime? | Trained? |
|---|---|---|---|
| `nli_evaluator.py` | pass | **yes** | n/a — but support-blind past 512 tokens |
| `gnn_encoder.py` (RGAT) | pass | **no** — referenced only by its own test and `memory.py`'s signature; no caller passes it | **no** — no training script exists |
| `owl_ontology.py` | passed | no | n/a — **removed** |
| D9 native hook | pass | yes | — genuinely fixed, xfails gone |

Three components landed with passing tests; two were reachable from nothing but their own tests. **Passing fixture unit tests is not evidence a subsystem works.**

### Additional defects found in the GNN path

- **Relation indices are unstable per query** (`native/memory.py:79`): `rel_type_map.setdefault(rel, len(rel_type_map) % 16)` rebuilds the map on every call, so `participant` receives weight matrix 2 in one query and 0 in another. Relation-specific weights are applied to different relations per query, which destroys the *R* in RGAT even after training. `% 16` also aliases silently; the graph has 18 relation types.
- **`w_relation[edge_type]` materialises `[E, in, out]`** — 1.18 GB at E=1000, 5.9 GB at E=5000 on layer 2. *(arithmetic on the shape, not a measured OOM)*
- **Two Python `for i in range(num_nodes)` loops** each masking all E edges — O(K·E) at interpreter speed, the same shape as the already-fixed D3.
- **D4's character-sum hash is back in a fallback path**: `inject()`'s `elif state.retrievals` branch builds slots with `embed_text` = `sum(ord(char)) % width` (`retrieval/legacy.py:16`).
- **The GCCA gate is near zero**: `max |tanh(α)| = 0.028` ≈ a 3% contribution. A perfect topological memory tensor barely reaches the model.

---

## Plan

Order is forced by dependency. Each stage has a cheap gate that decides whether to proceed.

### Stage 1 — Instrument (~1 day, no GPU)

Chunk evidence into windows and max-pool the NLI score instead of truncating at 512. Add thresholds; pin model and revision in the run manifest.

- **Gate:** support-present and support-absent must produce *different* scores (identical today), and negation AUC ≥ 0.80.
- **If it fails:** no off-the-shelf NLI model works on this prose — a real result, and it points at structured contradiction detection instead.

### Stage 2 — Retrieval scoring (~2 days)

Replace the multiplicative scorer with structural support: count of distinct seeds reaching a candidate, hop distance, relation-type weight — combined **additively** with a rank-normalised similarity. Handle hubs with a degree penalty or relation-type filter, not by damping everything.

`KuzuGraphStore.expand()` (`kuzu_store.py:146`) already returns `count(DISTINCT a.id) AS support` and is wired to nothing.

Add `provenance: dense | structural` and per-query slot counts to every result, and write retrieved ids into the artifact — nothing in the harness could have caught the 100/100 identical arms.

- **Gate:** structural slots > 0, and result sets differ from vector-only.
- **If it fails:** the existing graph carries no retrievable signal — worth knowing after two days rather than after a corpus rebuild.

### Stage 3 — Knowledge structure (weeks, LLM-bound)

Typed extraction replacing regex edges. Entity resolution. Facts with values and validity intervals.

Scope to ~30–50k documents first (gold docs + dense top-50 per question + a distractor sample). All 511,962 documents through LLM extraction is ~160 h even at 8-way concurrency.

- **Gate:** Stage 2's gate re-run on the typed graph, plus extraction rejection rate and entity merge counts reported as artifacts.
- **Kill criterion:** if Stage 2's gate still fails on a properly extracted graph, the structural thesis is dead for this corpus. Publish it.

### Stage 4 — GNN + GCCA (weeks)

Only interpretable after 1–3. Train the RGAT on self-supervised link prediction. Actually pass it to `build_memory_tensor` — nothing does today. Fix the relation→index map, the per-edge weight materialisation, and the Python loops. Then fix the injection bottleneck at `tanh(α) = 0.028`.

- **Gate:** link-prediction AUC reported **per relation type** (predicting `in_channel` from directory structure is trivial and proves nothing); `tanh(α)` materially above 0.028; and `run_l3_native.py`'s α=0 arm reproduces base token-for-token — it has never been executed.

### Effort

| Stage | Effort | Blocking |
|---|---|---|
| 1 Instrument | ~1 day, no GPU | Yes — nothing is measurable without it |
| 2 Retrieval scoring | ~2 days | Yes — decides whether Stage 3 is worth funding |
| 3 Knowledge structure | Weeks, LLM-bound | Yes, for Stage 4 |
| 4 GNN + GCCA | Weeks | The differentiator; last because least interpretable alone |

**Stages 1 and 2 together are ~3 days** and answer the question this project has been unable to answer for months: *does this graph carry retrievable signal at all?*

---

## What to stop doing

1. **Marking subsystems "COMPLETE & PASSED" on fixture unit tests.** Every subsystem needs an integration check: *is this reachable from the runtime?* Two of three components that landed today were not.
2. **Deleting acceptance gates after they fail.** The AUC > 0.95 negation / > 0.90 overall gate was in the remediation plan, is now absent from it, and the measured values are 0.611 / 0.481.
3. **Reporting deltas without provenance.** The graph and no-graph arms were bit-identical for 100/100 fragments, and the artifact does not record retrieved ids, so the harness could not have caught it.

---

## Confidence in these findings

Measured by running code in this repo during the analysis:

- `fact_coverage` ceiling 0.779 and negation delta 0.0000
- NLI support-blindness past 512 tokens (+0.826 with and without support)
- Expansion never winning a slot: 0/60 queries, impossible in 45/60
- 39/40 and 100/100 identical result sets
- RGAT and OWL reachable only from their own tests; no GNN training script
- 18 tests pass in the new suites

Inferred but not directly measured, and flagged as such in the text:

- The `w_relation` memory figures are arithmetic on a shape read from source, not an observed OOM.
- The relation-index instability was reproduced in a scratch script rather than by exercising `native/memory.py` directly.

One earlier hypothesis was **disproved** during this analysis and corrected: NLI truncation was initially blamed for `mean_true < 0`. Testing showed truncated-but-unsupported evidence scores +0.826, not negative. The real defect — invariance to support past 512 tokens — is worse, and was found only because the original claim was tested rather than asserted.
