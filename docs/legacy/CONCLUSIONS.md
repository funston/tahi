# TAHI Platform — Methodical Evaluation Findings & Audit Assessment

**Date:** 2026-08-05  
**Target File:** `docs/CONCLUSIONS.md`  
**Methodology:** All figures drawn directly from pre-registered GraphRAG-Bench evaluation artifacts (`data/graphrag_bench/graph_clean/`).  
**Audit Reference:** [`CLAUDE_CONCLUSIONS.md`](file:///home/rich/share/work/tahi/CLAUDE_CONCLUSIONS.md)

---

## 1. Headline Finding

**Gate 1 is currently incomplete.** The initial $N=20$ pilot comparison (`tahi_graph` 40.55% vs `vector_rag` 40.14% ROUGE-L) was statistically indistinguishable from zero ($p = 0.875$, 95% bootstrap CI `[-8.95, +11.00]`). Furthermore, the 3 arms suffered from retriever implementation confounders that have now been identified and remediated.

---

## 2. Verified Empirical Findings & Graph Topology

### 2.1 Graph Build & Provenance
Source: `data/graphrag_bench/graph_clean/manifest.json`

- **Build Specs**: `gpt-4o-mini`, 1200-token chunks, gleaning enabled.
- **Corpus Processing**: 199 chunks (1.06 MB corpus) processed in 3,285s ($0.259 per MB).
- **Extraction Yield**: 4,379 nodes, 1,078 canonical relation types, 5,224 directed triples (collapsing to 4,800 unique undirected node pairs).
- **Relation Normalization**: Relation canonicalization successfully merged 8 misspelled variants (`metastazises_to`, `can_metastasize_to`, etc.) into `metastasizes_to` (116 edges). Recorded in `manifest.json`.

### 2.2 Graph Topological Connectivity
Source: `data/graphrag_bench/graph_clean/indexing_metrics.json`

| Metric | Value | Technical Meaning |
|---|---:|---|
| Nodes | 4,379 | Canonical medical entity vertices |
| Unique Edge Pairs | 4,800 | Unique undirected connections |
| Directed Triples | 5,224 | Total directed triples (424 multi-edges) |
| Average Degree | 2.19 | Average connections per node |
| Connected Components | 487 | Subgraph connectivity partitions |
| Giant Component | 3,146 (71.8%) | Largest single connected subgraph |
| Degree-1 Leaf Nodes | 72.69% | Leaf nodes (endpoints, not intermediates) |

---

## 3. Step 2 Evidence Recall Gate

Source: `data/graphrag_bench/graph_clean/evidence_recall_stratified.json`  
Evaluated using standard benchmark instrument `compute_evidence_recall` across a seeded stratified sample ($N=100$, 25 per category):

| Question Category | Stratified Evidence Recall (%) |
|---|---:|
| Fact Retrieval | 38.38% |
| Complex Reasoning | 36.67% |
| Creative Generation | 34.73% |
| Contextual Summarize | **8.44%** |
| **OVERALL STRATIFIED** | **29.55%** |

### Critical Takeaway:
Graph evidence recall sets the theoretical ceiling on downstream graph retrieval. At **29.55% overall recall**, the graph contains ~30% of the factual evidence required to answer the benchmark dataset.

---

## 4. Remediation of Retriever Confounders

Following the audit in `CLAUDE_CONCLUSIONS.md`, we identified and fixed four critical code confounders in `scripts/run_graphrag_bench_3arm.py`:

1. **Neural Encoder Parity**: Replaced bag-of-words token intersection (`len(q_tokens & n_tokens)`) in `GraphRetriever` with `BAAI/bge-large-en-v1.5` dense node embeddings, ensuring `tahi_graph` uses the exact same neural encoder as `vector_rag`.
2. **2-Hop BFS Graph Traversal**: Replaced 0-hop incident edge fetching with real 2-hop BFS graph traversal (`seed_node -> hop1 -> hop2`) to test actual multi-hop relational path reasoning.
3. **Context Budget Parity**: Equalized graph context formatting to match `vector_rag` (~15KB-18KB context window).
4. **Fallback & Logging**: Removed silent `self.edges[:25]` fallback and added explicit logging for unmatched queries.

---

## 5. Executive Decision Roadmap

To complete Gate 1 with 100% scientific rigor:

1. **Execute Stratified $N=100$ Benchmark**: Evaluate the remediated 3 arms across a seeded stratified sample of 100 questions (25 per category).
2. **Save Metric Artifacts**: Run vendored `generation_eval.py` and commit `eval_results.json` directly to disk with non-parametric 95% bootstrap confidence intervals per category.
3. **Path Connectivity Diagnostic**: Measure direct path connectivity ($L \ge 2$) between entity pairs named in Complex Reasoning questions before running full generation benchmarks.
