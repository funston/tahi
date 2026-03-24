# BENDER SDK Architecture

## Goals

- Wrap existing LLMs without retraining
- Allow multiple deployment modes
- Expose world-model reasoning as a first-class runtime
- Support open- and closed-weight models

## Top-level developer experience

```python
import bender

wm = bender.WorldModel(domain="legal")
llm = bender.wrap_llm("claude-like-model", world_model=wm)

answer = llm.ask(
    "What precedent conflicts with this argument?",
    mode="coprocessor",
    trace=True,
)
```

## Core objects

### WorldModel
Maintains typed graph state, provenance, embeddings, and schema adapters.

### CognitiveState
Maintains active entities, relations, constraints, hypotheses, retrievals, planner state, simulation state, fused signals, and provenance during a session.

### BenderRuntime
Coordinates model-side capture, world-model retrieval, reasoning, simulation, fusion, and packet injection back to the LLM.

### LLMAdapter
Abstracts each provider/model:
- prompt-only
- embedding-only
- hidden-state hooks
- full open-weight runtime integration

In the current code this surface is represented by `ModelIntegration`, with `BlackBoxIntegration` and `NativeIntegration` implementations.

## Suggested package structure

- `bender.runtime`
- `bender.integration`
- `bender.world_model`
- `bender.retrieval`
- `bender.fusion`
- `bender.reasoning`
- `bender.simulation`
- `bender.provenance`

## Modes

### `mode="compat"`
Prompt / response compatibility mode for hosted APIs.

### `mode="coprocessor"`
Reasoning and graph state actively shape generation.

### `mode="latent"`
Open-weight mode with deeper hidden-state fusion.

## Phase 1 API surface

```python
import bender

wm = bender.WorldModel(domain="biomedical")
model = bender.wrap_llm(
    "demo-model",
    world_model=wm,
    integration=bender.BlackBoxIntegration(),
)

result = model.ask(
    "Can marine bacteria produce antimalarial compounds?",
    mode="coprocessor",
    trace=True,
)
```

Native path:

```python
model = bender.wrap_llm(
    "demo-open-weight-model",
    world_model=wm,
    integration=bender.NativeIntegration(),
)

result = model.ask(
    "Can marine bacteria produce antimalarial compounds?",
    mode="latent",
    hidden_state=[...],
)
```

## What is real vs placeholder

- Real: runtime boundaries, retrieval loop, cognitive packet, provenance flow, pluggable fusion, black-box integration surface, and native hidden-state contract.
- Placeholder: actual transformer hook-up for `NativeIntegration`, large-scale ANN backends, and domain-specific simulators.
