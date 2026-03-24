# BENDER Runtime System

## Runtime topology

1. User query enters runtime
2. `ModelIntegration.capture(...)` creates a `SemanticFrame` with query embedding and optional hidden-state proxy
3. `WorldModel.retrieve(...)` searches an in-memory graph index over typed nodes and relations
4. `Planner`, `RuleEngine`, and `Simulator` update the `CognitiveState`
5. `FusionModule.mix(...)` blends model-side signal with graph-side signal
6. `ModelIntegration.inject(...)` emits a `ControlPacket`
7. The base model continues generation using either structured control context or a native hidden-state delta
8. Provenance is recorded across each stage

## Important runtime components

### SemanticFrame
Represents the model-side semantic state observed by the coprocessor. It includes query text, token window, embedding, optional hidden state, decode step, and integration metadata.

### ModelIntegration
Defines the model boundary. `BlackBoxIntegration` supports API-only models. `NativeIntegration` provides the interface for open-weight hidden-state access.

### GraphIndex
The current prototype uses an in-memory embedding index with lexical-overlap re-ranking. This is intentionally minimal but already separate from prompt construction.

The intended architecture direction is not a custom ad hoc search layer. For larger or production settings, the retrieval backend should move to a standard ANN stack such as:

- FAISS,
- HNSW-style indexes,
- compressed vector search using product quantization (PQ) where appropriate.

So the right reading is:

- **prototype today**: in-memory structured lookup plus lexical reranking,
- **target architecture**: ANN-backed graph/entity retrieval using FAISS or HNSW-family indexing, potentially with PQ for scale and memory efficiency.

### FusionModule
Mixes token-time or hidden-state signals with world-model graph signals. The default implementation is `WeightedBlendFusion`.

### Planner
Optional decomposition for multi-step reasoning tasks.

### ControlPacket
The coprocessor output to the model integration layer. It contains fused vectors, active entities, hypotheses, constraints, hints, and provenance references.

### Provenance
Each capture, retrieval, reasoning, simulation, fusion, and injection step records a provenance event in the `CognitiveState`.

## Performance targets

- retrieval latency under tens of milliseconds for hot domains
- cached graph neighborhood expansion
- async simulation where possible
- deterministic rule engine for auditable paths

## Strategic point

The runtime is the product surface. The paper proposes the architecture, but the runtime is what turns BENDER into a deployable platform.

## Phase 1 limitations

- Retrieval is in-memory and heuristic, not FAISS/HNSW/PQ-backed yet.
- The native path defines the hidden-state packet contract but does not yet patch a transformer implementation.
- Simulation is still a deterministic biomedical heuristic rather than a domain simulator.
