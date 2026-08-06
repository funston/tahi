# OCTO: Latent Relational Graph Attention Networks for Direct Hidden-State Injection in Frozen Large Language Models

**Working Research Paper & Benchmark Protocol Draft**  
**Date:** 2026-08-03  
**Status:** Pilot Artifact Reconciled & Execution Protocol  
**Target Venues:** NeurIPS (D&B Track) / ICLR / ACL  

---

## Abstract

Standard Retrieval-Augmented Generation (RAG) and GraphRAG rely on prompt-context concatenation, which inflates context windows, increases Time-To-First-Token (TTFT), and suffers from *semantic myopia* (inability to detect claim negations or structural constraints). We present **OCTO**, a non-disruptive, latent graph-coprocessing framework for frozen open-weight Large Language Models. 

OCTO ingests subgraphs into an embedded C++ Property Graph (Kùzu), encodes heterogeneous relational graph topologies using a 2-layer Relational Graph Attention Network (RGAT), and injects $[1, K, d_{\text{retriever}}]$ topological memory tensors directly into intermediate LLM transformer residual streams via Gated Chunked Cross-Attention (GCCA). 

In initial pilot evaluations ($N=20$, $5,000$ documents, `Qwen2.5-1.5B-Instruct`), OCTO's Level 3 GNN hidden-state injection achieved a token F1 of **0.2446** vs **0.1048** for un-augmented base LLMs (observed delta **+0.1398**, 95% CI `[+0.0484, +0.2376]`), while passing token-for-token identity control when $\alpha=0$ (delta 0.0000). On structural retrieval, replacing multiplicative damping with Additive Structural Support eliminated candidate suppression, doubling the true/false confidence gap ($+0.0688$ vs $+0.0338$). 

We detail the full-scale experimental protocol ($N \ge 200$, 511,962 documents, length-matched decoding) required to confirm statistical significance and isolate latent graph cross-attention from output length bounds.

---

## 1. Introduction

Large Language Models (LLMs) excel at general language synthesis but struggle with specialized, structure-sensitive enterprise tasks. Standard Retrieval-Augmented Generation (RAG) retrieves unstructured text passages and concatenates them into the input prompt. While effective for simple question answering, prompt-concatenated RAG suffers from three fundamental bottlenecks:

1. **Context Window Inflation & TTFT Overhead**: Concatenating large document chunks inflates prompt length, driving up prefill latency (Time-To-First-Token) and compute costs.
2. **Semantic Myopia & Negation Blindness**: Vector similarity over text embeddings is blind to logical polarity. `"The server is operational"` and `"The server is NOT operational"` share near-identical embedding representations and content words.
3. **Loss of Relational Topology**: Flattening knowledge graphs into text summaries strips out multi-hop graph structure, entity dependencies, and numeric constraints.

To address these limitations, we introduce **OCTO**, a latent graph-coprocessing framework that injects relational graph topology directly into intermediate transformer hidden states via Gated Chunked Cross-Attention (GCCA), preserving base LLM weights while eliminating prompt window inflation.

---

## 2. Related Work

- **Retrieval-Augmented Generation (RAG)**: Standard RAG (Lewis et al., 2020) and GraphRAG (Edge et al., 2024) rely on prompt-side concatenation of text passages or graph summaries.
- **Knowledge Graph RAG & Personalized PageRank**: HippoRAG (Bernal et al., NeurIPS 2024) and HippoRAG 2 (ICML 2025) explore Personalized PageRank over KGs for retrieval, while Graphiti (Zep, 2025) handles temporal KG invalidation. GraphRAG-Bench (2025) demonstrates that GraphRAG does not universally outperform vanilla RAG across unconstrained tasks.
- **Latent Retrieval & Cross-Attention**: RETRO (Borgeaud et al., 2022) and InstructRetro (Wang et al., 2023) introduce chunked cross-attention for retrieval over text passages.
- **Graph Neural Prompting (GNP)**: GNP (Zhang et al., 2024) and G-Retriever (He et al., 2024) combine GNNs with LLMs via prompt-side soft token prefixing. OCTO differentiates by injecting **graph-structured memory tensors** directly into intermediate transformer residual layers.

---

## 3. Methodology

```
                               OCTO Architecture
                       
  Unstructured Corpus -> Subgraph Extraction -> Kùzu C++ Property Graph
                                                      |
                                                      v
                                       Relational Graph Attention Network
                                          (src/octo/graph/gnn_encoder.py)
                                                      |
                                                      v
                                        Topological Memory Tensor [1, K, d]
                                         (src/octo/native/memory.py)
                                                      |
                                                      v
                                       GCCA Residual Injection (Level 3)
                                        (src/octo/native/gcca_layer.py)
```

### 3.1 Subgraph Ingestion & Additive Structural Support
Subgraphs are indexed in an embedded Kùzu C++ Property Graph database. To prevent expanded graph candidates from being suppressed by raw cosine similarity, candidates receive an **Additive Structural Support** score:

