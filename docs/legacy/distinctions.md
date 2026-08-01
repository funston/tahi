# OCTO Distinctions

## Purpose

This document states the shortest defensible distinctions between OCTO and adjacent approaches.

## OCTO vs RAG

RAG is a retrieval pattern:

- retrieve text or text-like context,
- place it into the prompt or context stream,
- let the model continue generation.

OCTO is a coprocessor runtime:

- maintain explicit world state outside the prompt,
- retrieve typed graph state,
- run reasoning and simulation over that state,
- emit a model-facing control packet,
- optionally influence hidden-state computation through a native path.

If a system only retrieves graph context and serializes it into prompt text, it should be described as a weak compatibility mode, not the strongest form of OCTO.

## OCTO vs Fine-Tuning

Fine-tuning is an offline weight adaptation method.

OCTO is an inference-time systems architecture.

Fine-tuning changes:

- model parameters,
- what the model has internalized,
- behavior across future requests.

OCTO changes:

- what structured state the system can maintain,
- what domain logic can run at inference time,
- what provenance and constraints are available,
- how request-scoped world-model state can influence generation.

They can be combined, but they are not the same thing.

## OCTO vs KAA

Knowledge-Augmented Attention is a candidate mechanism family for mixing model-side and graph-side signals.

OCTO is broader. It includes:

- capture,
- retrieval,
- reasoning,
- simulation,
- fusion,
- injection,
- provenance,
- request-scoped runtime control.

KAA may be one mechanism inside OCTO. It is not identical to OCTO.

## OCTO vs GITA-like Graph-Attention Methods

Graph-integrated transformer attention methods are mechanism-level proposals. They describe how graph-derived information might enter attention or latent computation.

OCTO is a system-level proposal. It asks:

- where persistent world state lives,
- how that state is retrieved,
- how rules and simulation operate on it,
- how provenance is preserved,
- how request-scoped control reaches the model.

A GITA-like mechanism could be one native backend implementation for OCTO. That would still not replace the rest of the architecture.

## One-sentence version

RAG retrieves context, fine-tuning changes weights, KAA/GITA change mechanisms, and OCTO defines the larger runtime architecture that can use some of those tools without being reducible to any one of them.
