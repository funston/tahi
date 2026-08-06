# Antigravity Audit — Evaluation & Validation of `CLAUDE_AUDIT.md`

**Date:** 2026-08-05  
**Reviewer:** Antigravity (AGY)  
**Target Document:** [`CLAUDE_AUDIT.md`](file:///home/rich/share/work/octo/CLAUDE_AUDIT.md)  
**Verdict:** **All 6 findings in `CLAUDE_AUDIT.md` are 100% VALID and mathematically sound.** This document records Antigravity's empirical evaluation of each finding, root cause analysis, and remediation requirements.

---

## Executive Summary

After detailed empirical inspection of `data/graphrag_bench/graph_out/` and `scripts/run_evidence_recall.py`, Antigravity confirms that **all 6 defects identified in [`CLAUDE_AUDIT.md`](file:///home/rich/share/work/octo/CLAUDE_AUDIT.md) are real and valid.**

---

## Detailed Evaluation of Audit Findings

### Finding 1: Flaws in Evidence Recall Interpretation (100% VALID)

- **1a. Sample Bias (Fact Retrieval Only)**:
  - `medical_questions.json` is strictly sorted by question type:
    - `[0 - 1097]`: Fact Retrieval
    - `[1098 - 1606]`: Complex Reasoning
    - `[1607 - 1895]`: Contextual Summarize
    - `[1896 - 2061]`: Creative Generation
  - Using `--limit-questions 50` took `questions[:50]`, sampling **100% Fact Retrieval questions** and 0 Complex Reasoning, Contextual Summarize, or Creative Generation questions.
  - **Impact**: Fact Retrieval is the easiest subset. Reading 0.8658 as an overall benchmark evidence recall score is invalid.
  - **Remediation**: Use a seeded stratified random sample across all 4 question categories.

- **1b. Retriever Confound vs Graph Content Ceiling**:
  - `GATE1_SPEC.md` §2.1 specifies running `compute_evidence_recall` with all graph facts passed in as `contexts` to measure the graph's content ceiling.
  - The script inserted a custom keyword-overlap retriever (`build_question_relevant_graph_context`), measuring the retriever rather than the total graph content ceiling.
  - **Remediation**: Report both retrieval-free evidence recall (graph content ceiling) and retrieved evidence recall.

---

### Finding 2: Relation Explosion & Misspelling Fragmentation (100% VALID)

- **Empirical Measurement**:
  - `manifest.json` shows 5,701 edge mentions across 1,204 distinct relation types.
  - 795 relation types occur exactly once.
- **Metastasis Fragmentation Breakdown**:
  - `metastazises_to` (misspelled): **61 edges** (most frequent)
  - `metastasizes_to` (correct): **45 edges**
  - `can_metastasize_to`: 5 edges
  - `has_common_metastatic_areas`: 5 edges
  - `metastazies_to`: 3 edges
  - `can_metastasize`: 1 edge
  - `is_metastatic`: 1 edge
  - `does not metastasize`: 1 edge
- **Impact**: Un-normalized relation extraction shatters the primary medical relation across 8 variants. Any query filtering for `metastasizes_to` misses **63% of metastasis edges**.
- **Remediation**: Implement a relation canonicalization map (`metastazises_to` $\rightarrow$ `metastasizes_to`) in graph loading.

---

### Finding 3: Graph Topological Connectivity / 69% Dead-End Nodes (100% VALID)

- **Degree Distribution**:
  - 4,420 total nodes · 5,316 total edges
  - Mean degree: 2.41 · Median degree: 1
  - **3,066 nodes (69%) have exactly 1 edge** (dead ends).
- **Impact**: Multi-hop graph traversal across connected entity chains is impossible when 69% of nodes are isolated leaves.
- **Remediation**: Execute GraphRAG-Bench's `indexing_eval.py --framework graphml` to generate standardized structural graph metrics (graph density, average degree, connected components).

---

### Finding 4: Baseline Split Misalignment (100% VALID)

- `GATE1_SPEC.md` §3 cited 70.68% as the baseline floor from GraphRAG-Bench Table 4, but 70.68% is for the **CS/Textbook** split. We are evaluating the **Medical** split.
- **Remediation**: Use `base` (un-augmented `gpt-4o-mini`) on our actual Medical dataset as our empirical floor.

---

### Finding 5: Missing Confidence Intervals & Statistical Tests (100% VALID)

- Point estimates on small samples ($N=20$ or $N=50$) carry massive variance. A 3-point accuracy difference on 100 questions is inside noise.
- **Remediation**: Compute 95% bootstrap confidence intervals (`[ci_low, ci_high]`) on all final benchmark results.

---

### Finding 6: Spec Documentation Stale Text & Contradictions (100% VALID)

- `GATE1_SPEC.md` header contains stale "not implemented" status text, and Section 7 contradicts Appendix B regarding ReasonEmbed scope.
- **Remediation**: Reconcile Section 7 and Appendix B in `GATE1_SPEC.md`.

---

## Next Action Plan

1. **Complete Live Task `task-888`**: Allow the full 2,062-question 3-arm benchmark to finish running to record raw full-dataset baseline numbers.
2. **Apply Relation Normalization & Stratified Sampling**: Implement canonical relation mapping and stratified random sampling for all subsequent graph builds and evaluations.
