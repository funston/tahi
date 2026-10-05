# Architecture

## Core Idea

TAHI is a world-model coprocessor for LLMs.

Instead of asking the model to infer domain structure from retrieved text alone, TAHI:

1. captures model-side query state
2. retrieves structured world state
3. reasons over entities, relations, constraints, and hypotheses
4. fuses model-side and graph-side signals
5. emits a model-facing control packet

## Core Runtime

The core package lives in `src/tahi/`.

Primary components:

- `TahiRuntime`
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

TAHI adopts the Feature/Training/Inference (FTI) MLOps pattern for world model management:

**World Model Pipeline** (Feature Pipeline analog):
- Pre-build versioned world models from domain data
- Reproducible builds with metadata tracking

**Coprocessor Pipeline** (Inference Pipeline analog):
- Load pre-built world models on demand
- Runtime retrieval, planning, and fusion
- Point-in-time consistency with versioned models

**No Training Pipeline**:
- TAHI is model-agnostic by design (no fine-tuning)
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

- `src/tahi/`
 Pure framework and runtime code
- `implementations/`
 Reference world models built on top of the framework
- `examples/`
 Demo entrypoints

Architectural rule:

- `tahi` must not import from `implementations`
- `implementations/*` may import from `tahi`

This keeps the open-source core clean and shows third parties how to build on top of it.

## Integration Levels

### Black-box path

For API-only or closed-weight models, TAHI emits structured control context such as:

- active entities
- hypotheses
- constraints
- provenance
- fused signal metadata

### Native path

For open-weight models, TAHI is designed to provide request-scoped latent influence through a native backend.

In this repo, the native path is represented by the integration contracts, the PyTorch GCCA modules in `src/tahi/native/`, and prototype demos.

For a clearer operational distinction between weak and strong integration, see [Integration Levels](docs/INTEGRATION_LEVELS.md).

## Why This Is Not Plain RAG

RAG retrieves text and asks the model to reconstruct structure from the prompt.

TAHI explicitly models:

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
 SQL benchmark implementation kept outside core
- `spider`
 Stress-test benchmark implementation kept outside core

## Relationship to RETRO / Large-Scale ANN RAG

TAHI is not a competitor to RETRO, InstructRetro, or massive ANN retrieval systems. Those systems optimize for **recall coverage** over unstructured corpora. TAHI optimizes for **correctness, structure, and provenance** in constrained domains.

Where RETRO/ANN engineering is directly useful to TAHI:

- **Level 2/3 native integration:** Gated Chunked Cross-Attention (GCCA) adapters are a concrete recipe for TAHI's native coprocessor mode. The `tanh(α)` gate, frozen base model, and 1-chunk causal offset are all applicable.
- **Late chunking:** improves document evidence ingestion in world-model builders.
- **Out-of-core vector storage:** `WorldModelStore` can adopt DiskANN/Starling-style backends if a world model grows beyond RAM.
- **Async prefetch:** hides retrieval latency in token-time native mode.
- **Embedding-space alignment:** Procrustes or MLP projection lets TAHI upgrade embedding models without rebuilding adapters.

See the full comparison in [RETRO/ANN vs. TAHI](docs/RETRO_ANN_VS_TAHI.md).

## Cost Model

TAHI's cost is dominated by **domain curation and ontology engineering**, not by storage or embedding compute. A structured SQL world model for an enterprise schema is typically megabytes to gigabytes, not petabytes. This is the opposite of a 10 PB RETRO corpus, where the dominant costs are embedding compute, NVMe storage, and specialized serving hardware.

## Recommended Reading

- [Quick Start](docs/QUICKSTART.md)
- [Tutorial](docs/TUTORIAL.md)
- [Integration Levels](docs/INTEGRATION_LEVELS.md)
- [Benchmarking](docs/BENCHMARKING.md)
- [RETRO/ANN vs. TAHI](docs/RETRO_ANN_VS_TAHI.md)
- [Whitepaper Guide](docs/WHITEPAPER.md)
