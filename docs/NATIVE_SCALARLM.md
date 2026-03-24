# Native ScalarLM Backend

This document describes the current native backend dependency for BENDER.

## Summary

The deepest current BENDER integration requires a modified inference backend.

Today, that backend is the local ScalarLM branch:

- `rschiavi/bender`

This is not a dependency of the pure `bender` package. It is a dependency of **native coprocessor mode**.

## Why It Is Needed

Native coprocessor mode requires the inference server to support:

- request-scoped BENDER context on each request
- propagation of that context through scheduling and batching
- worker-side access to active BENDER state
- model-layer hooks that can consume the BENDER signal during generation

Generic model serving stacks do not expose this automatically.

## What BENDER Expects

At the backend boundary, BENDER expects support for a structured coprocessor packet containing:

- fused vector
- active entities
- hypotheses
- constraints
- provenance
- decode-step metadata

In the current code, the design objects for this are in [integration.py](/Users/richiek/work/bender/src/bender/integration.py#L58).

## What ScalarLM Provides

The ScalarLM branch is the current reference backend for:

- request-scoped Tokenformer context
- late-layer residual influence
- worker-side activation of BENDER context

The older detailed backend design note is preserved in [docs/legacy/scalarlm_vllm_integration.md](/Users/richiek/work/bender/docs/legacy/scalarlm_vllm_integration.md).

## Important Boundary

Keep this distinction explicit:

- `src/bender` = framework/runtime
- ScalarLM branch = current native backend implementation

BENDER core should stay backend-agnostic even if the strongest current backend is ScalarLM-specific.
