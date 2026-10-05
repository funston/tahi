# RETRO/ANN-Scale RAG vs. TAHI

This document compares massive Approximate-Nearest-Neighbor retrieval architectures (RETRO, InstructRetro, DiskANN/Starling-style out-of-core vector engines) with TAHI's world-coprocessor approach. It also identifies which RETRO/ANN engineering ideas TAHI can adopt.

## TL;DR

- **RETRO/ANN** optimizes for *recall coverage* over enormous unstructured corpora. It is a better answer engine for open-domain, long-tail factual questions.
- **TAHI** optimizes for *correctness, structure, and auditability* in constrained domains. It is a better reasoning layer where wrong answers have real costs.
- The two are **complementary**, not substitutes. TAHI should stay structured at the semantic layer and optionally borrow RETRO engineering for native integration and large-scale retrieval.
- The upfront cost of a 10 PB+ RETRO system is massive; TAHI's cost is dominated by ontology/world-model curation, not storage hardware.

---

## What RETRO/ANN-Scale RAG Actually Does

A RETRO-style system:

1. Chops a large corpus into small chunks (often 64 tokens).
2. Encodes each chunk into a dense vector.
3. Stores vectors in a fast ANN index (FAISS, ScaNN, DiskANN, Starling, etc.).
4. During autoregressive decoding, retrieves nearest-neighbor chunks every N tokens.
5. Feeds retrieved vectors into the LLM through chunked cross-attention (CCA) or prompt prepending.

The architecture in `RAG with ANN.txt` proposes a four-stage hardware roadmap ending at 10+ TB of out-of-core NVMe-backed vectors, with Gated Chunked Cross-Attention (GCCA) adapters on a frozen base model.

---

## Direct Comparison

| Dimension | RETRO / Large-Scale ANN RAG | TAHI |
|---|---|---|
| **Primary goal** | Factual recall from huge corpora | Correct, auditable reasoning in constrained domains |
| **Knowledge representation** | 64-token text chunks as dense vectors | Entities, relations, constraints, rules, provenance |
| **Retrieval signal** | Vector similarity | Structured graph + semantic embeddings + rules |
| **Hard constraints** | None — model may still violate them | Enforced deterministically before generation |
| **Provenance** | List of retrieved chunks | Trace of entities, rules, hypotheses, fused signal |
| **Update model** | Re-index vectors | Versioned world-model update |
| **Typical corpus** | 1–10+ TB of unstructured text | MB–GB of structured domain knowledge |
| **Integration depth** | Native residual/adapter (deep) | Levels 1–3; Level 1 shipping today |
| **Hallucination mode** | May hallucinate by trusting wrong chunks | May hallucinate if world model is wrong, but rules/simulation can catch it |
| **Best domains** | Open QA, general knowledge, multi-hop document synthesis | SQL, biomarkers, compliance, mass spec, legal reasoning |

---

## Why "1–10 PB of Data" Does Not Guarantee Correctness

Scale improves *coverage*, not *correctness*:

1. **ANN returns similar, not true.** A vector index finds chunks that are statistically close to the query embedding. In a 10 PB corpus, there are millions of plausible-sounding but incorrect chunks.
2. **No semantic validation.** The model still generates freely. A retrieved chunk can be misinterpreted, over-weighted, or contradicted by another retrieved chunk.
3. **No explicit reasoning trace.** You know which chunks were retrieved, but not why the model combined them the way it did.
4. **Distractor sensitivity.** As the ANN doc itself notes, you must train the model with hard negatives so it learns to ignore noisy chunks. That is an admission that retrieval alone is not enough.
5. **Domain constraints are absent.** A 10 PB corpus can tell you many things about SQL, but it cannot enforce that a generated query references only existing columns or respects a foreign-key graph.

**Bottom line:** RETRO reduces parametric hallucination by giving the model more external context, but it does not eliminate generative hallucination or enforce domain correctness.

---

## Cost Comparison

### RETRO / Large-Scale ANN

| Cost category | Scale | Notes |
|---|---|---|
| **Embedding compute** | Very high | Every token in the corpus must be encoded. 2T tokens ≈ tens of thousands of GPU-hours. |
| **Storage** | 1–10+ PB NVMe | Out-of-core engines (DiskANN/Starling) need fast flash. 10 PB of enterprise NVMe is $500K–$2M+ in hardware alone. |
| **Serving hardware** | Multi-GPU cluster | Blackwell-class GPUs, high PCIe bandwidth, dedicated retrieval workers. |
| **Engineering team** | Large | Custom decoding loop, ANN engine tuning, adapter training, prefetch pipelines, distributed serving. |
| **Maintenance** | High | Index rebuilds on data changes, embedding model upgrades require alignment adapters, capacity planning. |
| **Energy / DC footprint** | High | Continuous random reads across NVMe arrays plus GPU inference. |

Rough order-of-magnitude for a Stage 4 deployment: **$1M–$5M+ in hardware and embedding compute before the first production query**, plus a team of 5–10 specialized engineers.

