# OCTO Investor Strategy

## One-sentence pitch

OCTO turns general-purpose LLMs into trustworthy domain specialists by attaching external, structured **world-model coprocessors** — without retraining or fine-tuning the underlying model.

## The problem

Enterprises are hitting a wall with LLMs in high-stakes domains:

- **Hallucination** is unacceptable in finance, defense, and healthcare.
- **Fine-tuning is expensive and slow**: retrain a model every time policy, schema, or knowledge changes.
- **Proprietary data cannot leave the environment**: banks and defense agencies cannot send internal schemas to OpenAI for fine-tuning.
- **RAG is too loose**: retrieving chunks of text does not enforce constraints, relationships, or provenance.

The missing layer is a structured reasoning layer between the model and domain knowledge.

## What OCTO does

OCTO builds an explicit, typed **world model** — entities, relations, constraints, and provenance — separate from the LLM. At inference time, the OCTO runtime:

1. Captures the model-side query state.
2. Retrieves structured world state.
3. Reasons over entities, relations, constraints, and hypotheses.
4. Fuses model-side and graph-side signals.
5. Emits a model-facing control packet with constraints and provenance.

The LLM stays frozen. The domain knowledge lives in OCTO.

## Two business paths

### Path 1: Proprietary world-model coprocessors (enterprise)

**Target customers:** Banks, defense, healthcare, pharma, legal.

**How it works:**

- Customer gives OCTO access to internal schemas, documentation, query logs, and entity graphs.
- OCTO builds a structured world model / coprocessor for that domain.
- The customer's LLM — GPT-4o, Claude, Llama, whatever — calls OCTO at inference time.
- No LLM fine-tuning. No proprietary data in model weights.

**Why it is valuable:**

- **Data moat:** The coprocessor is built from data no competitor has.
- **Compliance:** Sensitive data stays inside the customer's environment.
- **Switching costs:** Once the coprocessor encodes a domain, replacing it is hard.
- **High willingness to pay:** Wrong answers in these domains are expensive.

**Examples:**

- Goldman Sachs LEGEND query language → natural language to LEGEND via coprocessor.
- Military doctrine and intel graphs → grounded reasoning over classified entities.
- Pharma compound databases → constraint-enforced drug-interaction queries.

### Path 2: Dynamic world-model coprocessors (generalist / benchmarks)

**Target customers:** SaaS, analytics platforms, benchmark credibility.

**How it works:**

- OCTO receives a question and a database it has never seen before.
- It introspects the schema, builds a world model on the fly, enriches it with LLM-generated aliases and semantic types.
- It generates SQL, executes it, learns from errors, and repairs the world model.
- No pre-built domain knowledge required.

**Why it is valuable:**

- **Scalable:** Works on any schema.
- **Defensible architecture:** Proves OCTO is not just memorization.


## Competitive positioning

| Approach | Needs LLM retraining? | Handles proprietary data? | Enforces constraints? | Interpretable? |
|---|---|---|---|---|
| RAG | No | Maybe | No | No |
| Fine-tuning / LoRA | Yes | No | Partial | No |
| Prompt engineering | No | Maybe | No | No |
| **OCTO** | **No** | **Yes** | **Yes** | **Yes** |

OCTO is not competing with OpenAI or Anthropic. It is the layer that makes their models usable in regulated domains.

## The coprocessor platform

We do not just build one coprocessor. We are building a platform for **composable AI specialists**:

- **Schema grounding coprocessor** — picks tables/columns.
- **SQL generator coprocessor** — produces candidate SQL (Claude, GPT-4o, or a trained specialist model).
- **Execution/validation coprocessor** — runs SQL and checks results.
- **Repair coprocessor** — rewrites SQL after failures.
- **Value-retrieval coprocessor** — finds real database values for WHERE clauses.

Each specialist is swappable. The base LLM orchestrates. The runtime maintains structured state and provenance.

## Training: what we do and don't do

**We do not fine-tune the customer's LLM.**

We may train small specialist models (e.g., a 7B schema-to-SQL coprocessor) that plug into OCTO. These are components, not replacements for the foundation model. This keeps the pitch intact:

> "The LLM stays general. OCTO attaches trained specialists to it."

## Current status and honest metrics

**What works:**

- Clean FTI infrastructure: versioned world models, caching, reproducible pipelines.
- SQL generators are now first-class composable coprocessors.

**What is in progress:**

- Dynamic schema enrichment and execution-repair loop.
- Value retrieval for unseen databases.

**What we do not claim:**

- We do not claim cost-effective local-model performance today.
- We are not a replacement for all LLM use cases.

## Roadmap

### Near term (1–2 months)

2. Add dynamic schema enrichment and value-retrieval coprocessors.
3. Build one enterprise pilot (e.g., finance or internal analytics).

### Medium term (3–6 months)

1. Train a small schema-to-SQL coprocessor model on the DGX for cost-effective inference.
3. Expand enterprise pilots to 2–3 domains.

### Long term (6–12 months)

1. Marketplace of domain coprocessors (finance, defense, healthcare, legal).
2. Native coprocessor integrations with vLLM and other inference engines.

## Risks

1. **SQL generation quality.** Grounding is strong; generation is the bottleneck. Mitigation: stronger models, repair loops, trained specialist coprocessors.
2. **Customer data access.** Enterprises may hesitate to share schemas. Mitigation: on-prem/VPC deployment and clear data-governance model.
3. **Competition from LLM providers.** OpenAI/Anthropic may add native grounding. Mitigation: specialization, vertical world models, and on-prem deployment.

## The bet

As LLMs commoditize, the value shifts from parameter count to **grounding, reasoning, and constraint enforcement**. OCTO owns that layer.

## What we need

- Capital to build the coprocessor platform and train specialist models.
- Access to 1–2 enterprise design partners with proprietary schemas.