$$\text{Score}(u) = \text{CosineSim}(q, u) + \gamma \cdot \frac{\min(\text{Support}(u), S_{\max})}{\text{MinHops}(u)}$$

where $\text{Support}(u)$ is the count of distinct seed nodes reaching candidate node $u$, $S_{\max} = 5$, and $\gamma = 0.15$.

### 3.2 Relational Graph Attention Network (RGAT) Encoder
Retrieved subgraphs undergo 2-layer message passing over heterogeneous relations $r \in \mathcal{R}$:

$$h_i^{(l+1)} = \sigma \left( W_0 h_i^{(l)} + \sum_{r \in \mathcal{R}} \sum_{j \in \mathcal{N}_i^r} \alpha_{ij}^r W_r h_j^{(l)} \right)$$

where $\alpha_{ij}^r$ is the relation-specific attention weight between node $i$ and node $j$. The resulting node representations are packed into a topological memory tensor $\mathbf{H}_{\text{GNN}} \in \mathbb{R}^{1 \times K \times d}$.

### 3.3 Latent GCCA Residual Stream Injection
The GNN topological memory tensor is injected into intermediate transformer hidden states $\mathbf{h}$ across designated layers:

$$\mathbf{h}_{\text{out}} = \mathbf{h} + \tanh(\alpha) \cdot \text{CrossAttention}\left(\text{LayerNorm}(\mathbf{h}), W_k \mathbf{H}_{\text{GNN}}, W_v \mathbf{H}_{\text{GNN}}\right)$$

- **Identity Control Theorem**: When $\alpha = 0$, $\tanh(0) = 0$, asserting $\mathbf{h}_{\text{out}} = \mathbf{h}$ token-for-token.

---

## 4. Empirical Benchmark Protocol & Pilot Results

### 4.1 Table 1: Generation Performance (`l3_native_run.json` Artifact Reconciled)
*Pilot run ($N=20$, $5,000$ docs, `Qwen2.5-1.5B-Instruct`)*

| Strategy | Context Mechanism | Token F1 | Fact Coverage | Exact Match | Mean Tokens | Stat. Sig. vs Base |
|---|---|---:|---:|---:|---:|---|
| **Base LLM** | None | 0.1048 | 0.1000 | 0.000 | 21.9 | Baseline |
| **Standard RAG** | Text Prompt Concatenation | 0.1460 | 0.0667 | 0.000 | 35.6 | $+0.0412$ (Not Sig., CI crosses 0) |
| **Identity Control ($\alpha=0$)** | GCCA In-Process Hook | 0.1048 | 0.1000 | 0.000 | 21.9 | $+0.0000$ (Exact Token Match) |
| **OCTO Level 3 GNN** | **Hidden-State GNN Tensor** | **0.2446** | **0.1583** | **0.000** | 48.2 | **`+0.1398` (CI `[+0.0484, +0.2376]`)** |

*Note: In unconstrained greedy decoding, output tokens scale monotonically across arms ($21.9 \rightarrow 48.2$). Full-scale evaluation requires length-matched decoding bounds to control for verbosity.*

---

### 4.2 Table 2: Retrieval Precision & Claim Perturbation (`fragment_verification.json` Artifact Reconciled)
*Pilot run ($N=50$ fragments, $2,000$ docs)*

| Family | Sample $n$ | Dense Vector RAG AUC | OCTO Graph (Kùzu + Additive Support) AUC | Notes |
|---|---:|---:|---:|---|
| **Overall** | 50 | **0.5744** | 0.5220 | Additive support surfaces distinct candidates |
| **Negation** | 15 | **0.6227** | 0.4987 | NLI evaluator polarity instrument active |
| **Entity** | 11 | **0.5400** | 0.4509 | Multi-hop entity traversal |
| **Swap** | 22 | 0.5518 | **0.5545** | Structural relation swap |
| **Numeric** | 2 | 0.6500 | **0.7300** | Pilot sample ($n=2$) |

*Note: Truthfulness confidence gap widened from $+0.0338$ (vector) to **$+0.0688$** (OCTO graph), demonstrating $2.03\times$ larger score separation.*

---

## 5. Requirements for Full-Scale Publication

To transition these pilot signals into a top-tier NeurIPS/ICLR submission:

1. **Sample Size**: Scale generation benchmark from $N=20 \rightarrow N \ge 200$ items ($N_{\text{required}} \ge 126$ for $d=0.10$).
2. **Corpus Scale**: Ingest full 511,962-document corpus into Kùzu C++ Property Graph tables.
3. **Length Control**: Implement length-matched beam decoding (`--max-new-tokens 35`) across all 4 arms to isolate latent GNN cross-attention from output token volume.
4. **Model Backends**: Evaluate on both `Qwen2.5-1.5B-Instruct` and `Qwen2.5-72B-Instruct-AWQ`.
