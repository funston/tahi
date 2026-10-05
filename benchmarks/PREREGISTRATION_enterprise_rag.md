# Pre-registration — EnterpriseRAG-Bench: RAG vs Tahi

**Committed:** 2026-08-01, before any run.
**Runner:** `benchmarks/run_enterprise_rag.py`
**Status:** awaiting corpus download.

This document exists to be unfalsifiable after the fact. Metric, N, and kill
criterion are fixed here, before results are seen.

---

## Hypothesis

Tahi's typed world model beats flat dense retrieval on enterprise questions
whose answers require combining documents linked by a structural relation
(project, thread, ticket, author), not merely documents that are semantically
similar to the question.

## Arms

| Arm | System | Retrieval |
|---|---|---|
| 1 | `base` | none — question only |
| 2 | `rag` | `StandaloneRAG`, dense top-k over the full corpus |
| 3 | `tahi_l1` | `TahiRuntime` — vector seed + graph expansion → `ControlPacket` |

All three share one LLM, one prompt template shape, one corpus. **No arm
receives `gold_answer` or `gold_document_ids`** — asserted at runtime by
`_assert_no_gold_leak`, which aborts the run on violation.

## Primary metric

**Token F1 on the pooled structure-sensitive categories** (n=170):
`project_related`, `constrained`, `conflicting_info`, `completeness`,
`intra_doc_reasoning`, `info_not_found`.

One metric, chosen in advance. `required_n(0.10) = 126`, so n=170 is adequate;
no individual category is (largest is 40). Per-category numbers are reported
as **descriptive only** and carry no significance claim.

## Secondary metrics (reported, not decisive)

- Document recall@10 — the diagnostic for *why* a delta happened. If Tahi and
  RAG have equal recall, any F1 difference is not coming from retrieval.
- Abstention accuracy on `info_not_found` — the real distractor-rejection test.
- Exact match (SQuAD-normalised), TTFT (streaming), cost per correct answer.

## Statistical test

Paired bootstrap, 10,000 resamples, seed 0, 95% CI on the mean F1 difference.
McNemar additionally on EM. **A delta reported without its CI is not a result.**

## Kill criterion

> If `tahi_l1` − `rag` on the primary metric has a 95% CI that includes zero at
> n=170, the structural thesis is **not supported** on enterprise multi-source
> QA. We publish that, and we do not re-cut the data by category, swap the
> primary metric, or expand N looking for a favourable slice.

Three outcomes, all publishable:

| Outcome | Action |
|---|---|
| CI excludes zero, favourable | First real support. Proceed to Level 3 work. |
| CI includes zero | Kill criterion fires. Publish the null. Move to the DEA domain. |
| CI excludes zero, unfavourable | Graph expansion adds noise (cf. MuSiQue −33%). Publish, then investigate expansion limits. |

## Known confounds — declared in advance

1. **Synthetic corpus.** LLM-generated; the authors note it lacks realistic
   tangents. Synthetic text may be unusually well-structured, which could
   flatter a structure-exploiting system. A win here is necessary, not
   sufficient.
