# OCTO Code Architecture and Design

## Scope

This document describes the current repository architecture as implemented, not the full long-term research vision.

It covers:

- the Python runtime in `src/octo`,
- the reference world-model implementations in `implementations/`,
- the example and test surfaces,
- the current native integration direction into ScalarLM's Tokenformer path.

## Top-level structure

- `src/octo/`
 Runtime, data models, retrieval, reasoning, fusion, simulation, and integration contracts.
- `implementations/`
 First-party reference world models that depend on `octo` but are not part of the core package.
- `examples/`
 Small runnable demonstrations for black-box and native prototype paths.
- `tests/`
 Unit tests covering retrieval, fusion, and end-to-end runtime behavior.
- `docs/`
 Architecture, runtime, math, and review documents.
- `whitepaper/`
 Architecture paper and reviewer-oriented framing.

## Core design principle

The repository is structured around a stable runtime boundary:

1. capture model-side state,
2. retrieve graph-side state,
3. reason over it,
4. simulate if needed,
5. fuse model-side and graph-side signals,
6. inject a model-facing control packet.

This makes the runtime the main product surface. Model-specific backends sit behind the integration interface.

An equally important repository rule is:

- `src/octo` stays architecturally pure,
- benchmark and domain packages live outside core,
- third parties should be able to look at `implementations/` as the reference pattern for building their own world coprocessors.

## Main runtime modules

### `src/octo/runtime.py`

`OctoRuntime` is the orchestrator.

Responsibilities:

- call `ModelIntegration.capture(...)`,
- call `WorldModel.retrieve(...)`,
- populate and update `CognitiveState`,
- invoke planner, rule engine, and simulator,
- call `FusionModule.mix(...)`,
- call `ModelIntegration.inject(...)`,
- emit a final state with provenance.

This is the center of the system.

### `src/octo/models.py`

This file defines the shared data model:

- `SemanticFrame`
- `RetrievedMemory`
- `EntityRef`
- `RelationRef`
- `Hypothesis`
- `FusedSignal`
- `ControlPacket`
- `CognitiveState`

These types matter because they separate:

- model-side observation,
- world-model retrieval,
- reasoning state,
- model-facing output.

### `src/octo/integration.py`

This file defines the model boundary.

Key classes:

- `ModelIntegration`
- `BlackBoxIntegration`
- `NativeIntegration`
- `NativeTokenformerIntegration`

Design intent:

- `BlackBoxIntegration` supports closed-weight or API-only models by emitting structured control context.
- `NativeIntegration` supports open-weight paths where hidden-state data is available.
- `NativeTokenformerIntegration` describes the intended ScalarLM Tokenformer-native contract.

The important architectural decision is that model coupling lives here, not inside the reasoning modules.

### `src/octo/world_state.py`

`WorldModel` stores typed nodes and relations and exposes retrieval methods.

Current implementation:

- in-memory typed graph,
- structured node and relation lookups,
- graph-derived signal generation.

This is intentionally simple but architecturally separate from prompting.

### `src/octo/retrieval.py`

Implements query embedding and retrieval helpers.

Current behavior:

- lightweight embedding proxy,
- lexical-overlap reranking,
- support for structured retrieval outputs.

This is a prototype retrieval layer, not yet a production ANN stack.

The intended architecture direction is to replace or back this layer with a standard approximate nearest-neighbor backend rather than grow a custom search system from scratch. The current likely targets are:

- FAISS,
- HNSW-style indexing,
- product quantization (PQ) for compressed vector search where scale demands it.

That distinction matters:

- **implemented now**: small in-memory retrieval suitable for toy domains and runtime proof,
- **target design**: ANN-backed structured retrieval suitable for larger persistent world models.

### `src/octo/planner.py`

Adds deterministic execution steps to the cognitive trace.

Current role:

- represent planned reasoning stages,
- make the pipeline legible in demos and provenance.

### `src/octo/rules.py`

Contains deterministic domain logic.

Current role:

- encode explicit exceptions and relation intersections,
- demonstrate reasoning that should not be left implicit in the language model.

The Hello World penguin example depends heavily on this file.

### `src/octo/simulator.py`

Executes simple task or domain evaluators.

Current implementation:

- heuristic simulation,
- placeholder for stronger domain-specific evaluation.

### `src/octo/fusion.py`

Defines the fusion boundary between model-side and graph-side state.

Current implementation:

- `FusionModule`
- `WeightedBlendFusion`

Design intent:

- keep fusion pluggable,
- let retrieval, reasoning, and simulation remain independent from model-specific injection code.

