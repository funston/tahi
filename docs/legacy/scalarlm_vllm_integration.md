# ScalarLM vLLM Integration Strategy

## Purpose

This document describes the current BENDER integration strategy for ScalarLM's `vllm-fork`, with emphasis on the Tokenformer path and the design choices behind the request-scoped native coprocessor model.

This is a design and implementation note for peers reviewing the integration, not an aspirational whitepaper section.

## Design goal

The ScalarLM integration is intended to prove that BENDER can affect inference as a **request-scoped native coprocessor**, not as:

- prompt stuffing,
- GraphRAG-style context serialization,
- a static adapter checkpoint swap,
- a LoRA-like global weight toggle.

The core requirement is:

> BENDER produces a structured coprocessor packet in the `bender` repo, and ScalarLM consumes that packet as request-scoped native inference context.

## Why Tokenformer

ScalarLM's `vllm-fork` already contains a Tokenformer path that wraps model layers with additive adapters. That makes it a practical insertion point for a first native BENDER backend because it provides:

- a pre-existing model surgery path,
- per-layer residual intervention points,
- worker-side adapter activation hooks inside vLLM.

The existing Tokenformer path, however, was oriented around static adapter activation. BENDER required a different model:

- per-request context,
- per-batch activation,
- residual influence derived from runtime state rather than loaded adapter weights.

## Integration targets

Primary files in `../scalarlm/vllm-fork`:

- `vllm/tokenformer/bender_coprocessor.py`
- `vllm/tokenformer/tokenformer_surgeon.py`
- `vllm/tokenformer/tokenformer_model_manager.py`
- `vllm/v1/worker/lora_model_runner_mixin.py`

Request plumbing also touches:

- `vllm/v1/engine/__init__.py`
- `vllm/v1/engine/input_processor.py`
- `vllm/v1/request.py`
- `vllm/v1/core/sched/output.py`
- `vllm/v1/worker/gpu_input_batch.py`
- `vllm/v1/worker/tpu_input_batch.py`
- `vllm/v1/worker/gpu_model_runner.py`
- `vllm/v1/worker/gpu/model_runner.py`
- `vllm/v1/worker/gpu/states.py`

## Core integration objects

### `BenderCoprocessorContext`

Location:

- `vllm/tokenformer/bender_coprocessor.py`

Purpose:

- hold the request-scoped structured packet that arrives from BENDER,
- keep the payload serializable across the vLLM request path,
- convert structured state into a compact feature vector for adapter use.

Fields:

- `fused_vector`
- `active_entities`
- `hypotheses`
- `constraints`
- `provenance`
- `decode_step`
- `mode`

Important detail:

The context object is not prompt text. It is structured inference metadata that can be converted into numerical features without passing through language serialization.

### `ActiveBenderBatch`

Location:

- `vllm/tokenformer/tokenformer_model_manager.py`

Purpose:

- hold the currently active request contexts for the scheduled batch,
- expand request-scoped contexts to token-scoped tensors,
- make those tensors available to wrapped adapter layers at forward time.

This object is what turns BENDER from “loaded state” into “current request state”.

### `BenderCoprocessorAdapter`

Location:

- `vllm/tokenformer/tokenformer_surgeon.py`

Purpose:

- wrap selected late MLP blocks,
- read the current `ActiveBenderBatch`,
- compute a residual `delta_h`,
- add that residual to the base layer output.

This is the key native mechanism.

### `BenderCoprocessorSurgeon`

Location:

- `vllm/tokenformer/tokenformer_surgeon.py`

Purpose:

- install `BenderCoprocessorAdapter` into late MLP layers,
- keep the intervention localized to a subset of the network,
- coexist with the existing Tokenformer wrapping model.

The current design intentionally targets **late MLP blocks** because they are a practical first residual intervention point without rewriting the base model.

## Request-scoped plumbing strategy

