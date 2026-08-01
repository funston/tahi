# BIRD Leaderboard Plan

This document describes the concrete path from OCTO's current BIRD grounding result to a leaderboard-level BIRD execution result.

## Current State

What OCTO has now:

- a full BIRD dev grounding benchmark
- a real lift from `schema_only` to `octo_with_evidence`
- a browser-readable BIRD report:
 - [bird_benchmark_report.html](/Users/richiek/work/bender/benchmarks/bird/bird_benchmark_report.html)

What OCTO does not have yet:

- an official BIRD execution accuracy score
- a leaderboard-comparable end-to-end SQL benchmark

## Goal

Reach a BIRD result that is defensible next to the official leaderboard:

- end-to-end SQL generation
- execution-based evaluation
- reproducible benchmark artifact
- clear comparison against public leaderboard systems

## Non-Negotiable Rule

Do not compare grounding accuracy directly to official BIRD execution accuracy.

Grounding is diagnostic.
Execution accuracy is leaderboard-level.

The work below is about closing that gap.

## Phase 1. Lock The Measurement Stack

Deliverables:

- `benchmarks/bird/full_dev_grounding_report.json`
- `benchmarks/bird/bird_benchmark_report.html`
- a new execution benchmark artifact alongside them

Required changes:

1. Add a BIRD execution runner
 - input: BIRD task set + sqlite dbs
 - output:
 - generated SQL
 - execution success/failure
 - execution accuracy against reference
 - error taxonomy

2. Keep grounding metrics and execution metrics separate
 - grounding:
 - full gold-table recall
 - avg table recall
 - top-1 hit
 - execution:
 - execution accuracy
 - invalid SQL rate
 - repair success rate

3. Produce one BIRD execution HTML report
 - same standard as the current grounding report
 - must include:
 - metric definition
 - exact run settings
 - model/backend used
 - comparison against public leaderboard context

## Phase 2. Turn OCTO Into The Front-End Of A Real SQL Solver

Current weakness:

- OCTO is strong at grounding
- OCTO is not yet proving end-to-end SQL generation quality

Required changes:

1. Use OCTO as the world-coprocessor front-end
 - candidate tables
 - join/path hypotheses
 - evidence-aware constraints
 - provenance

2. Put a strong SQL generator behind it
 - first acceptable path:
 - prompted ScalarLM or other strong SQL-capable backend
 - target path:
 - native coprocessor mode with ScalarLM backend support

3. Run multiple candidates
 - not just one SQL attempt
 - need:
 - candidate generation
 - execution filter
 - repair loop
 - reranking

4. Treat OCTO as a reranking and repair advantage
 - OCTO should improve:
 - schema grounding
 - evidence use
 - error recovery
 - candidate selection

## Phase 3. Evidence-Aware Execution Pipeline

The strongest signal in current BIRD results is:

- `octo_with_evidence` beats `schema_only`

That suggests the next execution pipeline should explicitly include:

1. Question
2. BIRD evidence field
3. OCTO grounding packet
4. SQL candidate generation
5. SQL execution
6. repair + retry

This should become the default serious BIRD pipeline.

## Phase 4. Build The Baseline Matrix

To be taken seriously, every BIRD execution report should include:

1. naive baseline
 - no OCTO

2. schema-only baseline
 - no metadata or evidence

3. OCTO grounding only
 - metadata/documents only

4. OCTO + evidence
 - current strongest path

5. OCTO + evidence + repair
 - likely near-term production candidate

6. OCTO + evidence + repair + native backend
 - target architecture path

Without this matrix, it will be too easy for outsiders to dismiss gains as prompt noise.

## Phase 5. Official Credibility Criteria

Before claiming "leaderboard-level" publicly, the run should satisfy all of these:

1. full BIRD dev split
2. end-to-end execution metric
3. exact model/backend named
4. reproducible command
5. HTML report with failures and caveats
6. direct comparison against the current official leaderboard context

## Concrete Next Steps

1. Build `examples/run_octo_bird_execution_benchmark.py`
2. Add execution scoring to `implementations/bird`
3. Run the first end-to-end BIRD dev baseline with:
 - schema-only
 - octo_with_evidence
4. Add repair loop
5. Add stronger SQL generation backend
6. Regenerate a BIRD execution benchmark report

## Priority Order

1. BIRD execution benchmark runner
2. BIRD execution HTML report
3. OCTO + evidence + repair path
4. strong generator backend
5. native coprocessor backend path

## Honest Summary

Right now OCTO has a real BIRD grounding result.

That is useful.

It is not yet a leaderboard result.

The path to leaderboard-level is not more chart styling. It is:

- execution benchmark
- strong generator
- repair loop
- reproducible reporting
