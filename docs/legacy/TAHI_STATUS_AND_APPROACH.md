# TAHI — where we are, and the approach

**Updated:** 2026-08-03

One page on what is real, what was abandoned and why, and what happens next.
Details and reproduction commands live in `benchmarks/COVERAGE_METHODOLOGY.md`.

---

## 1. The thesis, restated

An organisation's curated knowledge — an ontology, a knowledge graph, a GNN
— holds facts its language model does not have. TAHI connects the two at
generation time so the model states those facts instead of inventing them.
**No retraining.**

Two claims, independent, and they were tangled together for months:

| | Claim | Status |
|---|---|---|
| **A** | A curated graph holds facts the model does not state | **Measured. Large.** |
| **B** | Connecting the graph at generation time fixes that | **Not established** |

Claim A is now supported by counts over a third-party graph. Claim B has never
been measured honestly — the one attempt was circular and was discarded.

---

## 2. What is real

Verified by running code, reproducible from the repository.

### The factual gap (Claim A)

Hetionet v1.0, 47,031 nodes / 2,250,198 edges, used as-is. Questions generated
mechanically from edges; scoring is exact string match against curated targets.
**No model grades anything.**

| Relation | Facts from | Qwen2.5-1.5B | Claude Opus 5 |
|---|---|---:|---:|
| `CbG` binds | literature | 3.3% | **19.8%** |
| `DaG` disease–gene | literature | 6.2% | **30.8%** |
| `CdG` downregulates | LINCS assay | 0.0% | **2.1%** |
| `CuG` upregulates | LINCS assay | 0.0% | **2.7%** |
| **Overall coverage** | | **2.6%** | **14.8%** |

At n=100 the 1.5B holds at **3.0%**, with **76/100 subjects producing zero
correct facts** — so the small-model figure is stable across samples.

**The finding worth carrying into a room:** scale buys 5–6× on facts published
in literature and essentially nothing on facts produced by experiments. Data
never written down in prose is structurally beyond pretraining, which is exactly
the shape of a customer's proprietary graph.

Secondary: models confabulate rather than abstain. Given an explicit "say I
don't know" option, the 1.5B took it once in 60, Opus once in 20.

### Harness properties worth keeping

- **Identity control**: with the GCCA gate at zero, output is bit-identical to
  the stock model — 0 mismatches at n=500
- **Length-matched decoding** across arms (10.4 tokens), which killed the
  project's own headline result once already
- Paired bootstrap CIs, fail-loud manifests that refuse to write a degraded run

---

## 3. What was abandoned, and why

Recorded so none of it gets rebuilt by accident.

| Abandoned | Why | Evidence |
|---|---|---|
| `fact_coverage` metric | Negating **every** gold answer moved it **0.0000** | Negation probe |
| NLI entailment judge | **+0.826 with AND without** supporting evidence past ~512 tokens | Support-ablation probe |
| LLM claim extraction | 9/9 correct on real entities, **3/9 on invented ones** — recall, not grammar | `scripts/probe_extractor.py` |
| The 2026-08-03 L3 result | Adapter trained on raw embeddings, scored on a **randomly-initialised RGAT** projection. The −0.0117 delta measured the mismatch | Two code paths read directly |
| Hand-rolled negation regex | Keyword flags break on scoped and double negation | Reasoned, not shipped |
| First "with TAHI" arm | **Circular** — consulted the answer key to decide when to intervene, so 100% by construction | Caught on first run |
| Hetionet + GeneTuring pairing | **0 of 50** GeneTuring disease questions answerable from Hetionet's 137 common diseases | Overlap check |
| Cora / CiteSeer / PubMed | Planetoid ships **no text and no entity names** — bag-of-words vectors and integer ids only | Downloaded and inspected |

The common thread: **every one was found by testing the instrument against a
known answer, not by inspection.** That is now the standing rule.

---

## 4. The approach

### 4.1 Nothing we author decides a verdict

No learned metric, no judge model, no LLM in the scoring path. A fact is correct
because it matches an edge in a graph somebody else curated. The only model
involved is the one producing the answer being measured.

This is not fastidiousness. Three instruments in §3 failed silently and each
produced numbers that looked fine for weeks.

### 4.2 Manual review is the arbiter

`benchmarks/results/MANUAL_REVIEW.csv` has one row per subject in three buckets:

```
CLEARLY_CORRECT     exact match after normalisation
NEEDS_YOUR_EYE      ≥0.82 string similarity, not exact — counted as neither
CLEARLY_WRONG       no close match
```

`IL-1B` matches `IL1B`. `SLC19A3` does **not** match `SLC19A2` — different genes
— so it lands in the middle bucket for a person to judge. True coverage lies
between the correct rate and (correct + flagged).

### 4.3 Borrow the benchmark, don't build one

The questions in §2 are ours, and two ways that biases them are documented
(`COVERAGE_METHODOLOGY.md` §7). The fix is to adopt an evaluation domain experts
already published:

- **GeneTuring** — 1,600 expert questions, **48,303 answers scored by humans**,
  published baselines for GPT-4o / Claude 3.5 / Gemini. Downloaded.
- **PrimeKG** — 17,080 diseases, 90.8% of Orphanet's rare diseases. The likely
  graph for GeneTuring's rare-disease questions.
- **DrugMechDB** — 4,583 curated drug→disease mechanism paths, natively
  multi-hop.
- **STaRK-PRIME** — deprioritised: its queries are LLM-synthesised, which
  reintroduces the circularity above.

### 4.4 The experiment that earns the claim

1. Take a **documented** GeneTuring failure — published per-model, per-task
2. Reproduce it locally
3. Run the graph-backed path on the identical question
4. Report fixed or not fixed

We author no question, no gold answer, and no baseline. The "you made up your
benchmark" objection cannot attach.

---

## 5. Next, in order

1. **PrimeKG ↔ GeneTuring overlap check.** The same ten-minute check that
   eliminated Hetionet. If coverage is near zero again, this track needs a
   different graph and it is better to know before building anything.
2. **Pull GeneTuring's published per-task failure rates**, so step 1 of §4.4
   reproduces a documented failure rather than one we discovered.
3. **Build the non-circular TAHI arm** — the graph answers from the question
   alone, never from the gold set.
4. **Fix question phrasing to match edge semantics.** `CdG` means transcriptional
   downregulation in an assay, not pharmacological inhibition; the current
   `CdG`/`CuG` numbers are contaminated by our wording, not the model's error.

---

## 6. Explicitly not being worked on

| Item | Why |
|---|---|
| GCCA / Level 3 / α tuning | Claim B's delivery mechanism. Irrelevant until Claim B is shown to hold at all, and the gate never opened past 0.043 |
| Training the RGAT | No training script exists; it has never been validated against any published baseline |
| Retrieval scoring tuning | Expanded candidates won 0/60 slots; a fair test already failed |
| Scaling any corpus | Coverage, not corpus size, is the bottleneck |
| A new evaluation methodology | The point of §4.3 is to stop building these |

---

## 7. The honest one-paragraph version

A curated public knowledge graph contains a large body of facts that the best
available language model does not state — 85% of them, on the sampled subjects.
For facts drawn from published literature, a thousand-fold increase in model
size recovers a meaningful share. For facts drawn from experiments, it recovers
almost none, because that data was never written in prose to be learned from.
That is the durable case for an external knowledge layer, and it is measured
rather than argued. Whether TAHI closes the gap is a separate question, one
honest attempt at it has been discarded as circular, and the experiment that
would answer it is specified in §4.4 but has not been run.
