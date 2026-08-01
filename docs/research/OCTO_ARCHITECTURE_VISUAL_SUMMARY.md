# OCTO Architecture - Visual Summary

## Core Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ QUERY INPUT: "How many students attended schools in 2024?" │
└────────────────────┬────────────────────────────────────────────┘
 │
 ┌───────────▼────────────┐
 │ 1. CAPTURE (Model) │
 │ SemanticFrame │
 │ ├─ query │
 │ ├─ text_embedding │
 │ └─ hidden_state? │
 └───────────┬────────────┘
 │
 ┌────────────▼─────────────┐
 │ 2. RETRIEVE (World) │
 │ RetrievedMemory[] │
 │ ├─ schools table │
 │ ├─ student count column │
 │ ├─ year column │
 │ └─ relations (FK, etc) │
 └────────────┬─────────────┘
 │
 ┌───────────────▼──────────────┐
 │ 3. PLAN (Intent Detect) │
 │ ├─ db_id: "california" │
 │ ├─ query_intent: count │
 │ ├─ temporal_filter: true │
 │ └─ group_by_hint: true │
 └───────────────┬──────────────┘
 │
 ┌────────────────▼───────────────┐
 │ 4. RULES (Domain Logic) │
 │ ├─ semantic_role: METRIC │
 │ ├─ semantic_role: TEMPORAL │
 │ └─ hypothesis: "Use GROUP BY" │
 └────────────────┬───────────────┘
 │
 ┌─────────────────▼────────────────┐
 │ 5. SIMULATE (Validation) │
 │ ├─ has_numeric: true │
 │ ├─ structural_confidence: 0.95 │
 │ └─ checks: ["COUNT valid"] │
 └─────────────────┬────────────────┘
 │
 ┌──────────────────▼──────────────────┐
 │ 6. FUSE (Blend Signals) │
 │ token_weight: 0.35 │
 │ graph_weight: 0.65 │
 │ fused_vector: [0.2, 0.8, ...] │
 └──────────────────┬──────────────────┘
 │
 ┌───────────────────▼───────────────────┐
 │ 7. INJECT (Model-Facing Packet) │
 │ ControlPacket: │
 │ ├─ active_entities: [schools, ...] │
 │ ├─ hypotheses: [...] │
 │ ├─ constraints: {...} │
 │ ├─ prompt_hints: [...] │
 │ └─ fused_vector: [...] │
 └───────────────────┬───────────────────┘
 │
 ┌───────────▼────────────┐
 │ OUTPUT: CognitiveState│
 │ ├─ Control Packet │
 │ ├─ Provenance Trail │
 │ ├─ Hypotheses │
 │ ├─ Constraints │
 │ └─ Confidence Scores │
 └───────────┬────────────┘
 │
 ┌───────────▼────────────┐
 │ MODEL GENERATION │
 │ (Guided by Packet) │
 └────────────────────────┘
```

---

## World Model: Graph Structure

```
WORLD MODEL (Typed Knowledge Graph)
┌────────────────────────────────────────────────────┐
│ │
│ NODES (Typed Entities) │
│ ├─ "db:california.schools" → { │
│ │ type: "table", │
│ │ label: "schools", │
│ │ summary: "K-12 school records" │
│ │ } │
│ │ │
│ ├─ "db:california.schools.enrollment" → { │
│ │ type: "column", │
│ │ data_type: "INTEGER", │
│ │ label: "enrollment" │
│ │ } │
│ │ │
│ └─ "db:california.schools.year" → { │
│ type: "column", │
│ data_type: "INTEGER", │
│ label: "year" │
│ } │
│ │
│ EDGES (Typed Relations) │
│ ├─ (schools, has_column, enrollment) │
│ ├─ (schools, has_column, year) │
│ └─ (schools, foreign_key, districts) │
│ │
└────────────────────────────────────────────────────┘

