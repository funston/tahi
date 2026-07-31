# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BENDER is a World-Model Coprocessor for Large Language Models. It operates as a parallel cognitive system alongside LLMs, providing persistent world models, graph reasoning, simulation, and token-time intervention during inference. The core principle is that BENDER is a true coprocessor, not just a RAG wrapper.

## Development Commands

### Running Tests

Tests use Python's built-in `unittest` module:

```bash
# Run a single test file
PYTHONPATH=src .venv/bin/python tests/test_hello_world_pipeline.py

# Run all tests (from any test file)
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests

# Run a specific test
PYTHONPATH=src .venv/bin/python -m unittest tests.test_hello_world_pipeline.HelloWorldPipelineTests.test_penguin_exception_is_explicit_in_reasoning_pipeline
```

### Running Examples

```bash
# Set PYTHONPATH and run examples
PYTHONPATH=src .venv/bin/python examples/hello_world_coprocessor_demo.py
PYTHONPATH=src .venv/bin/python examples/sql_schema_coprocessor_demo.py
```

### Environment Setup

- Python 3.13 is used (see `.venv/pyvenv.cfg`)
- Virtual environment is at `.venv/`
- Set `PYTHONPATH=src` before running

## Architecture

### Core Runtime Flow

The BENDER runtime follows a stable pipeline:

1. `ModelIntegration.capture(...)` - captures model-side state (SemanticFrame)
2. `WorldModel.retrieve(...)` - retrieves structured graph memories
3. `Planner`, `RuleEngine`, `Simulator` - update CognitiveState
4. `FusionModule.mix(...)` - blends model-side and graph-side signals
5. `ModelIntegration.inject(...)` - produces ControlPacket for the model

### FTI MLOps Architecture (NEW: 2026-03-28)

BENDER adopts the Feature/Training/Inference (FTI) MLOps pattern:

- **WorldModelStore** (`src/bender/world_model_store.py`): Versioned world model storage
- **Feature Pipeline analog**: Pre-build and version world models (build once, use forever)
- **Inference Pipeline analog**: BenderRuntime loads pre-built models on demand
- **No Training Pipeline**: Model-agnostic design (domain logic in graphs, not weights)

**Key Benefits:**
- 3x faster benchmarks (pre-built vs rebuilt)
- Reproducible research (semantic versioning)
- Production-ready infrastructure

**Usage:**
```python
from bender import WorldModelStore
store = WorldModelStore("~/.bender/world-models/")
store.save(world, source="bird-dev", version="v1.0.0", model_id="db_id")
world = store.load("bird-dev", "v1.0.0", "db_id")
```

See: `FTI_IMPLEMENTATION_COMPLETE.md` and `examples/world_model_store_demo.py`

### Key Modules

**Stable Core Runtime** (rarely modified):
- `src/bender/runtime.py` - BenderRuntime orchestrator
- `src/bender/models.py` - SemanticFrame, CognitiveState, ControlPacket, FusedSignal
- `src/bender/integration.py` - ModelIntegration, BlackBoxIntegration, NativeIntegration
- `src/bender/fusion.py` - FusionModule, WeightedBlendFusion

**Domain Reasoning Layer**:
- `src/bender/world_state.py` - WorldModel with typed nodes/relations and retrieval
- `src/bender/retrieval.py` - InMemoryGraphIndex, embedding helpers
- `src/bender/planner.py` - deterministic planning steps
- `src/bender/rules.py` - domain-specific rule engine
- `src/bender/simulator.py` - domain evaluators

**Delivery Surfaces**:
- `src/bender/adapter.py` - wrap_llm() helper for demos
- `examples/` - runnable demonstrations
- `tests/` - unittest-based test suite

### Model Integration Types

- **BlackBoxIntegration**: For API-only/closed-weight models; emits structured control context
- **NativeIntegration**: For open-weight models with hidden-state access
- **NativeTokenformerIntegration**: Design stub for ScalarLM's vLLM Tokenformer integration

### SQL Coprocessor Architecture

The SQL reasoning layer follows a layered design:

1. **Generic SQL Schema Model** (`database.py`, `sql_coprocessor.py`)
   - SQLSchemaSnapshot, SQLSchemaPlanner, SQLSchemaRuleEngine
   - Reusable base for any SQL-backed domain

2. **Database Adapters** (`database.py`)
   - PostgresSchemaIntrospector (current)
   - Future: MySQL, SQLite, DuckDB, Snowflake

3. **Domain-Specific Layers**
   - `spider.py` - Spider benchmark-specific planner/rules
   - `spider_lite.py` - Spider Lite evaluation harness
   - `spider_snow.py` - Spider Snowflake benchmark

## Important Design Principles

### World Model is Graph-Based, Not Document-Based

BENDER retrieves typed nodes and relations, not serialized documents. The WorldModel stores structured knowledge that the runtime processes into constraints, hypotheses, and provenance.

### Integration Boundary

All model coupling lives in `integration.py`. The reasoning modules (planner, rules, simulator) remain model-agnostic.

### Extension Points

The code is modular at these boundaries:
- Swap retrieval/index backend (planned: FAISS/HNSW/PQ)
- Swap fusion strategy
- Add domain-specific rules
- Add domain simulators
- Add new ModelIntegration backends

## File Organization

- `src/bender/` - Main Python package
- `examples/` - Runnable demos (hello_world, biomedical, SQL coprocessor)
- `tests/` - unittest test files
- `docs/` - Architecture and design documents
- `scripts/` - Build and setup scripts
- `whitepaper/` - Research paper drafts

## Current Limitations (Phase 1)

- Retrieval is in-memory and heuristic (not FAISS/HNSW-backed)
- Native integration defines hidden-state packet contract but doesn't patch a transformer
- Simulation is deterministic heuristics, not domain simulators

These limitations are intentional Phase 1 scope, not missing prerequisites.

## Working with the Codebase

When adding new features:
- Place generic SQL reasoning in `database.py`/`sql_coprocessor.py`
- Place benchmark-specific logic in `spider*.py` files
- New domain rules go in `rules.py` or domain-specific modules
- New integration backends extend `ModelIntegration` in `integration.py`

When modifying retrieval:
- The current InMemoryGraphIndex is intentionally simple
- For production, plan migration to FAISS/HNSW rather than growing custom search

When working with Spider benchmarks:
- Spider Lite is the first practical target
- BENDER produces schema-planning packets, not direct SQL
- Follow the phase order: planning → SQL generation → execution repair
- always be verbose in your progress and status