2. **Gold sets are "revisable hypotheses"** (authors' words), not a hard oracle.
3. **LLM-judged correctness** in the official protocol. Any judge model must be
   pinned in the manifest, or run-to-run reproducibility is lost. This runner
   uses deterministic F1/EM to avoid the dependency for the primary metric.
4. **Graph density.** `graph_health()` warns if the world model has few edges.
   A null result on an edgeless graph says nothing about the thesis; it says the
   metadata did not parse.
5. **Cost apportionment** is total ÷ number of arms — approximate, and labelled
   as such in the manifest.

## Fixed before the run

- Corpus: full extract, no `--max-docs` cap. If a cap is used, the manifest
  records it and recall figures are marked non-comparable.
- `top_k = 10` for both retrieval arms (matches the benchmark's Recall@10).
- Seed 0 everywhere.
- Streaming on, so TTFT is time-to-first-token and not total latency.

## Pre-run defect log

Two defects were found and fixed *before* any measurement, both of which would
have confounded this comparison:

- `TahiRuntime.infer` passed a character-sum hash embedding as
  `query_embedding`, overriding sentence-transformer retrieval at matching
  dimensionality — so Tahi retrieved with a hash while RAG used real embeddings.
  Fixed; pinned by `tests/test_runtime_retrieval_quality.py`.
- `sentence-transformers` failed to import (missing FFmpeg for `torchcodec`) and
  `get_encoder()` silently substituted the hash encoder. Fixed; caught by
  `tahi.eval.preflight`.

---

# Success Criteria — committed 2026-08-01 18:55 UTC, run in flight, results unseen

Power available (95% confidence, 80% power), computed from `tahi.eval.stats`:

| Sample | n | Smallest real delta |
|---|---:|---:|
| Structural pool (primary) | 170 | **0.043 – 0.086** |
| Full set | 500 | 0.025 – 0.050 |
| `project_related` / `intra_document_reasoning` | 40 | 0.089 – 0.177 |
| `completeness` / `conflicting_info` / `info_not_found` | 20 | 0.125 – 0.250 |

**Consequence: no per-category result is decisive.** At n=20 the effect would have
to exceed 0.125 to be distinguishable from noise. Per-category numbers are
directional colour only. The 170-item pool is the only thing that can carry a claim.

## PRIMARY — `fact_coverage`, Tahi vs RAG, structural pool (n=170)

| Verdict | Criterion | Meaning |
|---|---|---|
| **STRONG SUCCESS** | delta ≥ **+0.10**, CI excludes zero | Thesis supported with margin. Fundable as evidence. |
| **SUCCESS** | delta ≥ **+0.05**, CI excludes zero | Real, at the edge of what n=170 resolves. Replicate before leaning on it. |
| **NULL** | CI includes zero | Not supported on this benchmark. Publish it. |
| **FAILURE** | delta ≤ **−0.05**, CI excludes zero | Graph expansion actively hurts (cf. MuSiQue −33%). |

A delta between 0 and +0.05 with a CI crossing zero is a **NULL**, not a "trend."
n=170 cannot resolve it, and calling it promising would be the exact error this
whole exercise exists to prevent.

## SECONDARY — the bullshit metric

`unsupported_rate` (= 1 − groundedness), same pool.

**Success: ≥ 20% relative reduction.** If RAG is 0.35, Tahi must reach ≤ 0.28.
This is the metric that maps to the actual pitch — fewer unsupported assertions.
A win here with a null on `fact_coverage` would mean Tahi is *more careful*
without being *more complete*: a real but narrower claim.

## MECHANISM CHECK — `doc_recall` decides what we are allowed to claim

| `fact_coverage` | `doc_recall` | What we may claim |
|---|---|---|
| up | up ≥ +0.05 | **The graph did the work.** Strongest form of the thesis. |
| up | flat | The win came from the control packet's prompt hints, not traversal. That is L1 prompt engineering — real, but reproducible by any competitor in a week. **Do not call it a structural result.** |
| flat | up | Retrieval improved, generation did not exploit it. Points at prompt/answer construction, not the thesis. |
| flat | flat | Graph adds nothing here. |

## ABSTENTION — `info_not_found` (n=20, descriptive only)

Underpowered by design. But directional: **Tahi must be ≥ RAG.** If Tahi
fabricates *more* often when the answer is absent, that contradicts the
provenance claim outright and no `fact_coverage` win offsets it.

## SANITY GATES — the run is invalid, not negative, if any of these hold

1. `doc_recall` for RAG stays ≈ 0.18 (the 30k-doc smoke value) on the full
   511,962-doc corpus. Recall must rise substantially with 17× the corpus; if it
   does not, indexing is broken.
2. `graph_health` reports < 0.5 edges/doc. A null on an edgeless graph says
   nothing about structure.
3. `encoder_is_fallback: true` or `strict_mode: false` in the manifest.
4. `base` arm scores above ~0.05 `fact_coverage` — would mean answers are
   recoverable without retrieval and the benchmark is not testing retrieval.

## What is NOT a success

- A favourable aggregate across all 500 driven by `basic`/`semantic`. Those are
  300 items where dense retrieval is expected to win or tie; a shift there
  indicates a prompt artifact, not structure.
- Any single category looking good at n=20–40. See the power table.
- Better TTFT or lower cost with equal correctness. Worth noting, not the claim.