KEY INSIGHT: Structure is NOT text—it's typed, relational, queryable
```

---

## Integration Levels

```
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 0: Retrieval Only (Not OCTO) │
│ Query → Vector search → Passages → Prompt │
│ ✗ No structure extraction │
│ ✗ No explicit constraints │
│ ✗ No provenance │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 1: Structured Control Mode (Weak, Available Today) │
│ │
│ Query → OCTO Reasoning → ControlPacket → Prompt │
│ (entities, constraints, (serialized) │
│ hypotheses, roles) │
│ │
│ ✓ Structured entities (not raw text) │
│ ✓ Explicit constraints (db_id, query_intent) │
│ ✓ Typed hypotheses with confidence │
│ ✓ Semantic roles (GEOGRAPHIC, METRIC, TEMPORAL) │
│ ✓ Complete provenance trail │
│ ✓ Works with any model (Claude, Gemini, Gemma, etc) │
│ ✗ Consumption is prompt-side (text serialization) │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 2: Native Coprocessor Mode (Strong, Requires Backend) │
│ │
│ Query → OCTO Reasoning → FusedSignal → Hidden-State Inject │
│ (entities, constraints, (latent vector) (token-time│
│ hypotheses, roles) generation) │
│ │
│ ✓ Token-time influence (generate-time) │
│ ✓ Direct hidden-state injection (no prompts) │
│ ✓ True parallel coprocessor (OCTO + Model in lockstep) │
│ ✓ Request-scoped context propagation │
│ ✗ Requires inference-server support │
│ ✗ Backend example: ScalarLM (reference implementation) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Retrieval Architecture

```
RETRIEVAL: Two Strategies

┌──────────────────────────────────┐
│ InMemoryGraphIndex (Default) │
│ ├─ Keyword matching on node text │
│ ├─ O(n) scan (small datasets OK) │
│ ├─ Zero dependencies │
│ ├─ Deterministic, offline │
│ ├─ Fast for schemas │
│ └─ Used by default │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ FAISS Index (Optional) │
│ ├─ Semantic similarity search │
│ ├─ SentenceTransformers encoded │
│ ├─ O(1) approximate lookup │
│ ├─ Better for NL queries │
│ └─ Enable: use_ann=True │
└──────────────────────────────────┘

Both return: RetrievedMemory[]
 ├─ node_id
 ├─ label
 ├─ score (relevance confidence)
 └─ relations (hydrated from graph)
```

---

## Fusion: Signal Blending

```
INPUT SIGNALS
┌─────────────────────────┐ ┌──────────────────────┐
│ Token Signal (LLM) │ │ Graph Signal (Domain)│
│ ├─ Text embedding │ │ ├─ Retrieved nodes │
│ ├─ OR hidden state │ │ ├─ Aggregated vector │
│ ├─ OR both (native) │ │ ├─ Score-weighted │
│ └─ Dimension: 8-384 │ │ └─ Dimension: same │
└───────┬─────────────────┘ └──────────┬───────────┘
 │ │
 └────────────────┬───────────────────┘
 │
 WEIGHT CALCULATION
 ┌──────────────▼────────────────┐
 │ retrieval_strength = avg( │
 │ [scores of retrieved items] │
 │ ) ∈ [0.0, 1.0] │
 │ │
 │ hypothesis_bonus = │
 │ 0.05 * num_hypotheses │
 │ │
 │ constraint_bonus = │
 │ 0.03 * num_constraints │
 │ │
 │ graph_weight = clamp([0.15, │
 │ retrieval_strength + │
 │ hypothesis_bonus + │
 │ constraint_bonus │
 │ ], 0.15, 0.85) │
 │ │
 │ token_weight = 1.0 - │
 │ graph_weight │
 └──────────────┬─────────────────┘
 │
 LINEAR BLEND (Element-wise)
 ┌────────────▼──────────────┐
 │ fused[i] = │
 │ token_weight * token[i] │
 │ + graph_weight * graph[i]│
 └────────────┬───────────────┘
 │
 OUTPUT: FusedSignal
 ├─ mixer: "WeightedBlendFusion"
 ├─ token_weight: 0.35
 ├─ graph_weight: 0.65
 ├─ vector: [fused vector]
 └─ rationale: "Graph weight rises..."
```

---

## FTI MLOps Pattern

