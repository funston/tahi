# OCTO World-Model Engine: Real LegalBench 4-Arm Benchmark Report

**Date**: August 1, 2026  
**Dataset**: LegalBench Statutory & Contract Reasoning Dataset  
**Environment**: DGX Workstation (`vLLM` + `PyTorch` Native GCCA Integration)  
**Model Backend**: `Qwen/Qwen2.5-72B-Instruct-AWQ`

---

## 1. Executive Summary

This report evaluates the **OCTO World-Model Cognitive Engine** on the **LegalBench** statutory interpretation and contract reasoning dataset. The evaluation benchmarks four architectural arms across legal F1 score accuracy, statutory constraint compliance, and Time-To-First-Token (TTFT) latency.

### Key Performance Findings
* **Highest F1 Legal Reasoning Accuracy**: **OCTO Level 1** achieved the highest F1 score at **0.402** (**+52% relative improvement** over Base LLM `0.264`, and **+17% improvement** over Standard RAG `0.344`).
* **48% Reduction in Initial Token Latency (TTFT)**: Both **OCTO Level 1** (**5,754 ms**) and **OCTO Level 3 GCCA** (**5,775 ms**) cut latency nearly in half compared to Base LLM (**11,124 ms**) and Standard RAG (**8,647 ms**).
* **Word-Boundary Constraint Audit**: Identified and resolved a string-matching false positive (`"frivolous"` in `"nonfrivolous"`), ensuring exact word-boundary enforcement for legal compliance checks.

---

## 2. 4-Arm LegalBench Comparative Results Table

| Evaluation Arm | System Description | F1 Score | F1 Gain vs Base | F1 Gain vs RAG | Time-to-First-Token (TTFT) | TTFT Latency Reduction |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Arm 1** | **Base LLM** (Zero-Retrieval Control) | 0.264 | Baseline | N/A | 11,124.1 ms | Baseline |
| **Arm 2** | **Standard RAG** (Dense Vector Search) | 0.344 | +30.3% | Baseline | 8,647.3 ms | -22.3% |
| **Arm 3** | **OCTO Level 1** (Black-Box Prompt Hints) | **0.402** 🏆 | **+52.3%** 🚀 | **+16.9%** 📈 | **5,754.3 ms** ⚡ | **-48.3%** ⚡ |
| **Arm 4** | **OCTO Level 3** (Native GCCA Residual) | **0.386** 🚀 | **+46.2%** 🚀 | **+12.2%** 📈 | **5,775.9 ms** ⚡ | **-48.1%** ⚡ |

---

## 3. Deep-Dive Metrics Analysis

### A. F1 Score Progression (Statutory Interpretation & Recall)
- **Base LLM (`0.264`)**: Without grounding in specific statutory sections, the base LLM struggles with precise statutory cross-references.
- **Standard RAG (`0.344`)**: Dense text chunk retrieval provides statutory snippets, boosting accuracy by **+30%**.
- **OCTO Level 3 GCCA (`0.386`)**: Direct latent residual injection of statutory entity nodes yields a **+46% gain over Base LLM** and **+12% over Standard RAG**.
- **OCTO Level 1 (`0.402`)**: Structured entity graph headers and statutory rule constraints give the model precise guidance, achieving the top F1 score of **0.402** (**+52% over Base LLM**).

### B. Time-To-First-Token (TTFT) Latency Reduction
- **Base LLM**: `11,124.1 ms`
- **Standard RAG**: `8,647.3 ms`
- **OCTO Level 1 & Level 3**: **`5,754 ms`** (**48% faster than Base LLM**, **33% faster than Standard RAG**)
- **Key Takeaway**: Providing compact, structured world-state headers reduces prefill token search overhead on vLLM, nearly doubling response initiation speeds on legal queries.

---

## 4. Code Audit & Fix: Constraint Checker False Positive
- **Issue Discovered**: The constraint checker previously performed a naive substring check for `"frivolous"`. Because the correct legal answer contained the word `"nonfrivolous"`, it triggered a false-positive violation.
- **Resolution**: Updated [`check_constraint_violation()`](file:///home/rich/share/work/octo/benchmarks/run_4arm_benchmark.py#L92) to use strict word-boundary regex (`\bfrivolous\b`).
