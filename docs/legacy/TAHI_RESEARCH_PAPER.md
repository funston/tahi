# TAHI: Optimal Co-processor Topology Architecture for Deterministic Property Graph Retrieval

**Authors:** TAHI Research Group  
**Date:** 2026-08-05  
**Document Type:** Formal Research Paper & Empirical Benchmark Analysis  
**Associated Artifacts:** `data/graphrag_bench/graph_clean/`

---

## Abstract

Vector Retrieval-Augmented Generation (Vector RAG) models suffer from severe limitations in multi-hop relational reasoning, deterministic claim attribution, and instant fact revocation. In this paper, we present **TAHI (Optimal Co-processor Topology Architecture)**, a Property Graph co-processor framework designed to index unstructured corpora into auditable entity-relation graphs with explicit per-edge source chunk pointers. Evaluated on the GraphRAG-Bench medical corpus (199 chunks, 1.06 MB), TAHI achieves an extraction yield of 4,379 nodes and 5,224 directed triples (4,800 unique undirected edges) at an indexing cost of **$0.259 per MB**. We implement relation canonicalization, reducing extraction variance across entity triples. Through a path connectivity diagnostic on 509 Complex Reasoning questions, we show that **76.56% of gold entity pairs** are connected by multi-hop relational paths of length $L \ge 2$. Finally, we detail our non-confounded retriever architecture featuring `BAAI/bge-large-en-v1.5` dense node embeddings, 2-hop BFS graph traversal, and context budget parity.

---

## 1. Introduction

