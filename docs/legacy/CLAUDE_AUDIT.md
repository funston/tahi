# Audit — Gate 1 spec, graph build, and evidence-recall results

**Date:** 2026-08-05
**Author:** Claude
**Scope:** `docs/GATE1_SPEC.md`, `data/graphrag_bench/graph_out/`, `scripts/run_evidence_recall.py`,
`scripts/run_graphrag_bench_3arm.py`
**Verdict:** two of the findings below mean the current numbers do not say what they appear to say.
Step 3 should not run until items 1–3 are resolved.

Every claim here was measured from the artifacts on disk, not inferred. Commands to reproduce are
inline.

---

## Artifacts under audit

`data/graphrag_bench/graph_out/manifest.json` (build completed 2026-08-05T19:44:10Z):

```
model gpt-4o-mini · chunk_size 1200 · overlap 100 · gleaning enabled
prompt_hash 8d4f90c150f0c2cd · tokenizer tiktoken (cl100k_base / o200k_base)
199 chunks → 4,420 nodes · 5,316 edges
698,460 prompt tokens + 285,093 completion tokens · $0.2758 · 3,963 s
```

`data/graphrag_bench/graph_out/evidence_recall_50_sample.json` (2026-08-06T01:07:39Z):

```
questions_evaluated 50 · overall_evidence_recall 0.8658
recall_by_question_type { "Fact Retrieval": 0.8658 }
```

---

## 1. The 0.8658 evidence recall is not a benchmark number

Two independent flaws. Either one alone is disqualifying.

### 1a. The sample is 50 Fact Retrieval questions and nothing else

`medical_questions.json` is **sorted by question type**:

| first index | question_type |
|---:|---|
| 0 | Fact Retrieval |
| 1098 | Complex Reasoning |
| 1607 | Contextual Summarize |
| 1896 | Creative Generation |

`scripts/run_evidence_recall.py:135` takes a head slice:

```python
questions_data = questions_data[: args.limit_questions]
```

So `--limit-questions 50` yields 50/50 Fact Retrieval. That is the type Appendix A of the spec
measured at **92.5% answer-in-evidence overlap** — the easiest subset of the benchmark, and the one
where the graph is least likely to matter. **Complex Reasoning has never been evaluated.**

The result file is honest about this (`"recall_by_question_type": {"Fact Retrieval": 0.8658}`); the
error is in reading 0.8658 as an overall score.

**Fix:** stratified random sample with a recorded seed, reported per question type.

### 1b. It is not a ceiling, which was the entire purpose of Step 2

`GATE1_SPEC.md` §2.1 specifies running the metric *"with the graph's facts as `contexts`"* to
establish *"the ceiling on Step 3 — no retriever can exceed it."*

The implementation inserts a retriever instead. `scripts/run_evidence_recall.py:59`:

```python
def build_question_relevant_graph_context(...)   # our code, token-overlap scoring
    ...
    top_node_ids = {n_id for _, n_id in scored_nodes[:max_triples]}   # max_triples = 50
```

So 0.8658 measures **a retriever we wrote**, not **what is present in the graph**. Step 2 and
Step 3 are confounded, and the gate cannot perform its stated function of distinguishing a bad
graph from a bad retriever.

**Fix:** run it twice — once retrieval-free (the ceiling §2.1 asks for), once with a retriever.
Two numbers, two distinct meanings, both reported.

---

## 2. Relation explosion — the spec's own prediction came true, and it fragmented metastasis

`GATE1_SPEC.md` §1.3: *"If the model invents relations in volume, that is a finding to report, not
something to suppress."*

Measured from `manifest.json`:

```
5,701 edge mentions across 1,204 distinct relation types
795 relation types occur exactly once
```

The specific relation this spec was written to protect is split eight ways:

| count | relation |
|---:|---|
| **61** | `metastazises_to` ← misspelled, and the **most common** variant |
| **45** | `metastasizes_to` ← correct spelling |
| 5 | `can_metastasize_to` |
| 5 | `has_common_metastatic_areas` |
| 3 | `metastazies_to` |
| 1 | `can_metastasize` |
| 1 | `is_metastatic` |
| 1 | `does not metastasize` |

The original hard-coded schema **deleted** metastasis facts (`build_corpus_graph.py:183`, since
fixed). That deletion is fixed. But nothing normalises relations, so the dataset's most frequent
relation is now shattered across eight types with the typo winning. **A typed query for
`metastasizes_to` misses 63% of metastasis edges.** The same facts are lost by a different
mechanism.

This is a **gap in the spec, not only the code**: §1.3 specifies merging *nodes* by normalised
name. It never specifies merging *relations*.

---

## 3. The graph is barely traversable — this threatens the thesis directly

Degree distribution computed from `graph.json`:

```
4,420 nodes · 5,316 edges
mean degree 2.41 · median degree 1 · max 119
3,066 nodes (69%) have exactly ONE edge
   594 nodes have two
   377 nodes have five or more
```

