# OCTO Benchmarking Guide & Protocols

**Last Updated:** 2026-08-03  
**Status:** Verified Operational Benchmark Suites  

---

## Benchmark Philosophy

OCTO is evaluated across three strict, non-negotiable measurement principles:

1. **Identity Control Assertions**: Level 3 in-process GCCA native runs MUST verify that setting $\alpha=0$ produces exact token-for-token identity with the base model ($h + \tanh(0) \cdot \text{attn} = h$). If $\alpha=0$ differs from `base`, the harness is corrupt and the run is rejected.
2. **Polarity-Aware Truthfulness Metrics**: Lexical groundedness is replaced by a passage-level max-aggregated DeBERTa NLI Cross-Encoder ($p_{\text{entailment}} - p_{\text{contradiction}}$) to evaluate claim validity across numeric, entity, negation, and swap perturbations.
3. **Cryptographic Manifest & Schema-Locked Artifacts**: Every published metric MUST be programmatically rendered from a machine-readable JSON artifact containing a cryptographic manifest (`git_sha`, `seed`, `strict_mode`, `encoder`).

---

## 1. Level 3 In-Process Native GCCA + GNN Benchmark

Evaluates in-process PyTorch model generation with live `OctoNativeAdapter` forward hooks injecting 2-layer RGAT GNN topological memory tensors into intermediate hidden layers.

### Command Execution

```bash
PYTHONPATH=src python benchmarks/run_l3_native.py \
    --model Qwen/Qwen2.5-1.5B-Instruct \
    --checkpoint checkpoints/gcca/gcca_epoch2.pt \
    --questions data/enterprise_rag/questions.jsonl \
    --corpus data/enterprise_rag/sources \
    --limit 50 \
    --output benchmarks/results/l3_native_run.json
```

### Evaluated Arms
- `base`: Pure LLM completion (floor baseline).
- `rag_prompt`: Standard RAG context pasted into text prompt.
- `l3_alpha0`: Native GCCA adapter live with $\alpha=0$ (identity control check).
- `l3_trained`: Native GCCA adapter live with GNN topological memory tensors ($\alpha > 0$).

---

## 2. NLI Fragment Verification Benchmark

Evaluates retrieval truthfulness and claim precision over Kùzu C++ Property Graph tables using Additive Structural Support scoring.

### Command Execution

```bash
PYTHONPATH=src python benchmarks/run_fragment_verification.py \
    --questions data/enterprise_rag/questions.jsonl \
    --corpus data/enterprise_rag/sources \
    --n-fragments 50 \
    --max-docs 10000 \
    --output benchmarks/results/fragment_verification.json
```

---

## 3. Subsystem Verification Test Suite

Before running large-scale benchmarks, verify all 5 core subsystems:

```bash
pytest tests/test_kuzu_world_model_integration.py tests/test_gnn_encoder.py \
       tests/test_gcca_falsification.py tests/test_nli_evaluator.py tests/test_semantic_grounding.py
```
