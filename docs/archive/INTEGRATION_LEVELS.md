# Integration Levels

This document defines what OCTO means in practice at different levels of integration.

The distinction matters because the framework, the runtime, and the native backend are not the same thing.

## Level 0: Retrieval Only

This is not really OCTO.

Examples:

- vector search
- prompt stuffing
- GraphRAG-style document serialization

At this level, the model is still responsible for reconstructing domain structure from retrieved text.

## Level 1: Structured Control Mode

This is the current **weak mode**.

At this level, OCTO:

1. captures the request
2. retrieves structured world state
3. applies planning, rules, and simulation
4. emits a structured `ControlPacket`

That packet contains:

- active entities
- hypotheses
- constraints
- provenance
- prompt hints
- a fused vector for downstream consumers

In the current code, this packet is produced by `BlackBoxIntegration` in [integration.py](src/octo/integration.py#L22).

### How it is consumed

In structured control mode, the packet is typically consumed by:

- an orchestration layer
- prompt construction
- a model wrapper that serializes the packet into guidance/context

So yes: in this mode, some form of prompt-side consumption is still involved.

### Why this is still better than plain RAG

The benefit over plain RAG is not that it avoids prompts entirely. The benefit is that the payload is different:

- OCTO emits normalized entities, not just retrieved passages
- OCTO emits explicit constraints and hypotheses, not only text chunks
- OCTO preserves provenance at the reasoning layer
- OCTO can apply deterministic rules before the model sees anything

So the improvement in weak mode is:

- **structured control instead of raw retrieval**

That is useful, but it is not yet the full architectural moat.

## Level 2: Native Coprocessor Mode

This is the target **strong mode**.

At this level, OCTO state is consumed directly inside the inference server and affects generation-time behavior through:

- request-scoped context propagation
- layer hooks
- hidden-state or residual updates
- token-time decode influence

This is the level that requires inference-server support.

In the current design, this is represented by:

- `NativeIntegration`
- `ScalarLMNativeIntegration` in `implementations/scalarlm/`
- `TokenformerContext` in `implementations/scalarlm/`

The canonical reference is `src/octo/integration.py` (base abstractions) and `implementations/scalarlm/native_integration.py` (ScalarLM backend).

### Concrete native mechanism: Gated Chunked Cross-Attention (GCCA)

RETRO and InstructRetro provide a proven recipe for Level 2/3 integration:

- Keep the base LLM frozen.
- Insert trainable cross-attention adapters (WK, WV projection layers) at selected Transformer layers.
- Initialize a scalar gate `tanh(α)` to 0, so the model starts identical to the base LLM.
- Retrieve neighbor vectors for the previous chunk and feed them as Keys/Values into the cross-attention layer.
- Enforce the 1-chunk causal offset: chunk `Ci` attends only to retrievals from `Ci-1`.

This maps directly onto OCTO's native coprocessor mode, where the retrieved "neighbors" are entities and relations from the world model rather than raw text chunks. OCTO can adopt the gating, adapter, and causality machinery while keeping its structured graph signal as the retrieval source.

## What Requires Backend Changes

The following require backend changes:

- attaching OCTO context to requests
- carrying that context through batching and scheduling
- exposing it in the worker/model-runner path
- applying it in the model forward pass

That is why the current native reference backend targets a vLLM-compatible inference server.

## vLLM Status

The current native reference backend is a vLLM-compatible adapter path. vLLM is required for the strongest current form of OCTO.

## What Spider Used

The Spider runs in this repo have **not** used native coprocessor mode.

They used:

- heuristic candidate generation, or
- prompted/HTTP model generation

through the Spider harness in [run_octo_spider_snow_solve.py](examples/run_octo_spider_snow_solve.py#L46).

That means:

- Spider heuristic runs were **below native mode** and in some cases below even prompt-driven weak mode, because they used no LLM at all for SQL generation.
- Spider prompted runs were **weak mode**, because OCTO produced structured planning/control but the downstream model path was still prompt-side rather than token-time native integration.

## Recommended Language

Use these terms consistently:

- **structured control mode** = weak mode
- **native coprocessor mode** = strong mode

Avoid saying "OCTO works with any LLM" without qualification.

The accurate statement is:

- OCTO core is backend-agnostic
- structured control mode can work with many model stacks
- native coprocessor mode requires backend support
