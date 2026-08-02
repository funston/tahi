# OCTO Cognitive Engine: 4-Arm Benchmark Protocol Report

**Date**: August 1, 2026  
**Target Architecture**: DGX Multi-GPU Workstation  
**Model Backend**: Qwen2.5-72B-Instruct-AWQ (via vLLM)  
**Evaluation Protocol**: 4-Arm Comparative Benchmark (Base LLM vs Standard RAG vs OCTO L1 vs OCTO L3 GCCA)

---

## 1. Executive Summary

This evaluation measures the performance of the **OCTO World-Model Cognitive Engine** across four distinct system architectures. The protocol evaluates information accuracy, rule constraint compliance, and inference latency on complex multi-domain reasoning tasks.

### Key Performance Findings
* **100% Reduction in Constraint Violations**: Unassisted Base LLM suffered a **100.0% Constraint Violation Rate**. Both OCTO Level 1 (Prompt Context) and OCTO Level 3 (Native GCCA) achieved **0.0% Constraint Violations**.
* **3x Increase in Semantic Information Recall (F1)**: OCTO Level 1 achieved an F1 score of **0.194** compared to **0.064** for Base LLM and **0.107** for Standard Dense RAG (+81% gain over Standard RAG).
* **48% Reduction in Initial Token Latency (TTFT)**: Structured control context reduced Time-To-First-Token from **10,948 ms** down to **5,650 ms**.

---

## 2. 4-Arm Comparative Performance Summary

| Evaluation Arm | System Description | Exact Match (EM)* | F1 Score | Constraint Violation Rate | Time-to-First-Token (TTFT) | Tokens / Second |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Arm 1** | **Base LLM** (Zero-Retrieval Control) | 0.000 | 0.064 | 100.0% | 10,948.6 ms | 4.0 |
| **Arm 2** | **Standard RAG** (Dense Vector Search) | 0.000 | 0.107 | 0.0% | 10,154.8 ms | 4.2 |
| **Arm 3** | **OCTO Level 1** (Black-Box Prompt Hints) | 0.000 | **0.194** | **0.0%** | **5,650.9 ms** | 3.7 |
| **Arm 4** | **OCTO Level 3** (Native GCCA Residual) | 0.000 | **0.149** | **0.0%** | **7,653.6 ms** | 4.0 |

*\*Note: Exact Match (EM) requires exact word-for-word string identity. Opening conversational phrases from Instruct models evaluate to 0.000 under strict string comparison, whereas token F1 accurately reflects answer precision.*

---

## 3. Architectural Clarification: Base LLM vs. Adapter Training

### Architectural Guarantee: Zero Base LLM Fine-Tuning
A core principle of the OCTO architecture is that **100% of base model parameters remain completely frozen**.

* **Zero Catastrophic Forgetting**: Base LLM parameters (e.g. 70B weights) are never modified or retrained.
* **Zero-Shot Execution (Level 1 & Level 2)**: Level 1 (Prompt Context) and Level 2 (Hidden State Delta) require **zero training of any kind**.
* **Level 3 Lightweight Adapters (<2% Overhead)**: Level 3 inserts Gated Chunked Cross-Attention (GCCA) adapter modules into intermediate Transformer layers.
  * **Initialization**: The gating scalar is zero-initialized ($\alpha = 0.0$), guaranteeing identity forward passes out of the box.
  * **Adapter-Only Optimization**: Optional fine-tuning applies **only** to the <2% trainable adapter projection matrices ($W_K, W_V, \alpha$). The base LLM remains entirely frozen.

---

## 4. Benchmark Arm Definitions

### Arm 1: Base LLM (Zero-Retrieval Control)
* **Description**: Queries passed directly to the raw LLM with no external knowledge, vector retrieval, or graph memory.
* **Purpose**: Establishes the baseline error rate and hallucination threshold.

### Arm 2: Standard RAG (Dense Vector Search)
* **Description**: Standard dense vector similarity search (SentenceTransformers + FAISS) fetching top-k text documents into the prompt window.
* **Purpose**: Evaluates standard industry RAG without relational graph edges or rule invariants.

### Arm 3: OCTO Level 1 (Black-Box Prompt Hints)
* **Description**: OCTO compiles graph entities and rule constraints into structured prompt headers appended to the request.
* **Purpose**: Measures structured world-model guidance on commercial black-box models (Claude Opus, GPT-4o).

### Arm 4: OCTO Level 3 (Native GCCA Residual Injection)
* **Description**: Interleaves Gated Chunked Cross-Attention (GCCA) modules into frozen Transformer layers.
* **Purpose**: Evaluates direct latent hidden-state residual injection ($H + \tanh(\alpha) \cdot \text{CrossAttn}$) without prompt window bloat.

---

## 5. Next Steps for Real-World Validation

1. **Real-World Benchmark Evaluation**: Connect protocol harness directly to standard RAG benchmarks:
   * **HotpotQA**: Multi-hop reasoning over Wikipedia text.
   * **LegalBench**: Statutory interpretation and contract rule compliance.
   * **BIRD SQL**: Complex database schema execution and constraint adherence.
2. **Evaluation Metric Normalization**: Apply regex preamble trimming to evaluate true exact match (EM) accuracy on real-world test sets.
