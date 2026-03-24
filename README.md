# BENDER

**BENDER is a world-model coprocessor framework for LLMs.**

It is built around a simple premise: specialized knowledge work should not require either retraining a base model or forcing the model to reconstruct structure from long retrieved prompts. BENDER builds explicit world state at runtime, reasons over that state, and returns structured control to the model.

Version: `0.1.0`

## Why BENDER

- **More structured than RAG:** BENDER operates over typed entities, relations, constraints, and provenance, not only retrieved passages.
- **More flexible than retraining:** domain specialization happens in the runtime world model, not by training a separate base model for each domain state.
- **Built for integration:** the core runtime emits a control packet and fused signal that can be consumed by black-box or open-weight model paths.
- **Well suited to specialized domains:** biotech, scientific interpretation, and enterprise data systems where domain structure matters more than generic text recall.

## Repository Structure

- `src/bender/`
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

- `bender` must not import from `implementations`
- `implementations/*` may import from `bender`

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

- [Quick Start](/Users/richiek/work/bender/docs/QUICKSTART.md)
- [Tutorial](/Users/richiek/work/bender/docs/TUTORIAL.md)
- [Architecture](/Users/richiek/work/bender/docs/ARCHITECTURE.md)
- [Integration Levels](/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md)
- [Native ScalarLM Backend](/Users/richiek/work/bender/docs/NATIVE_SCALARLM.md)
- [Whitepaper Guide](/Users/richiek/work/bender/docs/WHITEPAPER.md)
- [Docs Index](/Users/richiek/work/bender/docs/README.md)
- [0.1 Review Cut](/Users/richiek/work/bender/docs/RELEASE_0.1_REVIEW.md)

## Reference Implementations

- `implementations/bio`
  Biomarker interpretation, target profiling, and evidence-record ingestion.
- `implementations/mass_spec`
  Peak interpretation, analyte/adduct reasoning, and a strong counterexample to plain RAG in a scientific domain.
- `implementations/bird`
  Isolated SQL benchmark implementation.
- `implementations/spider`
  Isolated benchmark and stress-test implementation.

## Status

The core runtime is real and runnable today:

- `BenderRuntime`
- `BlackBoxIntegration`
- `NativeIntegration`
- `WeightedBlendFusion`
- `WorldModel`
- reference world-model demos and tests

Important distinction:

- structured control mode works today and can be used without a native model backend
- native coprocessor mode is the stronger target and requires backend support

The deepest native backend remains a prototype path. What is already implemented and reviewable is the runtime, the integration contract, and the pattern for building reference world models on top of the core package.
