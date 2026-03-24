# Mass Spec World Model

`implementations/mass_spec` is a reference world-model package for mass spectrometry interpretation built on top of `bender`.

## What This Implementation Demonstrates

- observed peak interpretation with deterministic mass checks
- analyte / adduct / polarity / instrument-mode reasoning
- sample-context effects such as sodium-adduct bias
- provenance-backed candidate explanations instead of free-form text synthesis

## Demo Workflows

Spectrum interpretation:

```bash
python examples/mass_spec_demo.py --mode spectrum --case-id demo_glucose_sodium
```

Analyte profile:

```bash
python examples/mass_spec_demo.py --mode analyte-profile --analyte Caffeine --polarity positive
```

## Why This Is A Strong Counterexample To Plain RAG

A plain RAG stack can retrieve documents about adducts and analytes, but it still leaves the hard part inside the model prompt:

- apply the correct adduct arithmetic
- respect polarity constraints
- account for instrument compatibility
- factor sample matrix effects
- preserve which source supported which hypothesis

In other words, RAG can retrieve text about mass spectrometry, but peak assignment needs constrained reasoning over structured state. That is exactly what the world-model layer is for.
