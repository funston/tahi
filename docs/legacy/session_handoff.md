# Session Handoff

## Current status

The BENDER repo now has a concrete Phase 1 coprocessor runtime implemented in `src/bender`.

Implemented pieces:

- `BenderRuntime` captures a semantic frame, retrieves typed world-model state, runs planning/rules/simulation, fuses graph influence, and emits a model-facing control packet.
- Black-box and native integration abstractions exist:
  - `BlackBoxIntegration`
  - `NativeIntegration`
  - `NativeTokenformerIntegration` design stub
- A pluggable fusion layer exists via `FusionModule` and `WeightedBlendFusion`.
- Retrieval is implemented as an in-memory structured graph lookup with lexical-overlap reranking.
- Provenance is tracked across capture, retrieval, reasoning, simulation, fusion, and injection.

## Hello World coprocessor

The minimal toy-domain proof is implemented and documented.

Relevant files:

- `docs/hello_world_coprocessor.md`
- `src/bender/demo_worlds.py`
- `examples/hello_world_coprocessor_demo.py`
- `tests/test_hello_world_pipeline.py`

Toy world:

- penguin / bird / seal / fish / Antarctica
- explicit exception handling:
  - `bird can fly`
  - `penguin cannot fly`
- explicit relation intersection:
  - Antarctic animals that eat fish -> penguin, seal

The Hello World demo proves:

- structured retrieval over nodes/relations,
- explicit reasoning traces,
- fused coprocessor packet emission,
- a native integration contract distinct from prompt stuffing.

## Biomedical demo

The biomedical demo still works on the same runtime.

Relevant file:

- `examples/biomedical_coprocessor_demo.py`

## Native Tokenformer target

The intended next step is to implement request-scoped native coprocessor injection in ScalarLM's vLLM fork.

Read these files in `../scalarlm/vllm-fork`:

- `vllm/tokenformer/tokenformer_surgeon.py`
- `vllm/tokenformer/tokenformer_model_manager.py`
- `vllm/v1/worker/lora_model_runner_mixin.py`

Current finding:

- ScalarLM's `vllm-fork` now has a real Tokenformer path inside vLLM.
- It is still oriented around static adapter activation, not request-scoped BENDER context.
- The next implementation should add a `BenderCoprocessorAdapter` as a sibling to `TokenformerAdapter`, not treat BENDER as a static checkpoint swap.

## Desired next implementation

Implement in `../scalarlm/vllm-fork`:

1. A request-scoped `BenderCoprocessorContext`
   - fused vector
   - active entities
   - hypotheses
   - constraints
   - provenance
   - decode step / mode

2. A `BenderCoprocessorAdapter`
   - wraps selected late MLP blocks
   - reads current request context
   - computes a residual `delta_h`
   - adds `delta_h` to the base layer output

3. A surgeon/manager path that can install the adapter without turning it into a static LoRA-style weight load

4. Worker-side request plumbing so a generation request can set and clear the BENDER coprocessor context per request

## Important constraints

- Do not implement BENDER as prompt stuffing or GraphRAG.
- The native path should prove hidden-state or layer-output influence during inference.
- The BENDER runtime in this repo should remain the producer of the structured coprocessor packet.
- ScalarLM should consume that packet as request-scoped native context.

## Verification status

Verified locally in this session:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `PYTHONPATH=src python3 examples/hello_world_coprocessor_demo.py`
- `PYTHONPATH=src python3 examples/biomedical_coprocessor_demo.py`

All tests passed in the `bender` repo.

## Why the ScalarLM patch was not applied here

This Codex session can read `../scalarlm` but cannot write there because the writable sandbox roots do not include `/Users/richiek/work/scalarlm`.

To continue, restart Codex with a writable root that includes:

- `/Users/richiek/work/scalarlm`

or simply:

- `/Users/richiek/work`
