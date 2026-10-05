# TAHI: The AI-Driven World-Model Coprocessor

---

## Executive Summary

TAHI is an open-source research framework and coprocessor for Large Language Models (LLMs).

It investigates whether structured knowledge graphs (Kùzu C++ Property Graph), Relational Graph Attention Networks (RGAT), and latent hidden-state cross-attention (GCCA Level 3) can overcome the fundamental bottlenecks of standard Retrieval-Augmented Generation (RAG).

---

## Core Technical Bottlenecks in Standard RAG

1. **Context Window Inflation & TTFT Overhead**: Concatenating large document chunks inflates prompt length, driving up prefill latency (Time-To-First-Token) and compute costs.
2. **Semantic Myopia & Negation Blindness**: Vector similarity over text embeddings is blind to logical polarity. `"The server is operational"` and `"The server is NOT operational"` share near-identical embedding representations.
3. **Loss of Relational Topology**: Flattening knowledge graphs into text summaries strips out multi-hop graph structure, entity dependencies, and numeric constraints.

---

## System Architecture

```
                       TAHI GNN Coprocessor Pipeline
                       
  Unstructured Corpus ──► Subgraph Extraction ──► Kùzu C++ Property Graph
                                                        │
                                                        ▼
                                         Relational Graph Attention Network
                                            (src/tahi/graph/gnn_encoder.py)
                                                        │
                                                        ▼
                                         Topological Memory Tensor [1, K, d]
                                          (src/tahi/native/memory.py)
                                                        │
                                                        ▼
                                         Level 3 GCCA Hidden-State Injection
                                          (src/tahi/native/gcca_layer.py)
```

1. **Embedded Subgraph Storage**: Ingests enterprise text into an embedded **Kùzu C++ Property Graph**, extracting typed entity relations.
2. **Topological Graph Neural Encoding**: A PyTorch **Relational Graph Attention Network (RGAT)** runs 2-layer message passing over retrieved subgraphs to output `[1, K, d_retriever]` topological memory tensors.
3. **Level 3 Native Residual Injection**: PyTorch Gated Chunked Cross-Attention (GCCA) forward hooks inject GNN topological memory tensors directly into intermediate LLM transformer hidden states.
4. **Passage-Level NLI Evaluator**: Uses a DeBERTa NLI Cross-Encoder with passage max-aggregation ($p_{\text{entailment}} - p_{\text{contradiction}}$) to evaluate claim validity.

---

## Empirical Benchmark Findings (Unvarnished Audit)

Every number below is drawn directly from pre-registered machine-generated JSON evaluation artifacts (`benchmarks/results/l3_native_run.json` and `fragment_verification.json`).

### 1. Length-Controlled Generation Benchmark ($N=500$ Questions, $10,000$ Documents, `--max-new-tokens 35`)

| Arm | Architecture | Token F1 | Fact Coverage | Exact Match | Mean Tokens | Stat. Sig. vs Base (95% CI) |
|---|---|---:|---:|---:|---:|---|
| **Base LLM** | Floor Baseline (No context) | 0.0749 | 0.0170 | 0.036 | 10.4 | Baseline |
| **Text Prompt RAG** | Text context pasted into prompt | **0.1277** | **0.0580** | 0.030 | 18.0 | **$+0.0528$ (CI `[+0.0378, +0.0675]`, $p < 0.05$)** |
| **Identity Control** | Native GCCA ($\alpha=0$) | 0.0749 | 0.0170 | 0.036 | 10.4 | **$+0.0000$ (CI `[0.0000, 0.0000]`, 0 Mismatches)** |
| **L3 GCCA (Epoch 2)** | Native Hidden-State Injection | 0.0733 | 0.0150 | 0.036 | 10.4 | $-0.0016$ (CI `[-0.0045, +0.0007]`, Not Sig.) |

* **Identity Control Verified**: Setting $\alpha=0$ perfectly reproduces base model completions token-for-token across all 500 questions (0 mismatches).
* **Text Prompt RAG Lift**: Standard prompt-side text retrieval yields a statistically significant Token F1 lift of $+0.0528$.
* **Hidden-State Injection Status**: Initial GCCA weights (`gcca_epoch2.pt`) act as a minor residual perturbation ($0.0733$ F1 vs $0.0749$ Base), demonstrating that latent hidden-state injection requires full multi-epoch joint training to match prompt-side RAG.

---

### 2. Retrieval Precision Benchmark ($N=50$ Fragments, $2,000$ Documents)

* **Overall Retrieval AUC**: Dense Vector RAG Baseline (**0.5744**) vs TAHI Graph Store (**0.5220**). Vector baseline outperforms current graph store across 3 of 4 perturbation families.
* **Numeric Claims Subset**: TAHI Graph Store (**0.7300**) vs Vector Baseline (**0.6500**) on $n=2$ sample questions.
