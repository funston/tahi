# Roadmap

## Current Architecture Direction

- `src/bender/` is the pure core package.
- Reference world-model implementations live outside core under `implementations/`.
- Current examples:
  - `implementations/spider/`
  - `implementations/bird/`

This separation is intentional. `bender` should remain the reusable runtime, planning, retrieval, fusion, repair, and integration framework. Domain and benchmark implementations should be built on top of it, not embedded inside it.

## Near-Term Implementation Roadmap

Build 3 reference implementations with different proof goals.

### 1. `implementations/spider`

Purpose:
- benchmark pressure test

What it proves:
- schema grounding
- constrained planning
- execution-time repair
- world-state-guided SQL generation

Why it matters:
- useful for technical credibility
- not the main product story

### 2. `implementations/bio`

Purpose:
- investor/customer narrative

Target workflow:
- biomarker / assay / disease interpretation
- target-pathway-disease reasoning
- evidence synthesis with provenance

What it proves:
- BENDER can normalize entities across fragmented biomedical knowledge
- BENDER can build a request-scoped evidence graph instead of stuffing papers into prompts
- runtime-updated domain knowledge beats retraining for niche, evolving domains

MVP tasks:
- "Interpret biomarker X in disease Y given assay result Z"
- "Summarize target relevance, mechanism, supporting evidence, and conflicts"
- "Suggest likely hypotheses and next questions with provenance"

### 3. `implementations/mass_spec`

Purpose:
- strongest technical differentiation from plain RAG

Target workflow:
- peak/adduct/isotope/fragments interpretation
- instrument/mode/sample-context-aware reasoning
- candidate identification / explanation

What it proves:
- BENDER handles structured scientific constraints well
- BENDER can reason over competing hypotheses with domain rules
- this is exactly the kind of niche knowledge problem where retraining is too expensive and RAG is too brittle

MVP tasks:
- "Explain this observed mass pattern"
- "Rank candidate compounds/adduct explanations"
- "Interpret fragmentation evidence with provenance"

## Suggested Order

1. Keep `implementations/spider` as benchmark reference.
2. Build `implementations/bio` next for market story.
3. Build `implementations/mass_spec` after that for deep technical proof.

## What "Bio" Should Solve / Prove

`bio` should not just be generic biology Q&A. It should solve tasks where:

- the domain has dense specialized knowledge
- the knowledge changes too often or is too fragmented to justify training a new model
- plain RAG returns documents, but the task actually needs structured interpretation

Strong proof targets:

### Biomarker / Assay Interpretation

Inputs:
- gene/protein/variant mentions
- assay outputs
- disease context
- treatment or trial context

BENDER value:
- normalize aliases and synonyms
- connect entities across ontologies
- preserve provenance
- reason over relationships, not just retrieve papers

### Translational Research Copilot

Inputs:
- target, pathway, disease, modality
- internal notes, external sources, study metadata

BENDER value:
- build a request-scoped world model of targets, pathways, indications, evidence, and conflicts
- produce structured hypotheses and provenance-backed recommendations

### Mass Spectrometry Interpretation

Inputs:
- analyte
- instrument mode
- sample prep
- observed peaks
- adducts
- metadata

BENDER value:
- structured constraints
- candidate explanation generation
- rule-based elimination
- provenance-aware interpretation

## What A Comparable RAG System Would Entail

For `bio`, a normal RAG stack would look like:

- ingest papers, trial records, pathway docs, ontology exports
- chunk documents
- embed chunks
- store in a vector database
- retrieve top-k chunks for a query
- stuff them into a prompt
- ask the LLM to synthesize an answer

To make that decent in practice, you also need:

- entity extraction and synonym normalization
- metadata filters
- reranking
- source deduplication
- prompt templates for evidence synthesis
- conflict handling logic
- caching
- provenance formatting
- custom evaluation harness

So "just use RAG" quickly becomes:

- vector DB
- entity linker
- reranker
- metadata and ontology layer
- rule layer
- prompt orchestration
- answer post-processing

At that point, you are already rebuilding pieces of a world model, just less explicitly.

For `mass_spec`, plain RAG is even weaker:

- retrieve docs about peaks, adducts, instruments
- ask the LLM to infer the right explanation from text blobs
- hope it applies the right rules consistently

That is exactly the kind of domain where plain retrieval is weakest.

## BENDER Strengths Over Plain RAG

### Structured World State, Not Text Piles

- RAG retrieves passages.
- BENDER builds entities, relations, constraints, hypotheses, and provenance.

### Runtime Reasoning Over Domain Structure

- RAG asks the LLM to infer structure from retrieved text.
- BENDER gives the model explicit structure to work from.

### Better Handling Of Aliases And Ontology Alignment

- In bio, names are messy.
- BENDER can normalize and link before generation.

### Conflict-Aware Reasoning

- RAG often collapses conflicting evidence into a smooth paragraph.
- BENDER can preserve conflicting hypotheses and their provenance.

### Cheaper Than Retraining

- specialized domains change
- runtime world-state updates are cheaper than new model training cycles

### More Reliable In Constrained Domains

Especially when tasks need:
- typed rules
- join paths
- domain constraints
- provenance-sensitive decisions
- execution and repair loops

## The Core Positioning

The simplest message is:

- training is too expensive and static
- RAG is cheap but fragile
- BENDER is the middle path:
  - runtime-specialized
  - structured
  - provenance-aware
  - domain-adaptable without retraining

## Best Go-To-Market Story

Use the pair:

- `spider`: "we can pressure-test the architecture on hard benchmark tasks"
- `bio` or `mass_spec`: "here is where this actually matters in the real world"

If optimizing for persuasion:

- investors: lead with `bio`
- technical community: lead with `mass_spec`
- benchmark credibility: keep `spider` in the background

## Next Concrete Step

Build `implementations/bio` with:

- a clear entity model
- source and provenance handling
- a small set of representative tasks
- explicit evaluation criteria
- a demo that shows why structured world state is better than prompt-only retrieval
