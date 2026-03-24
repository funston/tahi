# Tutorial

This tutorial shows the intended shape of BENDER:

1. build a world model
2. run the coprocessor runtime
3. inspect hypotheses, constraints, and provenance
4. scale that pattern into a real domain implementation

## Step 1: Understand The Core Boundary

The core package lives in `src/bender/`.

It owns:

- runtime orchestration
- retrieval and world state
- reasoning state
- fusion
- model integration contracts

It does not own domain-specific benchmark logic.

## Step 2: Run The Hello-World Proof

```bash
PYTHONPATH=src python examples/hello_world_coprocessor_demo.py
```

This proves the minimum viable coprocessor behavior:

- typed graph retrieval
- explicit rule firing
- exception handling
- provenance
- model-facing packet output

## Step 3: Look At A Real Reference Implementation

Use `bio` if you want a knowledge-heavy example:

```bash
PYTHONPATH=src python examples/bio_biomarker_demo.py --mode target-profile --target EGFR --disease NSCLC
```

Use `mass_spec` if you want a narrower, more constraint-heavy example:

```bash
PYTHONPATH=src python examples/mass_spec_demo.py --mode spectrum --case-id demo_glucose_sodium
```

## Step 4: Build Your Own World Model

The recommended pattern is:

1. define your domain entities and relations
2. load them into a `WorldModel`
3. write a small adapter that:
   - normalizes input entities
   - retrieves relevant state
   - derives hypotheses
   - preserves provenance
4. keep the implementation outside `src/bender`

In this repo, that is exactly how the packages under `implementations/` are structured.

## Step 5: Keep The Boundary Clean

Use this rule:

- `bender` is the framework
- `implementations/*` are examples of building on the framework

If benchmark-specific or customer-specific logic starts leaking into `src/bender`, the architecture is drifting in the wrong direction.

## Next Reading

- [Architecture](/Users/richiek/work/bender/docs/ARCHITECTURE.md)
- [Whitepaper Guide](/Users/richiek/work/bender/docs/WHITEPAPER.md)
- [Roadmap](/Users/richiek/work/bender/docs/ROADMAP.md)
