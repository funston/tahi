# Hello World Coprocessor

## Purpose

This is the smallest domain that can prove BENDER is behaving like a coprocessor rather than a retrieval wrapper.

The Hello World system must show:

1. structured graph retrieval rather than text chunk retrieval,
2. explicit rule application with inspectable traces,
3. a fused world-model signal that is returned to the model integration layer.

## Toy world

The world is intentionally small and exception-heavy:

- `penguin is_a bird`
- `bird can fly`
- `penguin cannot fly`
- `penguin lives_in antarctica`
- `seal lives_in antarctica`
- `fish lives_in ocean`
- `penguin eats fish`
- `seal eats fish`

This is a good coprocessor test because a base model may over-generalize from `bird -> can fly`, while the coprocessor can preserve the exception path.

## Questions

- `Can a penguin fly?`
- `What animals in Antarctica eat fish?`
- `Is a penguin a bird even though it cannot fly?`

## Runtime contract

At a reasoning step `t`, the runtime uses this contract:

1. The model integration layer emits a `SemanticFrame`.
2. The world model retrieves typed nodes and relations from the toy graph.
3. The rule engine produces a machine-readable reasoning trace.
4. The fusion layer computes a fused vector from model-side and graph-side state.
5. The integration layer emits a model-facing control packet.

## Fusion model

Phase 1 uses a simple blended state:

`z_t = rho_token * h_t + rho_graph * g_t`

Where:

- `h_t` is the text embedding or native hidden-state proxy,
- `g_t` is the weighted graph-memory summary,
- `rho_graph` rises when retrieval support, hypotheses, and constraints strengthen,
- `z_t` is returned in the control packet.

For the black-box path, `z_t` is exposed as structured control context.
For the native path, `z_t` is exposed as a hidden-state delta packet contract.

## Native Tokenformer target

The intended native proof path is ScalarLM's Tokenformer surgeon path, not prompt stuffing.

Target insertion points:

- `../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_surgeon.py`
- `../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_model_manager.py`
- `../scalarlm/vllm-fork/vllm/v1/worker/lora_model_runner_mixin.py`

The BENDER-specific native adapter should:

1. read request-scoped coprocessor context,
2. compute `delta_h` from the current hidden state plus graph packet,
3. add `delta_h` to selected late MLP blocks,
4. preserve provenance and per-request control.

## Success criteria

A valid Hello World proof shows that BENDER:

- retrieves symbolic facts and relations,
- records which rules fired,
- handles exceptions correctly,
- emits a fused coprocessor packet,
- has a native path that can attach to model internals without changing the world-model runtime.
