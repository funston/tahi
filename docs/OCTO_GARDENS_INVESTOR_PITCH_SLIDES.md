# OCTO Investor Pitch — Slide Deck Outline

A 12-slide deck derived from `docs/OCTO_INVESTOR_PITCH.md`. Each slide includes the headline, key bullets, and visual recommendation.

---

## Slide 1: Title

**Headline:** OCTO — The World Coprocessor for Domain-Grounded AI

**Subhead:** Turn any LLM into a trustworthy domain specialist without retraining.

**Visual:** Octo value-proposition diagram (`diagrams/octo_value_proposition.svg`).

**Speaker note:** Open with the one-liner: Octo turns general-purpose LLMs into trustworthy domain specialists through structured, retrieval-augmented reasoning.

---

## Slide 2: The Problem

**Headline:** LLMs Are Generalists — and They Fail in High-Stakes Domains

**Bullets:**
- Static knowledge frozen at training time.
- RAG retrieves text, not structure; it cannot enforce hard constraints.
- Outputs are unauditable — no trace of what influenced the answer.

**Visual:** Split-screen: confident LLM on one side; wrong SQL / wrong drug interaction / compliance violation on the other.

**Speaker note:** Use one concrete example: GPT-4 writes beautiful SQL but gets the schema wrong.

---

## Slide 3: The Bet

**Headline:** As LLMs Commoditize, Differentiation Moves to Grounding

**Bullets:**
- Model capability is rising; enterprise value shifts to data, domain knowledge, and reasoning.
- The winners will own the layer that makes models correct, constrained, and auditable.
- OCTO owns that layer.

**Visual:** Simple trend line: model capability flattening, value of grounding rising.

---

## Slide 4: What OCTO Is

**Headline:** A World-Model Coprocessor for LLMs

**Bullets:**
- Maintains an explicit, typed knowledge graph separate from the LLM.
- At inference time: capture → retrieve → plan → rule-check → simulate → fuse → inject.
- Produces a Control Packet that guides generation with constraints and provenance.

**Visual:** Cognitive lifecycle diagram (`diagrams/octo_cognitive_lifecycle.svg`).

---

## Slide 5: Why This Is Not RAG

**Headline:** RAG Retrieves Text. OCTO Reasons Over Structure.

| | RAG | OCTO |
|---|---|---|
| Knowledge shape | text chunks | entities, relations, constraints |
| Hard constraints | none | deterministic enforcement |
| Provenance | chunk list | full reasoning trace |
| Updates | re-index | versioned world model |

**Visual:** Octo vs. alternatives diagram (`diagrams/octo_vs_alternatives.svg`).

---

## Slide 6: Integration Levels

**Headline:** Shipping Today; Native Tomorrow

**Bullets:**
- **Level 1 (shipping):** structured Control Packet consumed by any LLM API.
- **Level 2:** trainable adapter native to a frozen LLM (RETRO-style cross-attention).
- **Level 3:** direct residual-stream injection for deepest control.

**Visual:** Integration levels diagram (`diagrams/octo_integration_levels.svg`).

---

## Slide 7: Traction

**Headline:** Working Runtime + Reference Implementations

**Bullets:**
- Core runtime: capture, retrieval, planner, rule engine, simulator, fusion, integration.
- Reference domains: mass spectrometry, biomarkers, text-to-SQL (BIRD/Spider).
- World Model Store with versioned, reproducible builds.
- Open-source core.

**Visual:** Component overview diagram (`diagrams/octo_component_overview.svg`).

---

## Slide 8: Market

**Headline:** $10B+ Immediate Verticals; $100B+ Platform Opportunity

**Bullets:**
- Immediate: SQL/analytics, life sciences, compliance, legal reasoning.
- Platform: World Model Marketplace, enterprise integrations, continuous learning without retraining.
- Wedge: domains where RAG is insufficient and fine-tuning is too expensive.

**Visual:** Market map or vertical grid.

---

## Slide 9: Moat

**Headline:** Defensible Through Structure, Not Scale

**Bullets:**
- Explicit structured reasoning: entities, relations, constraints, hypotheses, provenance.
- Domain world models become data moats.
- Provenance by design — every output is inspectable.
- Modular architecture: Level 1 value today, Level 2/3 optionality tomorrow.

**Visual:** Lock icon + layered stack diagram.

---

## Slide 10: Roadmap

**Headline:** 0–18 Month Path to Product

**Near term (0–6 mo):**
- Harden mass-spec benchmark.
- Real biomedical ontology integration.
- vLLM-compatible Level 2 adapter prototype.

**Medium term (6–18 mo):**
- 2–3 design partners in bio or analytics.
- Hosted world-model versioning pipeline.
- Joint benchmark vs. RAG/GraphRAG on constrained tasks.

**Visual:** Roadmap timeline.

---

## Slide 11: The Ask

**Headline:** Raising [$X]

**Bullets:**
- Harden reference implementations into defensible benchmarks.
- Build and ship a Level 2 native adapter.
- Secure 2–3 design partners.
- Grow core engineering + domain-expert team.

**Visual:** Simple pie chart of use of funds.

---

## Slide 12: Closing

**Headline:** The Company That Controls Semantic Grounding Controls the AI Stack

**Bullets:**
- OCTO is fundamental infrastructure for grounded, verifiable AI.
- Not another AI tool — the reasoning layer between enterprise knowledge and generative models.

**Visual:** Octo Gardens coprocessor architecture diagram (`diagrams/octo_coprocessor_architecture.svg`).

**Speaker note:** End with the concrete next step: a demo of OCTO vs. RAG on a real SQL or multi-hop QA task.

---

## Appendix Slides (Optional)

- **A1:** RETRO/ANN comparison (`docs/RETRO_ANN_VS_OCTO.md`).
- **A2:** RelationalAI joint architecture (`diagrams/octo_relationalai_joint_architecture.svg`).
- **A3:** Detailed competitive landscape table.
- **A4:** Risk factors and mitigations.

---

## Speaker Notes Summary

- Lead with the problem, not the technology.
- Use one concrete failure of RAG/fine-tuning before explaining OCTO.
- Emphasize that OCTO is model-agnostic and ships at Level 1 today.
- Close every meeting with a live-demo offer.
