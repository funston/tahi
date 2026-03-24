# BENDER Success Metrics

## Purpose

The first useful way to measure BENDER is not "did the architecture sound good on paper?"

It is:

- what changes when BENDER is turned on,
- what stays the same when it should,
- what extra cost is introduced,
- whether the added cost buys useful reasoning, constraints, and provenance.

## Measurement principle

For the current Phase 1 system, success should be measured as a **with-BENDER versus without-BENDER delta** on the same query.

That means every early evaluation should compare:

- a baseline path with no structured world-model support,
- a BENDER-enabled path with retrieval, rules, simulation, and packet emission.

In the current codebase, the cleanest prototype baseline is an empty-world model using the same wrapper surface. That isolates the effect of BENDER's world model and reasoning pipeline from the rest of the demo shell.

## What "success" means right now

### 1. Reasoning gain

BENDER should recover domain facts, exceptions, or relation intersections that the baseline path cannot recover.

Examples:

- `Can a penguin fly?`
  BENDER should recover the penguin exception.
- `What animals in Antarctica eat fish?`
  BENDER should recover the set intersection `penguin, seal`.
- `Can marine bacteria produce antimalarial compounds for screening?`
  BENDER should recover the screening hypothesis and the screening-priority constraint.

### 2. Constraint gain

BENDER should produce structured constraints that the baseline path does not produce.

Examples:

- `mobility_exception = penguin_cannot_fly`
- `antarctic_fish_eaters = [penguin, seal]`
- `screening_priority = natural_products`
- `assay_target = plasmodium_falciparum`

### 3. Provenance gain

BENDER should emit more reasoning and provenance detail than the baseline path.

Minimum expectation:

- retrieval references,
- rule references,
- simulation references where applicable,
- integration references.

### 4. Retrieval gain

BENDER should surface relevant entities and relations that are absent in the baseline path.

This is especially important for the current prototype because the graph runtime is the main source of nontrivial domain state.

### 5. Latency cost

BENDER should report the added wall-clock cost of the coprocessor path.

At this stage, latency is not yet a hard gate in tests, but it should be measured on every evaluation run so we can track whether added reasoning value remains worth the cost.

## Current evaluation surfaces

The current comparison harness is in:

- `src/bender/evaluation.py`
- `examples/compare_with_without_bender.py`
- `tests/test_comparison_evaluation.py`

The harness records:

- entity gain,
- retrieval gain,
- provenance gain,
- constraint gain,
- required hypothesis presence with BENDER,
- required absence of those hypotheses without BENDER,
- per-case wall-clock time for both paths.

## Hello World success criteria

Hello World succeeds when:

1. With BENDER, the system explicitly resolves the penguin exception.
2. Without BENDER, the baseline does not recover that exception from structured state.
3. With BENDER, the system resolves the Antarctic fish-eater intersection.
4. Without BENDER, the baseline does not produce that set-level answer.

This is not just a toy task. It is the smallest readable proof of:

- exception handling,
- relation intersection,
- structured constraints,
- provenance-bearing reasoning.

## BIO success criteria

The first biomedical vertical succeeds when:

1. With BENDER, the system links marine bacteria to antimalarial screening.
2. With BENDER, the system links the assay target to `Plasmodium falciparum`.
3. Without BENDER, the baseline does not produce those structured constraints or hypotheses.
4. The provenance trace makes the biomedical reasoning path inspectable.

## Native-path success criteria

For the ScalarLM/vLLM native path, success should be measured separately from the black-box path.

The key questions are:

1. Does the BENDER context produce per-request latent influence?
2. Does that influence remain request-scoped within a batch?
3. Can the native path preserve the same structured control contract as the black-box path?
4. What latency overhead does native coupling add relative to prompt or prefill-only modes?

## What not to confuse with success

At this stage, these are not yet success criteria:

- beating state-of-the-art benchmarks,
- replacing all RAG systems,
- proving universal agent reliability,
- proving production-grade graph construction,
- proving a final best latent-fusion mechanism.

Those are later-stage goals.

## Bottom line

The first meaningful BENDER metric is simple:

`When BENDER is on, do we get more correct structured reasoning, more useful constraints, and more provenance than when BENDER is off, at a latency cost we can quantify?`

That is the right success definition for Hello World, for the BIO vertical, and for the first native integration milestone.
