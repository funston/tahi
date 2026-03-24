# True Cognitive Coprocessor Architecture

## What makes BENDER a real coprocessor?

A true coprocessor does more than return retrieved facts. It must:

1. maintain persistent independent state,
2. participate in inference while generation is happening,
3. inject structured signals that the base model alone does not compute,
4. preserve provenance and updateability.

## Phase 1 implementation in this repo

The current codebase now implements a Phase 1 coprocessor runtime with these concrete boundaries:

1. `ModelIntegration.capture(...)` creates a `SemanticFrame` from the query plus optional hidden state.
2. `WorldModel.retrieve(...)` returns structured node and relation memories, not serialized documents.
3. `Planner`, `RuleEngine`, and `Simulator` update a persistent `CognitiveState`.
4. `FusionModule.mix(...)` produces a fused coprocessor signal from model-side and graph-side state.
5. `ModelIntegration.inject(...)` returns a `ControlPacket` for either black-box or native model paths.

This means the prototype is no longer just a prompt-side wrapper. The runtime explicitly computes a separate cognitive packet and model-facing integration artifact.

## Coupling levels

### Level 0 — Prompt-side augmentation
Weakest form. Good for compatibility, but not enough for the paper's strongest claims.

### Level 1 — Prefill graph conditioning
Graph state is serialized or encoded before generation starts.

### Level 2 — Hidden-state fusion
BENDER computes graph-derived vectors and fuses them into an adapter, router, or cross-attention module.

### Level 3 — Decode-loop coprocessing
At each major reasoning step or token chunk, the runtime can:
- inspect semantic state,
- retrieve graph neighborhoods,
- run rules,
- call simulators,
- feed a cognitive state packet back into generation.

## Cognitive state packet

A useful abstraction is a `CognitiveState` object:

- active entities
- active relations
- constraints
- hypotheses
- planner goals
- simulation outputs
- provenance references
- confidence scores

This packet is the coprocessor's output to the base model.

## Closed-weight vs open-weight models

For closed-weight APIs, BENDER may operate through structured control/context packets.
For open-weight models, BENDER can integrate more deeply via hidden-state hooks or adapters.

In the current implementation:

- `BlackBoxIntegration` is the closed-weight path. It emits structured hints, constraints, hypotheses, provenance, and a fused vector packet.
- `NativeIntegration` is the open-weight contract. It accepts hidden-state vectors and emits a hidden-state delta packet shape, but it does not yet attach to a specific transformer runtime.

## Practical thesis

BENDER should be presented as a **spectrum architecture**:
- immediately deployable at weaker integration levels,
- increasingly powerful as lower-level model access becomes available.

Phase 1 is meant to prove that the runtime is architected as a coprocessor today, while leaving the deepest model-native backend as the next implementation step rather than pretending it already exists.