Large Language Models (LLMs) augmented with Vector RAG retrieve text passages based on cosine similarity in dense embedding space. While effective for single-passage fact retrieval, Vector RAG breaks down under three enterprise constraints:
1. **Disjoint Multi-Hop Fact Synthesis**: Facts spanning non-adjacent chunks (e.g., Chunk #5 and Chunk #120) are rarely co-retrieved.
2. **Black-Box Provenance**: Probabilistic vector distances cannot verify whether a generated claim is grounded in raw source text.
3. **High Maintenance Overhead**: Deleting or updating a single invalid fact requires re-chunking and re-embedding large document collections.

TAHI addresses these challenges by transforming raw text into a structured Property Graph with deterministic `source_chunk_id` metadata tags on every edge.

---

## 2. Property Graph Construction & Canonicalization

### 2.1 Extraction Pipeline
Corpus processing was executed according to `GATE1_SPEC.md` using `gpt-4o-mini` with tiktoken `cl100k_base` encoding (1200-token chunk size, 100-token overlap, gleaning enabled).

```
Source Corpus (1.06 MB, 199 Chunks)
       │
       ▼  (gpt-4o-mini Extraction + Gleaning)
Extracted Triples (5,224 Directed Triples)
       │
       ▼  (Relation Canonicalization)
Canonical Property Graph (4,379 Nodes, 1,078 Relation Types)
```

- **Extraction Yield**: 4,379 nodes, 1,078 canonical relation types, 5,224 directed triples.
- **Node-Pair Collapse**: The 5,224 directed triples collapse to 4,800 unique undirected node-pair connections due to 424 directed multi-edges between identical entity pairs.
- **Indexing Cost**: 694,703 prompt tokens + 282,322 completion tokens = **$0.2736 total ($0.259/MB)** in 3,285 seconds.

### 2.2 Relation Canonicalization
Unconstrained LLM extraction produces morphological variants for identical semantic relations. We implemented relation canonicalization, collapsing 8 misspelled metastasis variants (`metastazises_to`, `can_metastasize_to`, `metastazies_to`, etc.) into a single canonical `metastasizes_to` relation with **116 edges**. Overall relation types dropped from 1,204 to 1,078. All canonical mappings are recorded in `data/graphrag_bench/graph_clean/manifest.json`.

---

## 3. Empirical Graph Topology & Path Connectivity

### 3.1 Network Topology Analysis
Source: `data/graphrag_bench/graph_clean/indexing_metrics.json`

| Metric | Value | Structural Impact |
|---|---:|---|
| Total Nodes ($|V|$) | 4,379 | Extracted entity vertices |
| Total Directed Triples | 5,224 | Raw extracted triples |
| Unique Undirected Edges ($|E|$) | 4,800 | Unique undirected connections |
| Average Node Degree | 2.19 | Connectivity density |
| Graph Density | 0.000501 | Sparse topological structure |
| Connected Components | 487 | Subgraph partitions |
| Giant Connected Component | 3,146 (71.8%) | Largest single connected subgraph |
| Degree-1 Leaf Nodes | 72.69% | Endpoint leaf nodes |

### 3.2 Path Connectivity Diagnostic
To verify whether the graph structure supports multi-hop relational path traversal, we evaluated 44,044 gold entity pairs across 509 Complex Reasoning questions in `medical_questions.json`. Shortest path lengths ($L$) were computed using NetworkX:

- **$L = 1$ (Direct Single Edge)**: 2,342 pairs (**5.32%**)
- **$L = 2$ (2-Hop Relational Path)**: 7,251 pairs (**16.46%**)
- **$L = 3$ (3-Hop Relational Path)**: 9,976 pairs (**22.65%**)
- **$L \ge 4$ (Long Relational Path)**: 16,494 pairs (**37.45%**)
- **Unconnected ($\infty$)**: 7,981 pairs (**18.12%**)

**Finding**: **76.56% of gold entity pairs** in Complex Reasoning questions are connected by multi-hop paths ($L \ge 2$), confirming that multi-hop paths exist across the 3,146-node giant component.

---

## 4. Stratified Evidence Recall Benchmark

Evaluated using standard benchmark instrument `compute_evidence_recall` across a seeded stratified sample ($N=100$, 25 per category):

| Question Type | Stratified Evidence Recall (%) |
|---|---:|
| Fact Retrieval | 38.38% |
| Complex Reasoning | 36.67% |
| Creative Generation | 34.73% |
| Contextual Summarize | **8.44%** |
| **OVERALL STRATIFIED** | **29.55%** |

**Recall Ceiling**: Evidence recall sets the theoretical ceiling on downstream graph retrieval. At **29.55% overall recall**, the graph contains ~30% of the facts required to answer the benchmark dataset.

---

## 5. Non-Confounded Retriever Architecture

Following the audit in `CLAUDE_CONCLUSIONS.md` and `CLAUDE_CHALLENGES.md`, we remediated three critical retriever confounders in `scripts/run_graphrag_bench_3arm.py`:

1. **Neural Encoder Parity**: Replaced bag-of-words token overlap (`len(q_tokens & n_tokens)`) with `BAAI/bge-large-en-v1.5` dense node embeddings, ensuring `tahi_graph` uses the exact same neural encoder as `vector_rag`.
2. **2-Hop BFS Graph Traversal**: Implemented 2-hop BFS graph traversal (`seed_node -> hop1 -> hop2`) to test actual multi-hop relational path traversal.
3. **Context Budget Parity**: Equalized graph context formatting to match `vector_rag` (~15KB–18KB context window).

---

## 6. Pre-Registered Oracle Falsification Plan

As specified in [`TAHI_PLAN.md`](file:///home/rich/share/work/tahi/TAHI_PLAN.md), the next decisive empirical step is the **Oracle Ceiling Test**:
- `oracle_vector`: Served gold evidence text chunks.
- `oracle_graph`: Served triples in `graph_clean/graph.json` seeded by gold entities.

If `oracle_graph` $\approx$ `oracle_vector`, the graph representation carries no inherent advantage and the thesis is falsified. If `oracle_graph` $\gg$ `oracle_vector`, downstream engineering is justified.

---

## References & Reproducibility Artifacts

- 📄 `data/graphrag_bench/graph_clean/manifest.json`
- 📄 `data/graphrag_bench/graph_clean/indexing_metrics.json`
- 📄 `data/graphrag_bench/graph_clean/evidence_recall_stratified.json`
- 🛠️ `scripts/run_path_connectivity.py`
- 🛠️ `scripts/run_graphrag_bench_3arm.py`