The request plumbing was designed so that BENDER context travels through the same scheduling path as the rest of vLLM request metadata.

### Request path

1. `EngineCoreRequest` carries `bender_context`.
2. `InputProcessor.process_inputs(...)` accepts and forwards `bender_context`.
3. `Request` and `NewRequestData` retain that context through scheduling.
4. Worker-side cached request state stores the context per request.
5. Input batch state collects contexts for currently active requests.
6. `LoRAModelRunnerMixin` activates the current batch's BENDER contexts before the forward pass.
7. Wrapped Tokenformer layers consume the active batch context and compute `delta_h`.

This path matters because it avoids a global mutable singleton. Context is attached to the request and lives and dies with that request.

## Why this is not a static adapter swap

The pre-existing Tokenformer path was adapter-oriented. That means a naïve implementation of BENDER could have treated the coprocessor as:

- load checkpoint,
- activate adapter id,
- change weights globally,
- run inference.

That would have violated the main design constraint.

The BENDER path differs in three ways:

1. The payload is request-scoped rather than adapter-scoped.
2. The payload is runtime state rather than a checkpointed parameter bundle.
3. The payload changes batch behavior without reloading or swapping model weights.

This is why `BenderCoprocessorAdapter` is a sibling to `TokenformerAdapter`, not just another use of the static adapter cache.

## Current native computation

At a high level, the current adapter computes:

1. flatten current hidden states,
2. fetch token-aligned context features from `ActiveBenderBatch`,
3. project context features into hidden space,
4. combine projected context with hidden-state features,
5. produce `delta_h`,
6. add `delta_h` to the base layer output.

This is a practical first native backend. It is not yet a final or benchmarked mechanism.

## Hello World native prototype relationship

The current repository includes:

- BENDER producer runtime in `bender`,
- request-scoped native Tokenformer path in `scalarlm/vllm-fork`,
- a toy end-to-end native prototype in `examples/hello_world_native_tokenformer_prototype.py`.

That prototype is important because it proves the intended property:

- no BENDER context means wrapped output matches base output,
- one request's context changes only that request's output,
- two different request contexts in one batch change outputs independently.

That is the minimal native proof that the integration is request-scoped and not just a static adapter toggle.

## Current limitations

The integration is not yet a full production serving result.

Current limitations:

- the vLLM stack in this environment is not fully bootstrapped for a live server demo,
- the upstream BENDER retrieval layer is still prototype-level in-memory retrieval rather than the intended FAISS/HNSW/PQ-backed architecture,
- the BENDER feature encoding is intentionally simple,
- the residual adapter is a first practical mechanism, not a final one,
- no production benchmark has been run yet against RAG or GraphRAG baselines,
- there is not yet a public API/server entrypoint that automatically constructs `bender_context` for live requests.

## Why this design is still valuable

Even with those limitations, the current integration establishes the important architectural facts:

- BENDER can remain the producer of structured cognitive state,
- ScalarLM can consume that state natively without prompt stuffing,
- the integration can be request-scoped rather than global,
- the intervention can happen in the model's latent path rather than only at prefill text level.

That is the main design proof for this stage.

## Recommended next steps

1. Add a serving/API path that constructs and passes `bender_context` on real requests.
2. Upgrade BENDER retrieval from the current in-memory heuristic index to an ANN backend such as FAISS or HNSW, with PQ as needed for scale and memory efficiency.
3. Replace the toy feature projection with a better learned or structured context encoder.
4. Evaluate late-MLP wrapping versus other intervention points.
5. Add tracing and observability for active context, affected layers, and delta norms.
6. Benchmark against prompt-side GraphRAG baselines on exception-heavy and constraint-heavy tasks.

## Bottom line

The ScalarLM/vLLM integration should be understood as a **request-scoped native coprocessor backend prototype**. Its purpose is to prove the architectural distinction between:

- static adapter activation, and
- live coprocessor-driven latent influence.

That distinction is the reason this integration exists.
