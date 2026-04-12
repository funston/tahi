# Quick Start

## Install

From the repository root:

```bash
pip install -e .
```

If you want the heavier ANN stack:

```bash
pip install -e .[ann]
```

## Run A Minimal Demo

```bash
PYTHONPATH=src python examples/hello_world_coprocessor_demo.py
```

This is the smallest proof that BENDER is doing more than retrieval:

- it builds world state
- applies explicit rules
- records provenance
- emits a model-facing control packet

Note:

- these quick-start demos use **structured control mode**
- they do **not** require the native ScalarLM backend
- native coprocessor mode is documented in [Integration Levels](/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md)

## Run A Knowledge-Heavy Demo

```bash
PYTHONPATH=src python examples/bio_biomarker_demo.py --mode biomarker --case-id demo_her2_breast
```

## Run A Scientific Constraint Demo

```bash
PYTHONPATH=src python examples/mass_spec_demo.py --mode spectrum --case-id demo_glucose_sodium
```

## Run Tests

```bash
pytest tests/test_bio.py tests/test_mass_spec.py tests/test_bird.py tests/test_hello_world_pipeline.py -q
```

## Repo Layout

- `src/bender/` — pure core package
- `implementations/` — reference world models
- `examples/` — runnable demos
- `docs/` — public docs
- `whitepaper/` — current paper draft
