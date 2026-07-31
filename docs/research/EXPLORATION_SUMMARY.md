# BENDER Codebase Exploration - Complete Summary

**Date:** July 25, 2026  
**Status:** Thorough exploration complete  
**Deliverables:** 3 comprehensive documents + this summary

---

## What Was Explored

This exploration analyzed the complete BENDER world-model coprocessor architecture through:

1. **Core source files** (`src/bender/*.py`)
   - Runtime orchestration (runtime.py, engine.py)
   - Data models (models.py, world_state.py)
   - Integration contracts (integration.py)
   - Signal fusion (fusion.py)
   - Domain reasoning (planner.py, rules.py, simulator.py)
   - World model storage (world_model_store.py)
   - Retrieval abstractions (retrieval/*.py)

2. **Architecture documentation** (`docs/*.md`)
   - ARCHITECTURE.md - High-level design
   - INTEGRATION_LEVELS.md - Integration spectrum
   - TUTORIAL.md - Getting started
   - QUICKSTART.md - Quick reference

3. **Status and analysis documents**
   - FTI_IMPLEMENTATION_COMPLETE.md - MLOps pattern implementation
   - BIRD_BENCHMARK_RESULTS.md - Real-world performance data
   - HONEST_STATUS_MARCH_2026.md - Candid assessment

---

## Three Exploration Documents Created

### 1. BENDER_ARCHITECTURE_EXPLORATION.md (1,159 lines)
**Comprehensive deep-dive covering:**
- Core runtime flow (7-stage pipeline)
- SemanticFrame and CognitiveState data models
- World model graph-based design (nodes, edges, retrieval)
- FTI MLOps pattern and WorldModelStore
- Fusion module signal blending algorithm
- Two-path integration (black-box + native)
- Domain reasoning layers (Planner, RuleEngine, Simulator)
- Integration levels spectrum (Level 0-2)
- Architectural decisions and trade-offs
- Provenance and auditability design
- Phase 1 intentional limitations
- Key takeaways and competitive moat

### 2. BENDER_ARCHITECTURE_VISUAL_SUMMARY.md
**Diagrams and visual explanations covering:**
- Core pipeline flow diagram (8 stages)
- World model graph structure example
- Integration levels comparison
- Retrieval architecture (InMemoryGraphIndex vs FAISS)
- Fusion signal blending flowchart
- FTI MLOps pattern visualization
- Domain reasoning layers breakdown
- RAG vs BENDER comparison table
- Integration boundaries (framework/domain split)
- Extension points (how to customize)
- Architectural decisions matrix
- Success criteria and next steps

### 3. EXPLORATION_SUMMARY.md (This file)
**Meta-summary and navigation guide**

---

## Key Findings

### 1. BENDER is NOT RAG

**RAG:** Query → Retrieve text passages → Serialize to prompt → Model reconstructs structure

**BENDER:** Query → Retrieve typed nodes → Apply rules → Emit structured state → Model uses control packet

**Distinction:** BENDER reasons BEFORE sending to model; RAG asks model to reason about retrieved text.

### 2. Core Architecture: 7-Stage Pipeline

```
1. Capture (SemanticFrame)
2. Retrieve (RetrievedMemory[])
3. Plan (Intent detection)
4. Rules (Domain logic)
5. Simulate (Validation)
6. Fuse (Signal blending)
7. Inject (ControlPacket)
```

Each stage adds provenance, making reasoning transparent.

### 3. World Model is a Typed Knowledge Graph

- **Nodes:** Entities with type, label, attributes (e.g., table, column, metric)
- **Edges:** Typed relations (has_column, foreign_key, etc.)
- **Retrieval:** Two strategies
  - Default: InMemoryGraphIndex (keyword matching, zero dependencies)
  - Optional: FAISS (semantic similarity, requires setup)
- **Key insight:** Structure is not serialized to text—it's kept structured

### 4. FTI MLOps Pattern (Feature/Training/Inference)

BENDER adopts SOTA architecture from Hopsworks:

- **Feature Pipeline:** Pre-build and version world models
  - `WorldModelStore` saves versioned graphs (e.g., `bird-dev:v1.0.0`)
  - Gzip compression (70% size reduction)
  - Manifest tracking (build date, node/edge counts)

- **Training Pipeline:** SKIP (model-agnostic, no fine-tuning)
  - Domain logic in graphs, not weights
  - Works with any base model

- **Inference Pipeline:** Load pre-built models at runtime
  - Lazy loading (`get_or_build()`)
  - Point-in-time consistency
  - 3x faster benchmarks (expected)

### 5. Fusion: How to Blend Two Signals

**WeightedBlendFusion** mixes token (LLM) and graph (domain) signals:

```
graph_weight = clamp(retrieval_strength + hypothesis_bonus + constraint_bonus, 0.15, 0.85)
token_weight = 1.0 - graph_weight

fused = token_weight * token_signal + graph_weight * graph_signal
```

**Why this matters:**
- Weights are explicit (interpretable)
- Graph signal can dominate when confident (doesn't wash out)
- Token signal is always preserved (fallback)
- Dynamic: weights change based on reasoning state

### 6. Two Integration Paths

**Level 1: Structured Control Mode (Black-box)**
- Produces ControlPacket (entities, constraints, hypotheses)
- Consumed at prompt-side (serialized to text)
- Works today with Claude, Gemini, Gemma, etc.
- Weak mode but better than plain RAG

**Level 2: Native Coprocessor Mode (Strong)**
- Produces FusedSignal (latent vector)
- Injected at token-generation time
- Requires inference-server support
- Example: ScalarLM reference backend
- Architectural goal: true coprocessor

### 7. Architectural Purity: Clear Boundaries

```
src/bender/              → Pure framework (generic)
└─ runtime.py          → Orchestration
   models.py           → Data structures
   world_state.py      → Graph storage
   retrieval/          → Search abstraction
   integration.py      → Model contracts
   fusion.py           → Signal blending
   planner.py          → Intent detection
   rules.py            → Generic domain logic
   simulator.py        → Validation

implementations/       → Domain-specific
├─ bird/              → SQL benchmark
├─ spider/            → Spider benchmark
├─ bio/               → Biomarker domain
└─ mass_spec/         → Mass spec domain

RULE: bender MUST NOT import from implementations
```

This keeps core generic and shows how to build on top.

### 8. Provenance by Design

Every stage adds ProvenanceRecord:
- stage: "capture", "retrieval", "planner", "rules", "simulation", "fusion", "injection"
- reference: Unique identifier (e.g., "integration:black_box", "rule:penguin_exception")
- detail: Explanation of what happened
- confidence: Numerical score

Result: Complete audit trail of reasoning (not black-box like RAG).

### 9. Extensibility Through Abstraction

BENDER defines abstract base classes for key components:

- `FusionModule.mix()` → Swap for attention-based fusion
- `ModelIntegration.capture/inject()` → Swap for vLLM, TGI, etc.
- `RuleEngine.apply()` → Extend with domain-specific rules
- Retrieval index → Swap InMemoryGraphIndex for PostgreSQL, FAISS, etc.

All components are swappable without changing core pipeline.

### 10. Real Performance Data

From BIRD benchmark (SQL generation):
- **Claude:** 20% → 26% accuracy (30% relative improvement) ✅
- **Qwen2.5-coder:14b:** 15% → 15% (0% improvement) ❌
- **Gemma3:27b:** 0% → 0% (0% improvement) ❌

**Insight:** BENDER helps when base model is capable. It cannot fix broken SQL generation.

---

## Critical Design Insights

### 1. Why Graph-Based?

Domains have structure (schemas, categories, hierarchies). A graph preserves this while text loses it.

**Example:** "penguin cannot fly"
- **Text-based:** Model must infer "penguin is a bird but an exception"
- **Graph-based:** Rule engine checks `(penguin, cannot_fly, TRUE)` directly

### 2. Why Deterministic Reasoning?

Planner uses keyword regex, not ML. This means:
- Reproducible (same query → same intent every time)
- Debuggable (know why "proportion" → share_of_total)
- Extensible (add pattern without retraining)

### 3. Why Separate Capture/Inject?

Decouples domain reasoning from model coupling:
- Core reasoning is model-agnostic
- Only boundaries (capture/inject) are model-specific
- Can add new backends without touching core

### 4. Why Linear Fusion (Not Attention)?

Phase 1 prioritizes interpretability. Linear blend:
- Weights explicit in output
- No learned parameters to hide behavior
- Attention can be added later as alternative

### 5. Why FTI Pattern?

- Reproducibility: version-lock world models
- Performance: 3x faster (no rebuild)
- Production-readiness: clear build/inference separation
- Collaboration: share pre-built models

---

## What BENDER Does Well

1. **Structured reasoning:** Explicit entities, relations, constraints
2. **Auditability:** Complete provenance trail
3. **Domain modularity:** Framework + domain implementations
4. **Integration flexibility:** Black-box + native paths
5. **Extensibility:** Swappable components
6. **Reproducibility:** Versioned world models (FTI)
7. **Model-agnosticism:** Works with any base model (via weak mode)

---

## What BENDER Doesn't Do

1. Replace LLMs (coprocessor, not replacement)
2. Fix broken base models (helps capable models)
3. Generate domain knowledge (requires manual modeling)
4. Work without retrieval (inherently retrieval-based)
5. Provide token-time influence without native backend (weak mode only)
6. Learn from examples (no training pipeline)

---

## Recommendations for Readers

**Start with:**
1. BENDER_ARCHITECTURE_VISUAL_SUMMARY.md (diagrams first)
2. Then BENDER_ARCHITECTURE_EXPLORATION.md (detailed dives)
3. Reference EXPLORATION_SUMMARY.md (this file) for navigation

**For specific topics:**
- Pipeline flow → Part 1 of exploration doc + visual diagram
- World model design → Part 2 of exploration + graph structure diagram
- Integration levels → Part 7 of exploration + levels diagram
- Fusion algorithm → Part 4 of exploration + fusion flowchart
- How to extend → Extension points section of visual summary
- Trade-offs → Part 8 of exploration + decisions matrix

**For implementation:**
- Read `/Users/richiek/work/bender/src/bender/runtime.py` (orchestration)
- Review `/Users/richiek/work/bender/src/bender/world_state.py` (graph storage)
- Study `/Users/richiek/work/bender/src/bender/fusion.py` (signal blending)
- Examine `/Users/richiek/work/bender/implementations/bird/` (reference domain)

---

## Files Analyzed

### Core Source
- `/Users/richiek/work/bender/src/bender/runtime.py` (119 lines) - Orchestration
- `/Users/richiek/work/bender/src/bender/models.py` (142 lines) - Data structures
- `/Users/richiek/work/bender/src/bender/world_state.py` (201 lines) - Graph storage
- `/Users/richiek/work/bender/src/bender/fusion.py` (77 lines) - Signal blending
- `/Users/richiek/work/bender/src/bender/integration.py` (115 lines) - Model contracts
- `/Users/richiek/work/bender/src/bender/planner.py` (106 lines) - Intent detection
- `/Users/richiek/work/bender/src/bender/rules.py` (112 lines) - Domain logic
- `/Users/richiek/work/bender/src/bender/simulator.py` (62 lines) - Validation
- `/Users/richiek/work/bender/src/bender/world_model_store.py` (324 lines) - FTI storage
- `/Users/richiek/work/bender/src/bender/retrieval/ann.py` (100+ lines) - ANN search
- `/Users/richiek/work/bender/src/bender/adapter.py` (99 lines) - LLM wrapper

### Documentation
- `/Users/richiek/work/bender/docs/ARCHITECTURE.md` (137 lines)
- `/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md` (136 lines)
- `/Users/richiek/work/bender/docs/TUTORIAL.md` (81 lines)
- `/Users/richiek/work/bender/FTI_IMPLEMENTATION_COMPLETE.md` (236 lines)
- `/Users/richiek/work/bender/README.md` (112 lines)
- `/Users/richiek/work/bender/CLAUDE.md` (Project guidelines)

**Total:** ~2,300 lines of core code + 1,100 lines of documentation analyzed

---

## Conclusion

BENDER represents a **fundamental architectural shift** from retrieval-based augmentation (RAG) to runtime-based reasoning. Key differentiators:

1. **Graph-based world models** (vs. flat document retrieval)
2. **Explicit deterministic reasoning** (vs. model-only inference)
3. **Structured control packets** (vs. raw text)
4. **Complete provenance** (vs. black-box reasoning)
5. **FTI MLOps pattern** (vs. on-demand building)
6. **Two integration paths** (vs. single prompt-side approach)

The architecture is:
- **Modular:** Swappable components (fusion, retrieval, rules)
- **Extensible:** Clear extension points
- **Maintainable:** Boundaries between core and domains
- **Auditable:** Complete provenance trails
- **Reproducible:** Versioned world models

Phase 1 achieves these goals while intentionally deferring production-scale concerns (FAISS retrieval, native backend integration) to later phases.

---

## Next Reading

For depth on specific topics:

| Topic | Document | Section |
|-------|----------|---------|
| Pipeline flow | Exploration | Part 1 |
| Graph design | Exploration | Part 2 |
| MLOps pattern | Exploration | Part 3 |
| Fusion algorithm | Exploration | Part 4 |
| Integration paths | Exploration | Part 5-7 |
| Domain reasoning | Exploration | Part 6 |
| Architectural decisions | Exploration | Part 8 |
| Extensibility | Visual Summary | Extension Points |
| Comparison | Visual Summary | RAG vs BENDER table |
| Diagrams | Visual Summary | All sections |

---

**Generated:** July 25, 2026  
**Exploration Status:** Complete ✅  
**Files Created:**
1. BENDER_ARCHITECTURE_EXPLORATION.md (1,159 lines)
2. BENDER_ARCHITECTURE_VISUAL_SUMMARY.md (450+ lines)
3. EXPLORATION_SUMMARY.md (this file)

All files available in `/Users/richiek/work/bender/`

