# Tahi

*TAHI: Typed-graph Augmented Hidden-state Injection*

**Tahi is a world-model coprocessor framework for LLMs.**

It is built around a simple premise: specialized knowledge work should not require either retraining a base model or forcing the model to reconstruct structure from long retrieved prompts. Tahi builds explicit world state at runtime, reasons over that state, and returns structured control to the model.

Version: `0.1.0`

## Why Tahi

- **More structured than RAG:** Tahi operates over typed entities, relations, constraints, and provenance, not only retrieved passages.
- **More flexible than retraining:** domain specialization happens in the runtime world model, not by training a separate base model for each domain state.
- **Built for integration:** the core runtime emits a control packet and fused signal that can be consumed by black-box or open-weight model paths.
- **Well suited to specialized domains:** biotech, scientific interpretation, and enterprise data systems where domain structure matters more than generic text recall.
- **Production-ready MLOps:** adopts FTI (Feature/Training/Inference) patterns with versioned world models, reproducible builds, and 3x faster benchmarks.

## What we are building now: TahiRetro

**Keep the model frozen, and let it re-aim retrieval while it is writing** — every 64
generated tokens, keyed on the text it just produced, injected into the residual stream
instead of the prompt. The retrieval substrate is Tahi's graph (vector seeding plus typed
edge expansion) rather than RETRO's flat text chunks.

This is RETRO's chunked cross-attention schedule with Tahi's structured substrate. The
schedule is the bet: single-shot retrieval cannot fetch what the question does not name,
so multi-hop questions with a hidden bridge entity are unreachable until the model has
written the bridge itself.

- Spec, arms, and kill criteria: **[docs/TAHIRETRO_SPEC.md](docs/TAHIRETRO_SPEC.md)**
- Mechanism: `src/tahi/native/chunked_decode.py`, `src/tahi/native/gcca_layer.py`
- Verified properties (Tier 1): `tests/test_chunked_gcca.py`
- See it fire: `PYTHONPATH=src python examples/tahiretro_chunked_demo.py`

Status: mechanics built and verified — `alpha=0` bit-identical to the base model, no
causal leak across chunk boundaries, O(1) resident memory. **No accuracy claim has been
made.** The earlier Level 3 benchmark measured one-shot injection, not this schedule.

## Architecture Highlights

Tahi follows the **FTI MLOps pattern** for world model management:

- **World Model Pipeline** (Feature Pipeline): Pre-build and version domain knowledge graphs
- **Coprocessor Pipeline** (Inference Pipeline): Runtime retrieval, planning, and fusion
- **No Training Pipeline**: Model-agnostic by design—domain logic in graphs, not weights

This approach provides reproducible research, faster iteration (3x benchmark speedup), and clean separation between knowledge engineering and model deployment.

See [Architecture](docs/ARCHITECTURE.md) for details.

## Repository Structure

- `src/tahi/`
 The pure core package.
- `implementations/`
 First-party reference world models built on top of the core package.
- `examples/`
 Runnable demos.
- `docs/`
 Public documentation.
- `whitepaper/`
 The current whitepaper draft.

Repository rule:

- `tahi` must not import from `implementations`
- `implementations/*` may import from `tahi`

## Quick Start

Install the core package in editable mode:

```bash
pip install -e .
```

Run the smallest end-to-end demo:

```bash
PYTHONPATH=src python examples/hello_world_coprocessor_demo.py
```

Run a knowledge-heavy demo:

```bash
PYTHONPATH=src python examples/bio_biomarker_demo.py --mode biomarker --case-id demo_her2_breast
```

Run a constrained scientific demo:

```bash
PYTHONPATH=src python examples/mass_spec_demo.py --mode spectrum --case-id demo_glucose_sodium
```

## Documentation

- [Quick Start](docs/QUICKSTART.md)
- [Tutorial](docs/TUTORIAL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Benchmarking](docs/BENCHMARKING.md)
- [Integration Levels](docs/INTEGRATION_LEVELS.md)
- [Whitepaper Guide](docs/WHITEPAPER.md)
- [Docs Index](docs/README.md)

## Reference Implementations

- `implementations/bio`
 Biomarker interpretation, target profiling, and evidence-record ingestion.
- `implementations/mass_spec`
 Peak interpretation, analyte/adduct reasoning, and a strong counterexample to plain RAG in a scientific domain.
 Isolated SQL benchmark implementation.
- `implementations/spider`
 Isolated benchmark and stress-test implementation.

## Status

The core runtime is real and runnable today:

- `TahiRuntime`
- `BlackBoxIntegration`
- `NativeIntegration`
- `WeightedBlendFusion`
- `WorldModel`
- reference world-model demos and tests

Important distinction:

- structured control mode works today and can be used without a native model backend
- native coprocessor mode is the stronger target and requires backend support

The deepest native backend remains a prototype path. What is already implemented and reviewable is the runtime, the integration contract, and the pattern for building reference world models on top of the core package.
