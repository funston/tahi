# Tahi Investor Brief

**Tahi: World-Model Coprocessor for Large Language Models**

---

## Overview

Tahi makes large language models specialist, updatable, and auditable by giving them an external structured memory — without retraining the model or using LoRA fine-tuning.

We are building the missing reasoning layer between enterprise domain knowledge and generative AI.

---

## The problem

Large language models are generalists. They cannot be trusted in specialized, high-stakes domains for three reasons:

1. **Static knowledge.** Training data is frozen at the moment of training. Updating the model requires expensive retraining or fine-tuning.
2. **Brittle retrieval.** RAG and GraphRAG stuff text into a prompt and ask the model to reconstruct structure. This fails when the domain has hard constraints — mass arithmetic, regulatory rules, drug interactions, SQL schema correctness.
3. **Unauditable outputs.** When a model makes a mistake, there is no explicit trace of what influenced the answer. This makes oversight, compliance, and safety hard.

Enterprises need a way to inject domain knowledge into AI systems that is:
- updateable without retraining,
- structured enough to enforce hard constraints,
- auditable enough to trust.

---

## The solution

Tahi Gardens is a **world-model coprocessor**.

It maintains an explicit, typed knowledge graph — a world model — separate from the LLM. At inference time, Tahi:

1. Captures the model-side query state.
2. Retrieves relevant entities, relations, and constraints from the world model.
3. Applies planning, deterministic rules, and lightweight simulation.
4. Produces a **Control Packet** with active entities, hypotheses, constraints, provenance, and a fused signal.
5. Injects that packet into the model path to guide generation.

Domain knowledge lives in a versioned **World Model Store**, separate from the base model. Updates are cheap, fast, and auditable.

---

## Integration levels

Tahi Gardens is designed to work at multiple levels of integration:

- **Level 1 — Structured Control Mode (shipping):** The Control Packet is consumed as structured context by an orchestration layer or prompt. Works with any LLM API today.
- **Level 2 — Adapter Native:** The fused vector is injected via a small trainable adapter (e.g., RETRO-style chunked cross-attention) on a frozen base model.
- **Level 3 — Request-Scoped Native:** Direct injection into the model’s residual stream. Requires inference-server support.

Current product operates at Level 1. Levels 2/3 are the research and differentiation roadmap.

---

## Why now

Three forces are converging:

1. **LLMs are commoditizing.** Model capabilities are rising, but differentiation is moving to data, domain knowledge, and reasoning.
2. **Enterprises are hitting the limits of RAG.** Vector search + prompt stuffing is insufficient for constrained, high-stakes domains.
3. **Regulatory and safety pressure is rising.** Finance, healthcare, and legal markets need auditable, constraint-aware AI.

The window for a structured-reasoning layer is opening now.

---

## Market

Primary verticals:

- **Life sciences / biotech:** biomarker interpretation, target profiling, evidence synthesis.
- **Scientific / industrial:** mass spectrometry, instrument interpretation, calibration-aware reasoning.
- **Financial services:** compliance, risk analysis, audit-trail-backed decisions.
- **Legal / enterprise knowledge:** contract analysis, precedent reasoning, policy enforcement.
- **Data analytics:** schema-grounded text-to-SQL and semantic query generation.

Initial wedge: domains where RAG is insufficient and retraining is too expensive.

---

## Traction

- **Working runtime and framework** (`src/tahi/`) with modular components: runtime, planner, rule engine, simulator, fusion module, integrations.
- **Reference implementations:**
 - **Mass spectrometry:** deterministic peak explanation with mass arithmetic and adduct rules; includes an A/B benchmark against retrieval baseline.
 - **Biomarker interpretation:** entity normalization and evidence-backed hypothesis generation.
 - **Text-to-SQL :** schema grounding and execution-time repair.
- **World Model Store:** versioned, reproducible world-model builds following FTI MLOps patterns.
- **Open-source core** with domain implementations layered on top.

---

## Competitive landscape

| Approach | Weakness | Tahi advantage |
|---|---|---|
| **Fine-tuning / LoRA** | Expensive, static, hard to audit | No model weight changes; updates are data-side |
| **RAG** | Model must infer structure from text | Provides structured entities, constraints, provenance |
| **GraphRAG** | Still prompt-side; no hard constraint enforcement | Deterministic rules + simulation before generation |
| **Tool use / function calling** | Model decides when to call tools | Constraints enforced deterministically, not suggested |
| **Custom hardware / weight-retrieval plays** | Unproven hardware latency and scaling; capital intensive | Runs on existing infrastructure; software-first |

---

## Business model

- **Open-core framework:** `src/tahi/` is reusable and extensible.
- **Domain implementations and services:** build and sell world models for specific verticals.
- **Enterprise platform:** hosted world-model builds, versioning, and integration into customer inference stacks.
- **Support and professional services:** implementation, ontology engineering, and evaluation.

---

## Technology moat

Tahi’s defensibility comes from:

1. **Explicit structured reasoning.** The runtime is designed around entities, relations, constraints, hypotheses, and provenance — not just embeddings.
2. **Domain world models.** Deep vertical knowledge is hard to build and becomes a data moat.
3. **Provenance by design.** Every output has an inspectable trace of what influenced it.
4. **Modular integration.** Works at Level 1 today; evolves toward Level 2/3 without architectural redesign.

---

## Roadmap

**Near term (0–6 months):**
- Harden mass-spec benchmark into a reproducible, publishable evaluation.
- Integrate real biomedical ontologies and evidence sources into the bio implementation.
- Ship a vLLM-compatible Level 2 adapter prototype using RETRO-style cross-attention.

**Medium term (6–18 months):**
- Land 2–3 design partners in bio or analytics.
- Build hosted world-model versioning and update pipeline.
- Publish joint benchmark showing Tahi superiority over RAG/GraphRAG on constrained tasks.

**Long term (18–36 months):**
- Native integration with major inference servers.
- Multi-tenant enterprise platform.
- Expansion into additional regulated verticals.

---

## The ask

We are raising [$X] to:

1. Harden reference implementations into defensible benchmarks.
2. Build and ship a Level 2 native adapter on existing serving stacks.
3. Secure 2–3 design partners in biomarker interpretation and analytics.
4. Grow the core engineering and domain-expert team.

---

## Risk factors

- **Native integration timing.** Level 2/3 adapters require engineering effort and alignment with inference-server ecosystems.
- **Market education.** Customers may initially confuse Tahi with RAG or GraphRAG.
- **Vertical depth.** Success depends on building high-quality domain world models, which requires domain expertise.
- **Competition.** Large model providers and RAG vendors may add structured-reasoning features.

We mitigate these by focusing on verticals with hard constraints, shipping value at Level 1 today, and making the architecture modular enough to absorb future backend improvements.

---

## Bottom line

Tahi Gardens is the structured reasoning layer that turns general-purpose LLMs into trustworthy domain specialists.

It is the safest, most practical path to the world-coprocessor vision: no custom hardware, no model retraining, and a clear route to product traction.

