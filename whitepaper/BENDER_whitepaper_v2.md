# BENDER
## A World-Model Coprocessor Architecture for Large Language Models

**Author:** Rich Schiavi  
**Date:** 2026

### Acknowledgment

The name **BENDER** is both a playful reference to the robot from *Futurama* and a set of internal backronyms:
- **B**idirectional **E**ntity **N**etwork and **D**eterministic **E**xecution **R**untime
- **B**iomedical **E**ntity **N**etwork and **D**iagnostic **E**valuation **R**untime
- **B**enchmark for **E**ntity **N**etworks and **D**ynamic **E**valuation **R**esults

---

## 1. Abstract

Large Language Models (LLMs) have demonstrated strong capabilities in natural language understanding and generation. However, their reliance on implicit world models, internalized during training, imposes limits on factual precision, logical consistency, and domain-specific reasoning. Prompt-side methods such as Retrieval-Augmented Generation (RAG) and GraphRAG improve access to external information, but they remain constrained by context windows, token cost, and the computational burden of attending over long prompts.

We propose **BENDER**, a World-Model Coprocessor architecture that separates structured reasoning from probabilistic language generation. BENDER maintains an explicit, typed world model and a parallel runtime that performs retrieval, planning, rule application, and simulation. The output of this runtime is not merely text for a prompt, but a structured **Control Packet** containing entities, constraints, hypotheses, and a **fused latent signal** intended for integration into the model's inference path.

This paper describes the BENDER architecture, the Phase 1 implementation of its runtime, its separation from domain-specific world models, and its integration strategy with high-performance serving stacks such as ScalarLM/vLLM.

## 2. The Problem: Implicit World Models are Weak Interfaces

Implicit world models in LLMs suffer from four primary limitations:

1. **Staleness:** Internalized knowledge is frozen at the point of training.
2. **Opacity:** Reasoning steps are hidden, making provenance and auditing difficult.
3. **Inconsistency:** Probabilistic generation lacks the hard constraints of symbolic systems.
4. **Context Bottleneck:** Injecting large-scale domain knowledge into a prompt is expensive and subject to "lost in the middle" effects.

RAG and GraphRAG help with staleness, but they do not fully solve the context bottleneck or consistency problems. They still rely on the model reconstructing structure from text, rather than operating over explicit runtime state.

## 3. The BENDER Architecture

BENDER is structured as a **coprocessor loop** that runs in parallel with LLM inference.

### 3.1 Components

- **World Model:** A persistent, typed knowledge graph with nodes (entities) and edges (relations).
- **BenderRuntime:** The orchestration engine that manages the cognitive lifecycle of a request.
- **ModelIntegration:** An interface for capturing model-side state and injecting coprocessor-side state.
- **Planner:** Generates a deterministic reasoning plan based on the query and retrieved state.
- **RuleEngine:** Applies domain-specific hard constraints and soft preferences.
- **Simulator:** Performs lightweight "mental simulation" to test hypotheses or predict outcomes.
- **FusionModule:** Combines model-side and graph-side signals into a fused latent vector.

### 3.2 The Cognitive Lifecycle

1. **Capture:** The model's query (and optionally its hidden state) is captured.
2. **Retrieve:** Relevant nodes and relations are fetched from the World Model.
3. **Plan:** A reasoning plan is constructed to address the query.
4. **Apply Rules:** Domain-specific logic is applied to the active state.
5. **Simulate:** Plausible outcomes or hypothesis implications are tested.
6. **Fuse:** Structured state and model state are blended into a unified signal.
7. **Inject:** A structured Control Packet is returned to the model's inference loop.

## 4. Native Hidden-State Integration

The strongest form of coprocessor design is **Level 2/3 Integration**, where the coprocessor's signal directly influences the model's latent stream during decoding.

It is important to separate this from weaker integration levels. A system can still use the BENDER runtime to produce structured control packets for prompt-side or orchestration-side consumption, but that is not the same as native coprocessor integration. The strongest architectural claim of BENDER depends on request-scoped native influence inside the inference server.

### 4.1 The Fused Vector

