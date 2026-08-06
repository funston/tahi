# OCTO Documentation

Welcome to the official documentation suite for **OCTO**, an AI-driven World-Model Coprocessor framework for Large Language Models.

---

## Core Documentation

- 🚀 [**Quick Start**](QUICKSTART.md) — Installation, environment setup, and runnable entrypoints.
- 📐 [**Architecture**](ARCHITECTURE.md) — Technical deep-dive on Kùzu C++ Property Graph, PyTorch RGAT GNN Encoders, and Level 3 Native GCCA hidden-state injection.
- 📊 [**Platform Status**](STATUS.md) — Present-day platform health, verified benchmark metrics, and subsystem test suite coverage.
- 🧪 [**Benchmarking Guide**](BENCHMARKING.md) — Complete benchmark reproduction runbook, identity control assertions ($\alpha=0$), and NLI evaluators.
- 💼 [**Investor Pitch**](INVESTOR_PITCH.md) — Executive pitch deck, value proposition, and market opportunity.
- 📋 [**RETRO Pre-Flight POC Plan**](RETRO_POC.txt) — 6-day zero-hardware-cost validation specification to de-risk $5M capital expenditure.
- 📄 [**Research Paper (Systems)**](RESEARCH_PAPER.md) — *OCTO: Latent Relational Graph Attention Networks for Direct Hidden-State Injection in Frozen Large Language Models* (NeurIPS / ICLR).
- 🔬 [**Research Paper (Evaluation Methodology)**](EVAL_METHODOLOGY_PAPER.md) — *Inert Instruments: Silent Failure Modes in RAG Faithfulness Evaluation* (NeurIPS D&B / ACM REP).

---

## Subsystem Code Map

- `src/octo/graph/gnn_encoder.py` — PyTorch Relational Graph Attention Network (RGAT) Subgraph Encoder.
- `src/octo/world_state.py` — Kùzu C++ Property Graph Engine & Additive Structural Support scoring.
- `src/octo/native/gcca_layer.py` — PyTorch Gated Chunked Cross-Attention (GCCA) residual layer.
- `src/octo/eval/nli_evaluator.py` — DeBERTa NLI Cross-Encoder with Passage-Level Max Aggregation.

---

## Archives & Historical Audits

All legacy documentation, initial analysis notes, and secondary drafts are archived in [`docs/archive/`](archive/).
