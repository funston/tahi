# Bio World Model

`implementations/bio` is a reference world-model package built on top of `octo`. It is intentionally outside `src/octo` so the core package stays architecturally pure.

## What This Implementation Demonstrates

- biomarker / assay / disease interpretation
- target / pathway / disease / therapy profiling
- entity normalization across aliases
- provenance-backed hypotheses instead of free-form summary text

## Demo Workflows

Biomarker interpretation:

```bash
python examples/bio_biomarker_demo.py --mode biomarker --case-id demo_her2_breast
```

Target profile:

```bash
python examples/bio_biomarker_demo.py --mode target-profile --target EGFR --disease NSCLC
```

Evidence-record ingest:

```bash
python examples/bio_ingest_demo.py --target BRAF --disease Melanoma
```

## What A Similar RAG Stack Would Require

A plain RAG build for this domain would usually need:

- ingestion of papers, guidelines, pathway notes, and assay metadata
- chunking and embedding
- vector search
- reranking
- entity extraction and alias normalization
- ontology alignment
- evidence deduplication
- provenance formatting
- prompt orchestration

That stack retrieves relevant text, but it still leaves the hard part inside the LLM prompt: keeping targets, biomarkers, pathways, diseases, therapies, and evidence links coherent.

## Why The World-Model Approach Is Different

- OCTO builds explicit entities and relations, not only retrieved passages.
- The adapter can reason over graph structure before generation.
- Provenance stays attached to each hypothesis instead of being flattened into a single answer.
- Domain updates happen in the runtime knowledge base, without retraining a new model.

This is the core counterargument to "just use a vector DB and RAG": once the task needs normalized entities, typed relations, constrained reasoning, and provenance-aware outputs, you are already rebuilding a world model. OCTO makes that layer explicit and reusable.