The `fused_vector` in a Control Packet is a numerical representation of the coprocessor's "opinion" on the current state. Unlike prompt text, this vector can be injected into:

- **Residual Blocks:** Added to MLP or attention outputs.
- **Cross-Attention:** Used as an additional key/value set in specialized layers.
- **Adapter Modules:** Activating request-scoped weights (e.g., via Tokenformer).

### 4.2 Why Native Integration Matters

Native integration avoids the cost of repeatedly serializing domain state into prompts. A compact fused vector can represent constraints or structured context far more efficiently than thousands of tokens of serialized text. In principle, this allows much larger domain grounding than prompt-side retrieval alone.

## 5. BENDER vs. The Alternatives

BENDER is frequently compared to RAG, GraphRAG, and post-training. Here we define the core technical distinctions.

### 5.1 Why BENDER is not "just RAG"
- **Inference-side vs. prompt-side:** Traditional RAG is a pre-inference text transformation. BENDER is intended as an intra-inference intervention that can supply structured state directly to the model path.
- **Structured state vs. retrieved passages:** RAG returns text. BENDER maintains entities, relations, constraints, hypotheses, and provenance as explicit runtime objects.
- **Persistent control vs. repeated prompt reconstruction:** RAG repeatedly asks the model to reconstruct structure from prompt content. BENDER is designed to provide a persistent structured influence during reasoning and generation.

### 5.2 Why BENDER is not "just Post-training"
- **World-state volatility:** Many domains change too quickly for retraining to be the only adaptation path.
- **Model preservation:** Fine-tuning on narrow domains can degrade general behavior. BENDER aims to preserve the base model while adding structured runtime specialization.
- **Portability:** The world model is an external asset that can, in principle, be reused across model backends without retraining the base model.

## 6. Reference World Models and Stress Tests

BENDER should be evaluated through domain implementations that sit on top of the core runtime, not by embedding benchmark logic into the runtime itself.

### 6.1 Spider 2.0 as a Stress Test

Spider 2.0 remains useful as a stress test for schema grounding, planning, and execution-time repair. It is best treated as a benchmark implementation layered on top of BENDER, not as the definition of BENDER itself.

### 6.2 Biomedical Interpretation

A biomedical world model demonstrates a higher-value class of tasks:

1. normalize biomarkers, diseases, assays, targets, and therapies,
2. preserve provenance across evidence sources,
3. derive hypotheses from explicit entity and relation structure rather than retrieved text alone.

This is strategically important because the domain is knowledge-dense, changes frequently, and is too specialized to justify retraining a large model for every new evidence state.

### 6.3 Mass Spectrometry Interpretation

Mass spectrometry is an especially strong demonstration domain because it requires:

1. hard mass constraints,
2. polarity and adduct compatibility,
3. instrument- and sample-context-aware reasoning,
4. provenance attached to candidate explanations.

This makes it a strong counterexample to the claim that a vector database plus RAG is sufficient for specialized scientific interpretation.

## 7. Strategic Implementation with ScalarLM/vLLM

One credible path for BENDER is integration into a high-performance serving stack such as ScalarLM's `vllm-fork`. This allows for **request-scoped native influence**:

1. **Tokenformer Surgeon:** Wraps late MLP layers to accept coprocessor residuals.
2. **ActiveBenderBatch:** Manages per-request coprocessor contexts for scheduled batches.
3. **Worker-Side Activation:** Injects the `fused_vector` into the forward pass without global weight swaps.

In the current repository, this distinction matters operationally:

- the core BENDER runtime can already run in structured control mode,
- the full native mode requires backend support such as the current ScalarLM branch,
- benchmark runs that only use prompt-side or heuristic generation should not be described as native coprocessor results.

## 8. Conclusion: The Coprocessor Moat

BENDER represents a shift from models that rely only on implicit world state toward systems that can use explicit runtime cognition. By separating structured reasoning from probabilistic language generation, the architecture aims to deliver stronger domain control, provenance, and adaptability than prompt-side methods alone.

The architectural moat, if the system is executed well, lies in **request-scoped native influence**: guiding inference with structured world-model state in a way that is efficient, updateable, and portable across domains and model backends.
