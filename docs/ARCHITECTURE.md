# Architecture

## Core Idea

BENDER is a world-model coprocessor for LLMs.

Instead of asking the model to infer domain structure from retrieved text alone, BENDER:

1. captures model-side query state
2. retrieves structured world state
3. reasons over entities, relations, constraints, and hypotheses
4. fuses model-side and graph-side signals
5. emits a model-facing control packet

## Core Runtime

The core package lives in `src/bender/`.

Primary components:

- `BenderRuntime`
- `WorldModel`
- `WorldModelStore` (FTI Feature Pipeline)
- `Planner`
- `RuleEngine`
- `Simulator`
- `FusionModule`
- `BlackBoxIntegration`
- `NativeIntegration`

The runtime contract is:

1. `ModelIntegration.capture(...)`
2. `WorldModel.retrieve(...)`
3. `Planner`, `RuleEngine`, `Simulator`
4. `FusionModule.mix(...)`
5. `ModelIntegration.inject(...)`

## FTI MLOps Architecture

BENDER adopts the Feature/Training/Inference (FTI) MLOps pattern for world model management:

**World Model Pipeline** (Feature Pipeline analog):
- Pre-build versioned world models from domain data
- Store with semantic versioning (e.g., `bird-dev:v1.0.0`)
- Reproducible builds with metadata tracking

**Coprocessor Pipeline** (Inference Pipeline analog):
- Load pre-built world models on demand
- Runtime retrieval, planning, and fusion
- Point-in-time consistency with versioned models

**No Training Pipeline**:
- BENDER is model-agnostic by design (no fine-tuning)
- Domain logic lives in graphs, not weights
- Maintains architectural purity

**WorldModelStore** provides:
- Versioned storage with gzip compression
- Lazy loading (`get_or_build`)
- Manifest tracking (build date, metadata, model counts)
- 3x faster benchmarks (pre-built vs rebuilt on every run)

Reference: https://www.hopsworks.ai/post/mlops-to-ml-systems-with-fti-pipelines

## Repository Boundary

The repo is intentionally split into:

- `src/bender/`
  Pure framework and runtime code
- `implementations/`
  Reference world models built on top of the framework
- `examples/`
  Demo entrypoints

Architectural rule:

- `bender` must not import from `implementations`
- `implementations/*` may import from `bender`

This keeps the open-source core clean and shows third parties how to build on top of it.

## Integration Levels

### Black-box path

For API-only or closed-weight models, BENDER emits structured control context such as:

- active entities
- hypotheses
- constraints
- provenance
- fused signal metadata

### Native path

For open-weight models, BENDER is designed to provide request-scoped latent influence through a native backend.

In this repo, the native path is represented by the integration contracts and prototype demos. Backend-specific notes such as the ScalarLM integration design live in `docs/legacy/` because they are implementation notes, not the core architecture.

For a clearer operational distinction between weak and strong integration, see [Integration Levels](/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md).

## Why This Is Not Plain RAG

RAG retrieves text and asks the model to reconstruct structure from the prompt.

BENDER explicitly models:

- entities
- relations
- constraints
- rule application
- provenance
- runtime-updatable domain state

That is the key architectural distinction. The goal is not merely better retrieval, but a runtime layer that can preserve structure, apply constraints, and keep provenance attached to the reasoning path.

## Reference Implementations

- `bio`
  Biomarker interpretation, target profiling, evidence ingestion
- `mass_spec`
  Analyte/adduct/polarity/instrument reasoning
- `bird`
  SQL benchmark implementation kept outside core
- `spider`
  Stress-test benchmark implementation kept outside core

## Recommended Reading

- [Quick Start](/Users/richiek/work/bender/docs/QUICKSTART.md)
- [Tutorial](/Users/richiek/work/bender/docs/TUTORIAL.md)
- [Integration Levels](/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md)
- scalarLM-specific backend notes now live in [docs/legacy/NATIVE_SCALARLM.md](/Users/richiek/work/bender/docs/legacy/NATIVE_SCALARLM.md)
- [Whitepaper Guide](/Users/richiek/work/bender/docs/WHITEPAPER.md)