TAHI's claim is that an answer is reached by following a chain of facts. **69% of nodes are dead
ends.** Whatever Step 3 reports, the `tahi_graph` arm has very little structure to exploit — and a
loss would be uninterpretable, indistinguishable from "the thesis is wrong."

`GATE1_SPEC.md` §2.2 specifies exactly the instrument for this:

```shell
python -m Evaluation.indexing_eval --framework graphml --base_path <graph dir> \
  --output results/indexing_metrics.txt
```

**It has never been run.** `graph.graphml` (1.4 MB) has been on disk since 09:44. It costs nothing
and produces published-comparable structural metrics.

---

## 4. The ~3-point bar is quoted from the wrong dataset split

`GATE1_SPEC.md` §3 cites S1 Table 4 — vanilla gpt-4o-mini **70.68%**, RAPTOR **73.58%** — and the
spec itself labels these *"accuracy on the CS/textbook split."*

We are running the **Medical** split.

§3.1 then defines the `base` arm as *"S1 reports 70.68% for this; a sanity check on our harness."*
That compares a medical result against a published CS result. The check cannot meaningfully pass or
fail.

**Fix:** obtain the Medical-split baselines, or remove the sanity-check framing and state plainly
that no published number exists for our split.

---

## 5. No statistical test anywhere, against a ~3-point effect

`GATE1_SPEC.md` §6 proposes a pilot of 100 questions. At n=100 a 3-point difference is **three
questions** — inside noise. Per question type it is worse: Creative Generation is 166 questions in
the entire benchmark.

The spec contains no power calculation, no confidence intervals, and no significance test. §4's
deliverable is a table of bare point estimates.

Given this project's history of retracted results, this is the gap most likely to produce another
one. **Minimum: bootstrap confidence intervals per question type, and a stated minimum detectable
effect for the chosen n.**

---

## 6. The spec contradicts itself and is stale

| location | problem |
|---|---|
| Header | *"Status: spec, not implemented"* — it is built, run, and $0.2758 spent |
| §1.2 | *"What `build_corpus_graph.py` does today, and why it is wrong"* describes the pre-fix version; reads as a live defect list but is history |
| §7 vs Appendix B | **Direct contradiction.** §7: ReasonEmbed enhancements *"are incorporated into TAHI's roadmap"* with concrete protocols. Appendix B: *"PARKED. Not in scope for Gate 1… it is not a work item."* |
| §7.3 vs B.0 | §7.3 defines reasoning intensity as a **difference** of losses; B.0 and the source paper define it as a **ratio** |
| §7 style | Different voice and LaTeX formatting from the rest of the document — appears pasted in from another source |
| `manifest.json` | `num_edges: 5316` but `relation_distribution` sums to **5701** (Δ 385) — presumably pre- vs post-dedup, but unlabelled |
| §2 cost | Estimated graph cost ~$0.12; actual **$0.2758** (2.3×). The $15–25 total estimate uses the same estimator |

---

## What is holding up

Recorded because it is not nothing, and because these are the parts that make a Step 3 result
credible:

- **Rule 1 held.** `run_evidence_recall.py:30` genuinely imports the benchmark's own
  `compute_evidence_recall`. The metric is not ours.
- **Provenance is good.** The manifest records prompt hash, tokenizer, chunk size, per-run token
  counts, cost, and wall clock. The build is reproducible and auditable.
- **Every edge carries `source_chunk_id`.** Any fact can be traced to its source chunk.
- **"Guidance, not filter" works.** Free-form relations the model invented (`begins in`,
  `does not metastasize`) were logged rather than silently dropped — which is precisely how
  finding 2 became visible instead of invisible.
- **Appendix A's pre-registered prediction is the strongest thing in the document.** It was written
  before the run and cannot be rationalised afterwards.

---

## Required before Step 3

1. Re-run evidence recall on a **stratified random sample with a recorded seed**, reported per
   question type. (Finding 1a)
2. Run it **retrieval-free** to obtain the ceiling §2.1 actually specifies, in addition to the
   with-retriever number. (Finding 1b)
3. Run `indexing_eval --framework graphml`. Free, and it is the connectivity evidence for
   finding 3.
4. Reconcile §7 with Appendix B — the document currently issues two opposing instructions.
5. Add confidence intervals and a stated minimum detectable effect to §4's deliverable.

## Open decision — Rich's call, not mine

**Relation normalisation.** Merging `metastazises_to` into `metastasizes_to` is a *filter*, and
Rule 3 forbids silent filtering.

Recommendation: leave the raw graph untouched, add a canonical alias map as a **separate, logged
layer**, and report results on both graphs. The delta between them then becomes a measured
finding rather than a hidden preprocessing step.

This is a knob. Per Rule 2 it must be named in the spec together with whoever chose it.
