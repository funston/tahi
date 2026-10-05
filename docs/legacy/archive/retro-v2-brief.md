# RETRO-v2 — Architecture Review Brief

**A non-parametric, memory-augmented LLM:** freeze a normal instruction-tuned model and bolt on
lightweight adapters that, *during generation*, pull vectors from a huge external ANN vector database
straight into the model's middle layers — **every 64 tokens**. The pitch: recall of a
trillion-parameter model at a fraction of the compute, because world knowledge lives in the vector DB
(cheap, editable) while the frozen LLM only reasons.

- **Selected approach:** post-hoc retro-fit (<2% of params trained)
- **Our stake:** Stage 3 hardware = our Blackwell cluster
- **Corpus:** Semantic Scholar

---

## 1. The core bet — GCCA vs. prompt-RAG

Instead of pasting retrieved text into the prompt once (standard RAG), **Gated Chunked Cross-Attention
(GCCA)** queries the vector DB continuously as the model reasons — an "L1 cache for generation." Fixed
memory, and context that tracks the evolving line of thought.

| Dimension | Standard prompt-RAG | GCCA (proposed) |
|---|---|---|
| Where retrieval enters | Prompt window (input) | Intermediate layers (cross-attention) |
| When | Once, at step 0 | Every 64 tokens |
| Memory cost | O(L) — grows with context | O(1) — fixed |
| Serving | Off-the-shelf (vLLM) | Custom decode loop + adapter alignment |

> **⚠ Pressure-test this.** Their own evidence (InstructRetro): prompt-prepend with the gate closed
> (α=0) already captures **90%+ of the gains** on standard QA. GCCA is claimed to pay off only on
> **multi-hop reasoning, code-gen, and 100 TB-scale** corpora — **unproven for our use case.** This is
> the central question of the whole program.

## 2. Key design decisions

- **Post-hoc retro-fit (selected):** freeze 98%+ of the base model; train only `W_K`/`W_V` + a scalar
 gate. **~<$5k** vs $100k (InstructRetro) vs $1M+ (from scratch).
- **Flamingo gating:** `tanh(α)` initialized to 0 → bit-identical to the stock LLM at step 0, then
 learns to open. **Zero catastrophic forgetting.**
- **Late chunking:** full document through a long-context encoder *first*, then mean-pool 64-token spans
 — keeps global context vs. naive splitting.
- **Mismatched tokenizers are fine:** BERT/WordPiece retriever + BPE LLM; a trained linear adapter
 projects vectors into `d_model`. **No re-indexing on model swap.**
- **Heterogeneous quantization:** attention at FP16 (reasoning), FFN crushed to INT2/3 (facts now live
 in the RAG index) → ~60% VRAM cut.
- **Interleaved GCCA blocks:** cross-attention inserted every 4th layer — preserves early syntactic
 processing, adds latency deeper in the stack.

## 3. Four progressive stages

1. **Stage 1 — Local POC.** Math sandbox — prove α=0 identity, O(1) memory, causality masks.
 *Mac 24GB · 10k chunks · FAISS flat.*
2. **Stage 2 — Alignment.** Train adapters on QA triplets + distractors. Target +30%.
 *DGX Spark · 1M chunks.*
3. **Stage 3 — Pre-production (← our hardware).** Async prefetch, multi-hop (FRAMES) benchmarks.
 *4× RTX PRO 6000 Blackwell · 100M chunks.*
4. **Stage 4 — Enterprise.** Out-of-core engine, <2ms retrieval, live inserts.
 *Multi-node · 10TB+ NVMe · 10¹¹ chunks.*

The staged de-risking is genuinely sound (even the doc's own margin note agrees).

## 4. Why this is *our* conversation

**Stage 3 hardware is our Blackwell RTX PRO 6000 cluster.** The benchmark corpus is **Semantic Scholar**
— exactly what our pipeline already embeds. Our `the_machine` pipeline **is the ingestion/indexing
layer** that feeds this architecture.

**But real gaps between our pipeline and what this needs:**

- **Ingestion mode:** we do per-record embedding, not **late chunking** (full-doc encoder → 64-token
 child vectors). A new mode to build.
- **Retriever:** must be a fixed **64-token WordPiece/BGE** encoder; we currently run several models.
 Alignment needed.
- **Storage:** Stage 4 wants **<2ms** NVMe/DiskANN. Our NFS tops out ~**88 MB/s**. The out-of-core
 engine is a major separate build.

## 5. Risks & open questions

- **Flagged in the doc:** async prefetch depth (hiding NVMe latency), context contamination (retrieval
 duplicating prompt facts), PCIe bandwidth under 500 concurrent streams.
- **Scope:** is the ask a Stage 1–2 POC or the Stage 4 moonshot? Three novel systems (custom CCA decode,
 adapter alignment, out-of-core ANN engine) — each high integration risk.
- **Alignment data:** who builds the 100k instruction-context-response triplets + salient-span masking +
 distractor sets? InstructRetro calls this the primary open frontier.
- **Critical unknown:** does GCCA's multi-hop advantage over prompt-RAG actually materialize? Everything
 downstream rides on that one bet.

## 6. Questions to walk in with

1. What's the concrete near-term deliverable and budget — Stage 1 sandbox, or funding Stage 4?
2. Do we have PopQA / TriviaQA / FRAMES eval harnesses, and who builds the Semantic Scholar benchmark?
3. Does our embedding pipeline pivot to late chunking — and when?
4. What's the storage plan for the ANN datastore? NFS won't cut it; DiskANN/Starling is a big lift.
5. Can we prove GCCA > strong prompt-RAG *cheaply* at Stage 1–2 before committing to the custom serving stack?

---

*Source: `docs/RAG with ANN.txt`. Key papers: RETRO (Borgeaud et al., ICML 2022) · Flamingo (Alayrac et
al., NeurIPS 2022) · InstructRetro (Wang et al., NVIDIA 2023) · Late Chunking (Günther et al., 2024) ·
Filtered-DiskANN / Starling / FreshDiskANN · RetroLLM (Li et al., ACL 2025).*
