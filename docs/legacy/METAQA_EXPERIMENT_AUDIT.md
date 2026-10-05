# Audit Report: Detailed Analysis of the MetaQA Experiment Run

**Document Version:** 1.0.0  
**Date:** 2026-08-05  
**Auditor:** Antigravity AI  
**Target Script:** `scripts/run_metaqa_error_correction.py`

---

## 1. Executive Summary

Rich rightfully flagged that the previous script output ("Graph fixed 2, broke 1") was highly suspect. 

We conducted a line-by-line code audit and per-item inspection of the raw generation logs in `data/metaqa/results/metaqa_transition_results.json`. Here are the direct, un-spun answers to Rich's 4 questions:

---

## 2. Answers to Rich's 4 Audit Questions

### Question 1: Did you do a detailed analysis for EACH prompt of what the graph query was?
**ANSWER: NO.**  
We ran a batch loop and did not inspect individual prompt queries or subgraphs until your prompt. 

When we inspected item #1:
- **Question**: *"the movies that share actors with the movie Billy Budd were in which languages"*
- **Target Answer**: `['German', 'French', 'Italian']`
- **What the Graph Query Fetched**: `Billy Budd -> actor -> movie`. It fetched actors and movie titles, but **completely missed the 3rd hop (`movie -> language`)**!
- **Result**: The LLM had no language information in its prompt, so it listed movie titles instead of languages.

---

### Question 2: Was the query correct?
**ANSWER: NO.**  
The graph traversal in `scripts/run_metaqa_error_correction.py` used an unguided 3-hop BFS (`list(graph.neighbors(node))[:8]`).

Because it was unguided:
- It retrieved arbitrary neighbor edges (e.g. `written_by`, `starred_in`, `release_year`) instead of following the **specific predicate chain** requested in the question (e.g. `actor -> movie -> in_language`).
- It truncated at arbitrary limits (`[:8]`, `[:5]`, `[:3]`), cutting off the actual gold target entities before they could reach the LLM.

---

### Question 3: Did it return anything?
**ANSWER: YES, BUT IT RETURNED NOISE.**  
The graph queries returned 30-line text strings of graph edges, but because the BFS was unguided, it returned movie names, release years, and directors when the question asked for **languages** or **genres**.

---

### Question 4: Is this running at the generation step?
**ANSWER: NO. THIS WAS PROMPT RAG AGAIN.**  
The script prepended `graph_context` into `gcca_prompt` and sent it to OpenAI's `gpt-4o-mini` API **BEFORE** generation. 

It did **NOT** run native TAHI GCCA cross-attention (`TahiNativeAdapter` in `src/tahi/native/`) during autoregressive token generation!

---

## 3. What Needs to Be Fixed for a Valid Experiment

1. **Native In-Generation GCCA Execution**: Use native TAHI `TahiNativeAdapter` on a local open-weight model (`Qwen2.5-0.5B-Instruct` or `Llama-3.2-1B`) so cross-attention runs **DURING GENERATION**, not as prepended text.
2. **Predicate-Guided Path Traversal**: Parse the target relation in the question (e.g. `directed_by`, `in_language`) so 3-hop traversal actually follows the path to the gold target entities.
3. **Exact Match Evaluation**: Score exact entity set matches without sentence wrapper noise.
