# Contributing

## Principles

- keep `src/bender` pure
- build domain and benchmark logic outside the core package
- prefer clear runtime contracts over benchmark-specific hacks
- preserve provenance and inspectability

## Setup

```bash
pip install -e .[dev]
```

Optional ANN dependencies:

```bash
pip install -e .[ann]
```

## Before Opening A Review

Run the focused suite:

```bash
pytest tests/test_bio.py tests/test_mass_spec.py tests/test_bird.py tests/test_hello_world_pipeline.py -q
```

Run at least one demo relevant to your change.

## Architectural Boundary

Use this dependency direction:

- `bender` must not import from `implementations`
- `implementations/*` may import from `bender`

If a change violates that rule, it is probably going in the wrong place.

## Documentation

When public behavior changes, update:

- `README.md`
- `docs/`
- the relevant implementation README

Older or superseded material should go to `docs/legacy/` rather than staying mixed into the main doc surface.