```
TRADITIONAL: Rebuild Every Time
┌────────────────┐
│ Raw Data │
└───────┬────────┘
 │ (each run)
 ▼
┌──────────────────┐ ┌──────────────┐
│ Build World │──────│ OctoRuntime│
│ Model (15 min) │ │ Infer (5 min)│
└────────────────┬─┘ └──────────────┘
 │ (rebuilt next run!)
 ▼
 Wasteful 🔴

FTI PATTERN: Build Once, Use Forever
┌────────────────┐
│ Raw Data │
└───────┬────────┘
 │ (once)
 ▼
┌──────────────────────────────┐
│ Build & Version World Model │ Version: bird-dev:v1.0.0
│ (2 min) │ Manifest: 11 DBs, 207 nodes max
│ → WorldModelStore │ Compressed: 70% size reduction
│ → Gzipped JSON │
└──────────────┬───────────────┘
 │ (cached, reused)
 ┌──────▼──────────┬──────────┬──────────┐
 │ Exp 1 │ Exp 2 │ Exp 3 │
 │ (load 1ms + │ (load + │ (load + │
 │ infer 5min) │ infer) │ infer) │
 ▼ ▼ ▼
 Reproducible ✅ Faster ✅ Collaborative ✅

BENEFIT: 3x faster iteration (15 min → 5 min for 50 tasks)
```

---

## Domain Reasoning Layers

```
PLANNER (Query Intent Detection)
┌─────────────────────────────────────┐
│ Keyword Pattern Matching (Regex) │
│ ├─ "quantile" → window_quantile │
│ ├─ "growth in" → growth_analysis │
│ ├─ "proportion" → share_of_total │
│ └─ "year" → temporal_filter │
│ │
│ Output: state.constraints dict │
│ ├─ query_intent │
│ ├─ db_id (identified from retrieval)│
│ └─ structural hints │
└─────────────────────────────────────┘

RULES (Domain-Specific Logic)
┌─────────────────────────────────────┐
│ Semantic Role Discovery │
│ ├─ "student_count" → ROLE_METRIC │
│ ├─ "school_name" → ROLE_GEOGRAPHIC │
│ ├─ "enrollment_date" → ROLE_TEMPORAL│
│ │
│ Pattern Rules │
│ ├─ proportion queries → share_join │
│ ├─ growth queries → self_join │
│ ├─ "penguin" + "cannot_fly" → exc. │
│ │
│ Output: state.hypotheses list │
│ (confidence-scored conclusions) │
└─────────────────────────────────────┘

SIMULATOR (Structural Validation)
┌─────────────────────────────────────┐
│ Before generation, validate: │
│ ├─ "self_join_on_month" proposed? │
│ → Check: retrieved data has │
│ date column? (-50% confidence)│
│ │
│ ├─ "proportion_join" proposed? │
│ → Check: metric AND key? (-60%) │
│ │
│ └─ Aggregation required? │
│ → Check: numeric columns? (-30%) │
│ │
│ Output: state.simulation_state │
│ ├─ checks: [...] │
│ └─ structural_confidence: 0.95 │
└─────────────────────────────────────┘
```

---

## Comparison: RAG vs OCTO

```
┌──────────────────────┬───────────────────┬───────────────────┐
│ Aspect │ RAG │ OCTO │
├──────────────────────┼───────────────────┼───────────────────┤
│ Knowledge │ Text passages │ Typed graph │
│ representation │ (flat vectors) │ (nodes + relations)│
│ │ │ │
│ Reasoning │ Model only │ Explicit planning │
│ (where happens) │ (black-box) │ + rules + sim │
│ │ │ │
│ Constraints │ Implicit │ Explicit │
│ │ (prompt hints) │ (typed dict) │
│ │ │ │
│ Provenance │ None │ Complete audit │
│ │ (hidden reasoning)│ trail │
│ │ │ │
│ Confidence scores │ Retrieval only │ Per reasoning │
│ │ │ stage + composites│
│ │ │ │
│ Model control │ Prompt-side │ Prompt-side (weak)│
│ │ Text serialization│ or token-time │
│ │ │ (strong native) │
│ │ │ │
│ Reproducibility │ Document drift │ Versioned world │
│ │ │ models (FTI) │
└──────────────────────┴───────────────────┴───────────────────┘
```

---

## Integration Boundaries