### `src/octo/adapter.py`

Provides the user-facing wrapper surface:

- `wrap_llm(...)`
- `WrappedLLM.ask(...)`

This is the easiest entrypoint for demos and tests.

## Runtime flow in code

The implemented execution path is:

1. `wrap_llm(...)` constructs a `OctoEngine` / `OctoRuntime`.
2. `WrappedLLM.ask(...)` calls `engine.infer(...)`.
3. `ModelIntegration.capture(...)` builds a `SemanticFrame`.
4. `WorldModel.retrieve(...)` returns structured memories.
5. `Planner`, `RuleEngine`, and `Simulator` update `CognitiveState`.
6. `FusionModule.mix(...)` computes a `FusedSignal`.
7. `ModelIntegration.inject(...)` produces a `ControlPacket`.
8. The wrapper returns a traceable dictionary for examples or tests.

## Example surfaces

## Reference world-model implementations

### `implementations/bio/`

Purpose:

- demonstrate a knowledge-heavy domain with ontology-like entity normalization,
- show provenance-backed biomarker interpretation and target profiling,
- show the difference between a world model and plain retrieval.

### `implementations/mass_spec/`

Purpose:

- demonstrate a narrow scientific domain where deterministic constraints matter,
- show analyte / adduct / polarity / instrument reasoning,
- provide a stronger counterexample to "just use RAG".

### `implementations/bird/`

Purpose:

- preserve a SQL-oriented benchmark implementation outside the core package.

### `implementations/spider/`

Purpose:

- preserve Spider benchmark work as an external implementation rather than letting it define the core architecture.

### `examples/hello_world_coprocessor_demo.py`

Purpose:

- prove the smallest legible coprocessor behavior,
- show explicit exception handling,
- show relation intersection,
- show black-box and native-design packet output.

### `examples/biomedical_coprocessor_demo.py`

Purpose:

- demonstrate a less toy-like domain,
- show the same runtime boundary on a biomedical example.

### `examples/hello_world_native_tokenformer_prototype.py`

Purpose:

- use the real OCTO producer runtime,
- load the new ScalarLM Tokenformer prototype modules,
- demonstrate request-scoped residual influence in a toy PyTorch model.

This is currently the clearest native proof artifact in the repo.

## Test strategy

The current tests focus on the runtime contract rather than benchmark performance.

Key tests:

- retrieval relevance,
- fusion behavior,
- black-box control packet emission,
- native integration packet shape,
- Hello World reasoning behavior.

This is appropriate for Phase 1 because the main goal is architectural correctness.

## ScalarLM native integration direction

The current native backend work lives outside this repo in `../scalarlm/vllm-fork`, but it is part of the practical architecture.

Main target files:

- `vllm/tokenformer/octo_coprocessor.py`
- `vllm/tokenformer/tokenformer_surgeon.py`
- `vllm/tokenformer/tokenformer_model_manager.py`
- `vllm/v1/worker/lora_model_runner_mixin.py`

Implemented design:

- request-scoped `OctoCoprocessorContext`,
- `OctoCoprocessorAdapter` wrapping late MLP blocks,
- per-request batch context activation,
- worker-side request plumbing carrying `octo_context`.

Important constraint:

- OCTO is not implemented there as prompt stuffing or a static checkpoint swap.
- The intent is native residual influence per request.

## Current limitations

- retrieval is in-memory and heuristic,
- graph construction is mostly manual in the demos,
- simulation is simplistic,
- production serving integration is incomplete,
- the deepest transformer-native backend is still early.

These limitations should be treated as part of the design state, not hidden.

For retrieval specifically, the limitation is not conceptual uncertainty about the direction. The planned direction is a standard ANN retrieval backend such as FAISS or HNSW, with PQ as needed for scale and memory efficiency.

## Extension points

The code is intentionally modular at these boundaries:

- swap retrieval/index backend,
- swap fusion strategy,
- add domain-specific rules,
- add domain simulators,
- add new `ModelIntegration` backends,
- attach stronger native hidden-state backends.

## Recommended mental model

Think of the repository as three concentric layers:

1. **Stable core runtime**
 `runtime.py`, `models.py`, `integration.py`, `fusion.py`

2. **Domain reasoning layer**
 `world_state.py`, `retrieval.py`, `planner.py`, `rules.py`, `simulator.py`

3. **Delivery surfaces**
 `adapter.py`, `examples/`, tests, and external native backends such as ScalarLM Tokenformer.

That separation is the main architectural asset of the codebase.