### TAHI

| Cost category | Scale | Notes |
|---|---|---|
| **World-model construction** | Moderate | Requires domain expertise to build ontologies, schema graphs, and rule sets. Can be 90% automated for SQL schema world models. |
| **Storage** | Small | World models are structured graphs (JSON/Gzip). Even large enterprise schemas fit in MB–GB. |
| **Serving hardware** | Standard | Runs on existing LLM serving stacks. No custom retrieval hardware required at Level 1. |
| **Engineering team** | Small–medium | Core framework + domain engineers. No custom CUDA kernels or distributed ANN tuning needed at Level 1. |
| **Maintenance** | Moderate | Versioned world-model updates; no full re-indexing of a PB-scale corpus. |
| **Energy / DC footprint** | Low | Graph retrieval and rule execution are cheap compared to continuous ANN lookups across NVMe. |

Rough order-of-magnitude for a production SQL coprocessor: **$10K–$100K in engineering time per domain**, plus standard LLM inference costs.

### When the Cost Models Flip

- **TAHI is cheaper** when the domain is narrow and structured (most enterprise SQL, compliance, biotech workflows).
- **RETRO/ANN is cheaper per query** only when the knowledge is inherently unstructured and web-scale (open-domain QA, research synthesis over full paper corpora).

---

## What TAHI Should Borrow from RETRO/ANN

Despite the philosophical differences, RETRO/ANN engineering is directly useful for TAHI's Level 2/3 roadmap.

### 1. Native adapter integration (Level 2/3)

RETRO's Gated Chunked Cross-Attention (GCCA) is a concrete implementation of TAHI's "native coprocessor mode."

| RETRO idea | TAHI application |
|---|---|
| Frozen base LLM + trainable cross-attention adapters | `NativeIntegration` / `ScalarLMNativeIntegration` |
| `tanh(α)` gate initialized to 0 | Lets TAHI start identical to base LLM and learn to open the gate |
| 1-chunk causal offset | Ensures retrieved state conditions future tokens without leakage |
| Chunked retrieval every N tokens | TAHI world-state updates can be chunked similarly |

Reference implementation path: `src/tahi/integration.py` → `NativeIntegration` and `knowledge_attention.py`.

### 2. Late chunking for document evidence


Application: enrichment step in world-model builders that ingests documents.

### 3. Out-of-core vector storage for large world models

`WorldModelStore` currently uses gzip-compressed JSON. For world models that grow to hundreds of millions of nodes, Tahi can adopt:

- **Filtered-DiskANN** for metadata-filtered vector search
- **Starling** for sector-aligned NVMe layout
- **FreshDiskANN** for real-time incremental updates

This is only needed if a single world model exceeds RAM. Most current TAHI domains do not need it.

### 4. Asynchronous prefetch pipelines

At Level 3, retrieval latency matters. RETRO's async prefetch of the next chunk's retrieval vector can hide latency behind the forward pass.

Application: `TahiRuntime.infer()` prefetch path for native mode.

### 5. Orthogonal embedding-space alignment

If TAHI upgrades its embedding model, it can use Procrustes alignment or a small MLP to map old vectors into the new space without rebuilding adapters.

Application: `WorldModelStore` migration tooling.

---

## Recommended Positioning

Use this framing in investor and technical conversations:

> "RETRO-style architectures solve open-domain recall by retrieving from trillions of tokens. TAHI solves constrained-domain correctness by reasoning over structured world models. We do not compete on corpus size; we compete on correctness, provenance, and constraint enforcement. Where RETRO/ANN engineering is useful — native cross-attention adapters, large-scale retrieval backends — we adopt those techniques at our Level 2/3 integration layers."

---

## Summary Table: When to Use Which

| Scenario | Use RETRO/ANN | Use TAHI |
|---|---|---|
| Open-domain QA over web-scale corpora | ✅ | ❌ |
| Multi-hop synthesis over millions of papers | ✅ | ⚠️ only with document enrichment |
| Text-to-SQL with schema correctness | ❌ | ✅ |
| Biomarker interpretation with entity normalization | ❌ | ✅ |
| Regulatory compliance / audit-trail decisions | ❌ | ✅ |
| Real-time knowledge updates without retraining | ✅ | ✅ |
| Minimize hallucination in unconstrained domains | ⚠️ helps | ⚠️ helps differently |
| Minimize hallucination in constrained domains | ❌ | ✅ |

---

## References

- DeepMind RETRO: Improving Language Models by Retrieving from Trillions of Tokens (Borgeaud et al., 2022)
- NVIDIA InstructRetro: Instruction Tuning Post Retrieval-Augmented Pretraining (Wang et al., 2023)
- Filtered-DiskANN (Gollapudi et al., WWW 2023)
- Starling (Wang et al., SIGMOD 2024)
- FreshDiskANN (Singh et al., SIGMOD 2022)
- Jina AI Late Chunking (Günther et al., 2024)
- RetroLLM (Li et al., ACL 2025)