```
ARCHITECTURAL PURITY RULE

src/octo/ ← Pure Framework
├─ runtime.py ← Orchestration
├─ models.py ← Data structures
├─ world_state.py ← Graph storage
├─ retrieval/ ← Search abstraction
├─ integration.py ← Model contracts
├─ fusion.py ← Signal blending
├─ planner.py ← Intent detection
├─ rules.py ← Generic domain logic
└─ simulator.py ← Validation

implementations/ ← Domain-Specific
├─ bird/ ← SQL benchmark
│ ├─ claude_generator.py ← Claude SQL gen
│ └─ execution.py ← Execution harness
│
├─ spider/ ← Spider benchmark
│
├─ bio/ ← Biomarker domain
│
└─ mass_spec/ ← Mass spec domain

RULE: octo MUST NOT import from implementations
RESULT: Core is generic, extensions are domain-specific
```

---

## Extension Points (How to Customize)

```
FUSION MODULE
┌─────────────────────────────────────────────┐
│ class AttentionFusion(FusionModule): │
│ def mix(token_signal, graph_signal, │
│ state: CognitiveState): │
│ # Compute attention weights │
│ # Return FusedSignal │
│ │
│ runtime = OctoRuntime( │
│ world_model, │
│ fusion=AttentionFusion() # ← Swap here│
│ ) │
└─────────────────────────────────────────────┘

RETRIEVAL INDEX
┌─────────────────────────────────────────────┐
│ class PostgresGraphIndex(GraphIndex): │
│ def search(query, top_k): │
│ # Query PostgreSQL directly │
│ # Return RetrievedMemory[] │
│ │
│ world_model._index = PostgresGraphIndex() │
└─────────────────────────────────────────────┘

DOMAIN RULES
┌─────────────────────────────────────────────┐
│ class BirdRules(RuleEngine): │
│ def apply(state): │
│ super().apply(state) │
│ # Add BIRD-specific rules │
│ return state │
│ │
│ runtime = OctoRuntime( │
│ world_model, │
│ rules=BirdRules() # ← Swap here │
│ ) │
└─────────────────────────────────────────────┘

MODEL INTEGRATION
┌─────────────────────────────────────────────┐
│ class vLLMIntegration(ModelIntegration): │
│ def capture(...) → SemanticFrame: │
│ def inject(...) → ControlPacket: │
│ │
│ runtime = OctoRuntime( │
│ world_model, │
│ integration=vLLMIntegration() # ← Swap │
│ ) │
└─────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| Knowledge rep | Graph (typed nodes+rels) | ✅ Expressive, ❌ requires modeling |
| Retrieval | Lightweight default (InMemoryGraphIndex), FAISS optional | ✅ Simple, ❌ less semantic |
| Fusion | Linear weighted blend | ✅ Interpretable, ❌ less expressive |
| Domain logic | In graphs/rules (not weights) | ✅ Explainable, ❌ manual engineering |
| Integration | Two paths (black-box + native) | ✅ Flexible, ❌ more code |
| Versioning | FTI pattern (build once, version) | ✅ Reproducible, ❌ extra step |
| Phase 1 scope | Runtime + Level 1 integration | ✅ Focused, ❌ native needs backend work |

---

## Success Criteria

| Criterion | Metric | Status |
|-----------|--------|--------|
| Architectural clarity | Can explain reasoning | ✅ Complete provenance |
| Reproducibility | Version-lock results | ✅ FTI pattern implemented |
| Model-agnosticism | Works across base models | ⚠️ Claude strong, others weak |
| Integration contract | Two clear paths | ✅ Black-box + Native defined |
| Code cleanliness | Framework/domain boundary | ✅ implementations/ separate |
| Extensibility | Can swap components | ✅ Fusion, rules, retrieval swappable |
| Performance | Benchmark improvement | ⚠️ 30% with Claude, 0% with others |

---

## Next Steps

**Phase 2: Production Retrieval**
- Migrate to FAISS/HNSW for large-scale retrieval
- Add S3 backend to WorldModelStore
- Benchmark vs PostgreSQL full-text search

**Phase 3: Native Backend Integration**
- vLLM adapter for open-source models
- TGI (Text Generation Inference) support
- ScalarLM validation

**Phase 4: Domain Simulators**
- SQL query planner (pre-validate JOIN feasibility)
- Biomarker inference engine
- Custom domain-specific validators

**Phase 5: Production Deployment**
- Multi-region WorldModelStore
- Request batching for inference server
- Cost optimization (model selection by domain difficulty)

