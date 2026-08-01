# OCTO World Coprocessor Architecture - Deep Exploration

**Date:** July 25, 2026 
**Scope:** Comprehensive analysis of OCTO's world coprocessor architecture 
**Focus:** Core runtime, world model graph design, FTI MLOps pattern, fusion module, and architectural decisions

---

## Executive Summary

OCTO is a **world-model coprocessor framework** that operates as a parallel cognitive system alongside LLMs. Rather than asking models to reconstruct domain structure from retrieved text (like RAG), OCTO:

1. **Captures** model-side semantic state
2. **Retrieves** structured world state (typed nodes and relations)
3. **Reasons** over entities, constraints, hypotheses, and domain rules
4. **Fuses** model-side signals with graph-side signals
5. **Injects** a control packet to guide model behavior

The key architectural distinction from RAG: OCTO is not a retrieval system but a **runtime reasoning layer** that preserves structure, applies constraints, and maintains provenance throughout the pipeline.

---

## Part 1: Core Runtime Flow

### 1.1 The Pipeline Contract

`OctoRuntime.infer()` in `/Users/richiek/work/bender/src/octo/runtime.py` orchestrates the complete pipeline:

```
Input Query
 ↓
1. ModelIntegration.capture() → SemanticFrame
 ↓
2. WorldModel.retrieve() → RetrievedMemory[]
 ↓
3. Planner.plan() → CognitiveState (constraints, planner_state)
 ↓
4. RuleEngine.apply() → CognitiveState (hypotheses, semantic roles)
 ↓
5. Simulator.run() → CognitiveState (confidence scores)
 ↓
6. FusionModule.mix() → FusedSignal (blended token+graph vectors)
 ↓
7. ModelIntegration.inject() → ControlPacket
 ↓
Output CognitiveState (complete reasoning trace)
```

### 1.2 SemanticFrame: Model-Side Capture

The `SemanticFrame` (in `/Users/richiek/work/bender/src/octo/models.py`) captures everything the model knows at inference time:

```python
@dataclass
class SemanticFrame:
 query: str # Original query text
 mode: str = "coprocessor" # Integration mode (coprocessor/native)
 decode_step: int = 0 # Token generation step (native mode)
 semantic_query: str = "" # Optional refined query
 text_embedding: Vector # Query embedding (text only)
 hidden_state: Optional[Vector] = None # Model hidden state (native mode only)
 token_window: List[str] = [] # Recent token context
 metadata: Dict[str, Any] # Integration-specific metadata
```

**Key insight:** The frame separates **text-only signal** (always available) from **hidden-state signal** (native mode only). This two-path design allows both black-box and native integrations.

### 1.3 CognitiveState: Reasoning State Machine

The `CognitiveState` accumulates reasoning outputs:

```python
@dataclass
class CognitiveState:
 entities: List[EntityRef] # Retrieved entities with scores
 relations: List[RelationRef] # Typed relations (e.g., "table:x has_column table:y:column")
 constraints: Dict[str, Any] # Query-specific constraints (db_id, query_intent, etc.)
 hypotheses: List[Hypothesis] # Reasoning conclusions with confidence
 planner_state: Dict[str, Any] # Planning metadata
 simulation_state: Dict[str, Any] # Simulation results
 retrievals: List[RetrievedMemory] # Full retrieval records with relations
 provenance_records: List[ProvenanceRecord] # Complete reasoning audit trail
 fused_signal: Optional[FusedSignal] # Blended model+graph signal
 control_packet: Optional[ControlPacket] # Model-facing output
```

**Critical design:** Every stage adds provenance. This makes OCTO's reasoning transparent and auditable, unlike RAG which obscures reasoning.

### 1.4 Control Packet: Model-Facing Output

The final `ControlPacket` bridges OCTO's reasoning to the model:

```python
@dataclass
class ControlPacket:
 integration: str # Integration type (black_box / native_hidden_state)
 prompt_hints: List[str] # Text guidance for prompt construction
 active_entities: List[str] # Retrieved entities to focus on
 hypotheses: List[str] # Structured reasoning conclusions
 constraints: Dict[str, Any] # Domain constraints and patterns
 fused_vector: Vector # Blended latent signal
 provenance: List[str] # Reasoning audit trail
 metadata: Dict[str, Any] # Integration-specific metadata
```

**Why this matters:** The packet is NOT raw retrieved text. It's:
- Deduplicated entities
- Typed relations
- Explicit hypotheses with confidence scores
- Domain constraints extracted by rules
- A blended vector that combines model semantics with graph structure

---

## Part 2: World Model - Graph-Based vs Document-Based

### 2.1 The Key Design Difference

**Document-based (RAG):**
```
Query → Vector search → Retrieved passages → Concatenate to prompt → Model reconstructs structure
```

**Graph-based (OCTO):**
```
Query → Vector search → Retrieve typed nodes → Hydrate with relations → Apply rules → Emit structured state
```

### 2.2 WorldModel Internals

`WorldModel` (in `/Users/richiek/work/bender/src/octo/world_state.py`) stores structured knowledge:

```python
@dataclass
class WorldModel:
 domain: str # Domain name (e.g., "bird-dev", "spider")
 nodes: Dict[str, dict] # node_id → {label, type, summary, keywords, data_type, ...}
 edges: List[Tuple[str, str, str, dict]] # (src, relation_type, dst, attributes)
 use_ann: bool # Enable ANN-based retrieval (FAISS)
 
 # Internal caches (lazy-loaded)
 _index: Optional[InMemoryGraphIndex] # Default: heuristic keyword matching
 _ann_index: Optional[FaissIndex] # Optional: semantic similarity search
 _encoder: Optional[STEncoder] # Sentence-transformer for embeddings
```

### 2.3 Typed Nodes and Relations

Example from BIRD benchmark:

```
Nodes:
 "db:california_schools.schools"
 → {type: "table", label: "schools", summary: "K-12 school records"}
 "db:california_schools.schools.id"
 → {type: "column", label: "id", data_type: "INTEGER"}
 "db:california_schools.schools.name"
 → {type: "column", label: "name", data_type: "VARCHAR"}

Edges:
 ("db:california_schools.schools", "has_column", "db:california_schools.schools.id")
 ("db:california_schools.schools", "has_column", "db:california_schools.schools.name")
 ("db:california_schools.schools", "foreign_key", "db:california_schools.districts")
```

**Critical point:** The structure is **not serialized into text**. It's kept as typed nodes and relations. This allows:

1. **Constraint application** without model parsing (rules know about foreign keys structurally)
2. **Relation intersection** (e.g., "find birds that live in Antarctica AND eat fish")
3. **Semantic role discovery** (the RuleEngine tags nodes as ROLE_GEOGRAPHIC, ROLE_METRIC, etc.)

### 2.4 Retrieval: Multiple Indexing Strategies

OCTO supports two retrieval modes:

#### InMemoryGraphIndex (Default, Fast, Offline)
Located in `/Users/richiek/work/bender/src/octo/retrieval/legacy.py`:
- Keyword matching on node text
- Deterministic, no dependencies
- Works offline
- Sufficient for structured schema matching

#### FAISS Index (ANN, High-Dimensional)
Located in `/Users/richiek/work/bender/src/octo/retrieval/ann.py`:
- Semantic similarity via SentenceTransformers
- Query embedding → top-k nearest neighbors
- Optional: HashedTokenEncoder (deterministic fallback)
- Better for natural language queries

**Trade-off decision:**
- OCTO defaults to lightweight retrieval (InMemoryGraphIndex)
- ANN is optional (enable with `world_model.use_ann = True`)
- Future: Plan migration to FAISS for production, but intentionally defer

### 2.5 Graph Signal vs Token Signal

`WorldModel.graph_signal()` converts retrieved memories to a latent vector:

```python
def graph_signal(self, retrievals: Sequence[RetrievedMemory], width: int = 8) -> Vector:
 # For each retrieved node, encode its text to a vector
 weighted = [0.0] * actual_width
 normalizer = 0.0
 
 for item in retrievals:
 if item.node_id not in self.nodes:
 continue
 
 # Get the node's text representation
 text = self.embedding_text(item.node_id) # label + summary + keywords
 vector = self._encoder.encode([text])[0] # or embed_text for lightweight
 
 # Weight by retrieval score (confidence)
 normalizer += item.score
 for i, value in enumerate(vector):
 weighted[i] += float(value) * item.score
 
 # Normalize to unit vector
 return tuple(value / normalizer for value in weighted)
```

**Key insight:** The graph signal is **aggregated retrieval**, not raw graph data. It's a dense vector that encodes "what entities were retrieved" into a latent form that can be mixed with the token signal.

---

## Part 3: FTI MLOps Architecture

### 3.1 Why FTI for OCTO?

OCTO adopts the **Feature/Training/Inference (FTI)** MLOps pattern, a SOTA architecture from Hopsworks.

**Traditional ML pipeline:**
```
Raw data → Feature engineering → Train → Deploy → Serve
 ↑
 Rebuilds every run (wasteful)
```

**FTI pattern:**
```
Raw data → Feature pipeline (build once, version, publish) → Load in inference
 ↑ ↓
 Pre-built Point-in-time consistency
 Reproducible 3x faster iteration
 Versioned
```

**OCTO's adaptation:**
```
Domain data → WorldModel pipeline → WorldModelStore (versioned, gzipped)
 (build_bird_world_model) ↓
 OctoRuntime.infer()
 (load + retrieve → plan → fuse)
```

### 3.2 WorldModelStore Implementation

`WorldModelStore` (in `/Users/richiek/work/bender/src/octo/world_model_store.py`) is the FTI Feature Pipeline:

```python
class WorldModelStore:
 """
 Structure:
 store_path/
 {source}/
 {version}/
 manifest.json
 {db_id}.json.gz
 """
 
 def save(world_model, source="bird-dev", version="v1.0.0", 
 model_id="california_schools", metadata={}) → None
 # Serialize to JSON, optionally gzip (70% compression)
 # Update manifest (build_date, num_nodes, num_edges, metadata)
 
 def load(source, version, model_id) → WorldModel
 # Lazy load: decompress and deserialize only when needed
 
 def get_or_build(builder, source, version, model_id, **builder_kwargs) → WorldModel
 # If exists: load
 # If not: call builder(), save(), return
 # Enables caching without explicit versioning
 
 def list_versions(source) → List[str]
 def list_models(source, version) → List[str]
 def get_manifest(source, version) → WorldModelManifest
```

### 3.3 Benefits Realized

**Reproducible Research ✅**
- Version-lock world models (e.g., `bird-dev:v1.0.0`)
- Manifest tracks build date, number of nodes/edges
- Re-run experiments with **exact same world model**

**Performance (3x Speedup Expected) 🚀**
- BIRD dev: 15 min for 50 tasks (most time spent rebuilding)
- Expected: 5 min for 50 tasks (zero rebuild time)
- Pre-built models load in milliseconds

**Collaboration ✅**
- Share pre-built world models across teams
- Semantic versioning (v1.0.0 = "stable schema", v2.0.0 = "new columns")
- Easy distribution (gzip-compressed JSON files)

**Development Velocity ✅**
- Iteration: change query logic without rebuilding world models
- `get_or_build()` with caching prevents accidental rebuilds
- Clear separation: "build once, use forever"

**Production Readiness ✅**
- Adopts SOTA MLOps pattern (not "vibe coding")
- Manifest + versioning = auditability
- S3 support ready to add (just swap storage backend)

### 3.4 No Training Pipeline (Intentional)

OCTO **does not have a training pipeline**. This is architectural purity, not a limitation:

- Domain logic lives in **graphs**, not model weights
- OCTO is model-agnostic (works with Claude, Gemma, Qwen, custom)
- No fine-tuning = no overfitting to specific training data
- Rules and simulation are deterministic and explainable

This contrasts with approaches that add a separate fine-tuned model for each domain.

---

## Part 4: Fusion Module - Blending Signals

### 4.1 The Fusion Problem

OCTO runs **two parallel inference paths:**

1. **Token-side (LLM signal)**
 - The model's latent understanding of the query
 - Continuous vector from text embedding or hidden state
 - Semantic but potentially noisy

2. **Graph-side (Domain signal)**
 - Structured world model entities
 - Aggregated into a latent vector
 - Precise but potentially brittle

**Challenge:** How to combine them without either:
- Drowning graph signal in model noise
- Losing model semantic knowledge?

### 4.2 WeightedBlendFusion Strategy

`WeightedBlendFusion.mix()` (in `/Users/richiek/work/bender/src/octo/fusion.py`):

```python
def mix(token_signal, graph_signal, state: CognitiveState) -> FusedSignal:
 # Step 1: Compute retrieval strength
 retrieval_strength = sum(item.score for item in state.retrievals) / max(len(state.retrievals), 1)
 # Average confidence of retrieved entities (0.0 to 1.0)
 
 # Step 2: Apply reasoning bonuses
 hypothesis_bonus = 0.05 * len(state.hypotheses) # +0.05 per hypothesis
 constraint_bonus = 0.03 * len(state.constraints) # +0.03 per constraint
 
 # Step 3: Compute weights (bounded between 0.15 and 0.85)
 graph_weight = min(0.85, max(0.15, retrieval_strength + hypothesis_bonus + constraint_bonus))
 token_weight = max(0.15, 1.0 - graph_weight)
 
 # Normalize (weights must sum to 1.0)
 total = token_weight + graph_weight
 token_weight /= total
 graph_weight /= total
 
 # Step 4: Linear blend (element-wise weighted sum)
 fused = tuple(
 token_weight * token_value + graph_weight * graph_value
 for token_value, graph_value in zip(token, graph)
 )
 
 return FusedSignal(
 mixer="WeightedBlendFusion",
 token_weight=token_weight, # e.g., 0.35
 graph_weight=graph_weight, # e.g., 0.65
 vector=fused,
 rationale="Graph weight rises with retrieved support and reasoning state; token weight preserves base-model semantic trajectory."
 )
```

### 4.3 Weight Dynamics

**Example scenario 1: High-confidence retrieval**
```
retrieval_strength = 0.9 (3 entities retrieved with high scores)
hypotheses = 2 (hypothesis_bonus = 0.10)
constraints = 1 (constraint_bonus = 0.03)

graph_weight = min(0.85, max(0.15, 0.9 + 0.10 + 0.03))
 = min(0.85, max(0.15, 1.03))
 = min(0.85, 1.03)
 = 0.85 ← Graph signal dominates

token_weight = max(0.15, 1.0 - 0.85) = max(0.15, 0.15) = 0.15 ← Token signal preserved as fallback
```

**Example scenario 2: No retrieval**
```
retrieval_strength = 0.0
hypotheses = 0
constraints = 0

graph_weight = min(0.85, max(0.15, 0.0)) = 0.15 ← Minimal graph influence
token_weight = max(0.15, 1.0 - 0.15) = 0.85 ← Model signal takes over
```

### 4.4 Architectural Insights

**Why not simple averaging?**
- Simple 0.5/0.5 split would wash out weak graph signals with strong LLM semantics
- Scoring distractors equally would dilute valid matches

**Why minimum 0.15 for each?**
- Prevents complete domination by one signal
- Maintains hybrid reasoning even in extreme cases
- Token signal is always "in the loop" (cannot be muted)

**Why linearly blend?**
- Non-linear blending (e.g., attention) requires learned weights
- Linear blend is interpretable and deterministic
- Weights are explicit in the output (no hidden dynamics)

**Is this the only fusion strategy?**
- No. `FusionModule` is an abstract base class
- Future strategies: gating mechanisms, cross-attention, attention-weighted blend
- Current strategy is simple because Phase 1 focuses on architectural clarity

---

## Part 5: Model Integration - Two Paths

### 5.1 Integration Architecture

OCTO decouples domain reasoning from model coupling through `ModelIntegration`:

```python
class ModelIntegration(ABC):
 @abstractmethod
 def capture(query, mode, hidden_state, decode_step, width) → SemanticFrame:
 # Model-specific: extract semantic state from query + hidden state
 
 @abstractmethod
 def inject(frame, state, fused) → ControlPacket:
 # Model-specific: format OCTO output for downstream consumption
```

### 5.2 BlackBoxIntegration (Weak Mode)

For API-only or closed-weight models:

```python
class BlackBoxIntegration(ModelIntegration):
 name = "black_box"
 
 def capture(query, mode, hidden_state, **kwargs) → SemanticFrame:
 # Ignore hidden_state (not available in black-box models)
 return SemanticFrame(
 query=query,
 semantic_query=query,
 text_embedding=embed_text(query, width=width), # Text embedding only
 hidden_state=None, # No hidden state access
 token_window=tokenize(query),
 )
 
 def inject(frame, state, fused) → ControlPacket:
 # Format for prompt-side consumption
 hints = [
 "Focus on retrieved entities: ...",
 "Respect structured constraints: ...",
 "Prioritize coprocessor hypotheses: ...",
 ]
 return ControlPacket(
 integration="black_box",
 prompt_hints=hints, # → Prepended to prompt
 active_entities=state.active_entity_labels(), # → Entity list
 hypotheses=state.hypothesis_texts(), # → Hypothesis list
 constraints=state.constraints, # → Structured dict
 fused_vector=fused.vector, # → Latent signal
 provenance=state.provenance,
 metadata={"adapter_action": "structured_control_context"}
 )
```

**Consumption model:**
- Packet is serialized into prompt (e.g., "Active entities: [schools, districts]")
- Model reads hints and decides how to use them
- This is still better than RAG because OCTO has already applied rules and constraints

### 5.3 NativeIntegration (Strong Mode)

For open-weight models with access to hidden states:

```python
class NativeIntegration(ModelIntegration):
 name = "native_hidden_state"
 
 def capture(query, mode, hidden_state, width, **kwargs) → SemanticFrame:
 # Both text embedding AND model hidden state
 return SemanticFrame(
 query=query,
 text_embedding=embed_text(query, width=width),
 hidden_state=coerce_vector(hidden_state, width=width) if hidden_state else text_embedding,
 token_window=tokenize(query),
 )
 
 def inject(frame, state, fused) → ControlPacket:
 # Format for inference-server integration
 return ControlPacket(
 integration="native_hidden_state",
 prompt_hints=[
 "Apply fused world-model delta to the model-side adapter or cross-attention hook.",
 "Preserve base-model decoding while biasing toward structured state.",
 ],
 active_entities=state.active_entity_labels(),
 hypotheses=state.hypothesis_texts(),
 constraints=state.constraints,
 fused_vector=fused.vector, # → Inject into hidden state path
 metadata={
 "adapter_action": "hidden_state_delta",
 "hidden_state_present": frame.hidden_state is not None,
 "decode_step": frame.decode_step, # Token-time information
 }
 )
```

**Consumption model:**
- Packet is injected into the inference server's request context
- Server inserts fused vector into model's forward pass
- Happens at token-generation time (not post-hoc)
- This is the architectural goal: true coprocessor integration

### 5.4 Why Separate Paths?

**Black-box path:**
- Works with any model (Claude, GPT, Gemini via API)
- Produces structured output, but consumption is prompt-side
- Slower iteration: model still interprets text hints
- This is Levels 0-1 integration (weak mode)

**Native path:**
- Requires inference-server support (e.g., ScalarLM)
- Produces latent signals that bypass prompts
- Token-time influence: direct hidden-state injection
- This is Level 2 integration (strong mode, architectural goal)

**Both paths use the same runtime**
- Domain reasoning is identical
- Only the capture/inject boundaries differ
- Enables gradual migration from black-box to native

---

## Part 6: Domain Reasoning Layers

### 6.1 Planner: Query Intent Detection

`Planner.plan()` (in `/Users/richiek/work/bender/src/octo/planner.py`) extracts query structure:

```python
def plan(query: str, state: CognitiveState) → CognitiveState:
 lowered = query.lower()
 
 # 1. Identify DB/Schema from retrievals
 for item in state.retrievals:
 if "." in item.node_id:
 db_id = item.node_id.split(".")[0] # "db:california_schools.schools" → "california_schools"
 state.constraints["db_id"] = db_id.upper()
 break
 
 # 2. Detect query intent (pattern matching on keywords)
 if any(token in lowered for token in ("quantile", "equal groups", "decile")):
 state.constraints["query_intent"] = "window_quantile"
 state.constraints["window_function"] = "NTILE"
 elif any(token in lowered for token in ("consecutive", "increase in", "growth")):
 state.constraints["query_intent"] = "growth_analysis"
 state.constraints["sql_pattern"] = "self_join_on_month"
 elif any(token in lowered for token in ("proportion", "share", "ratio")):
 state.constraints["query_intent"] = "share_of_total"
 state.constraints["requires_global_denominator"] = True
 # ... more patterns
 
 # 3. Extract structural hints
 if "each" in lowered or "per " in lowered or "by " in lowered:
 state.constraints["group_by_hint"] = True
 
 if "year" in lowered or "202" in lowered:
 state.constraints["temporal_filter"] = True
 
 # 4. Regex for numeric ranges
 range_match = re.search(r"between\s+(\d+)\s+and\s+(\d+)", lowered)
 if range_match:
 state.constraints["numeric_range"] = (int(range_match.group(1)), int(range_match.group(2)))
 
 # 5. Populate planner state for tracing
 state.planner_state["analytic_plan"] = [
 {"action": "resolve_concept", "concept": "primary_subject"},
 {"action": "apply_pattern", "pattern": "pattern:window_quantile"},
 {"action": "validate_schema", "requirement": "column_types"},
 ]
 
 return state
```

**Key insight:** Planner is **deterministic keyword matching**, not ML. This means:
- Results are reproducible
- Easy to debug ("why did it tag this as window_quantile?")
- Can be extended without retraining

### 6.2 RuleEngine: Semantic Role Discovery

`RuleEngine.apply()` (in `/Users/richiek/work/bender/src/octo/rules.py`) assigns meaning to entities:

```python
def apply(state: CognitiveState) → CognitiveState:
 labels = {entity.label.lower() for entity in state.entities}
 db_id = state.constraints.get("db_id", "").upper()
 
 # 1. Semantic role discovery (entity classification)
 for entity in state.entities:
 label = entity.label.lower()
 if any(token in label for token in ["state", "province", "region", "city"]):
 entity.attributes["semantic_role"] = "ROLE_GEOGRAPHIC"
 elif any(token in label for token in ["year", "month", "date"]):
 entity.attributes["semantic_role"] = "ROLE_TEMPORAL"
 elif any(token in label for token in ["count", "price", "amount", "number"]):
 entity.attributes["semantic_role"] = "ROLE_METRIC"
 
 # 2. Generic SQL pattern rules
 if state.constraints.get("requires_global_denominator"):
 state.hypotheses.append(
 Hypothesis(
 text=f"Proportion queries in {db_id} require a 'share of total' pattern.",
 confidence=0.98,
 evidence=["rule:global_proportion", f"db:{db_id}"],
 kind="sql_pattern"
 )
 )
 state.constraints["sql_template"] = "proportion_join"
 
 # 3. DB-specific domain rules
 if db_id == "CHICAGO":
 if any("duration" in l for l in labels) and any("quantile" in l for l in labels):
 state.constraints["query_intent"] = "window_quantile"
 state.constraints["window_function"] = "NTILE"
 
 # 4. Toy domain rules (relation intersection)
 if "penguin" in labels and ("penguin", "cannot", "fly") in [(r.source, r.relation, r.target) for r in state.relations]:
 state.constraints["mobility_exception"] = "penguin_cannot_fly"
 state.hypotheses.append(
 Hypothesis(
 text="Penguins are birds, but this query hits an explicit exception: penguins cannot fly.",
 confidence=0.99,
 kind="rule_exception",
 )
 )
 
 return state
```

**Architectural pattern:**
- Rules operate on **typed entities and relations**, not text
- Semantic roles (GEOGRAPHIC, METRIC, etc.) guide downstream reasoning
- Domain-specific rules (e.g., CHICAGO-specific patterns) are explicit and auditable
- Hypotheses are explicit with confidence scores

### 6.3 Simulator: Structural Validation

`Simulator.run()` (in `/Users/richiek/work/bender/src/octo/simulator.py`) tests query feasibility:

```python
def run(state: CognitiveState) → CognitiveState:
 if not state.retrievals:
 state.simulation_state["status"] = "skipped"
 return state
 
 simulation_checks = []
 confidence_score = 1.0
 
 # 1. Validate join path (self-join on month)
 if state.constraints.get("sql_pattern") == "self_join_on_month":
 has_date = any("month" in item.label.lower() or "date" in item.label.lower() 
 for item in state.retrievals)
 if not has_date:
 simulation_checks.append("Self-join on month proposed but no date column found.")
 confidence_score *= 0.5
 else:
 simulation_checks.append("Self-join on month appears structurally valid.")
 
 # 2. Validate proportion join integrity
 if state.constraints.get("sql_template") == "proportion_join":
 has_metric = any("number" in item.label.lower() or "count" in item.label.lower() 
 for item in state.retrievals)
 has_key = any("name" in item.label.lower() for item in state.retrievals)
 if not (has_metric and has_key):
 simulation_checks.append("Proportion join missing metric or grouping key.")
 confidence_score *= 0.4
 
 # 3. Validate aggregation targets
 if state.constraints.get("aggregation_required"):
 has_numeric = any(item.attributes.get("data_type", "").upper() in ["NUMBER", "INTEGER"] 
 for item in state.retrievals)
 if not has_numeric:
 simulation_checks.append("Query requires aggregation but no numeric columns found.")
 confidence_score *= 0.7
 
 state.simulation_state["status"] = "completed"
 state.simulation_state["checks"] = simulation_checks
 state.simulation_state["structural_confidence"] = confidence_score
 
 return state
```

**Purpose:** Before the model generates SQL, OCTO validates that the retrieved schema supports the planned query pattern. This catches structural issues early.

---

## Part 7: Integration Levels - The Architectural Spectrum

OCTO defines three integration levels (see `/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md`):

### 7.1 Level 0: Retrieval Only (Not OCTO)

```
Query → Vector search → Retrieved passages → Concatenate → Prompt
```

Examples: Langchain RAG, basic vector DBs

**Why it's not OCTO:**
- Model reconstructs structure from text alone
- No explicit constraints or hypotheses
- No provenance preservation
- No fusion between model semantics and domain knowledge

### 7.2 Level 1: Structured Control Mode (Weak Mode, Available Today)

```
Query → Retrieve + Plan + Reason → ControlPacket (entities, constraints, hypotheses) → Append to prompt
```

**What OCTO produces:**
- Deduplicated entities (not raw passages)
- Explicit constraints (db_id, query_intent, sql_pattern)
- Typed hypotheses with confidence scores
- Semantic roles (GEOGRAPHIC, METRIC, TEMPORAL)
- Complete provenance trail

**How it's consumed:**
- ControlPacket serialized into prompt context
- Model reads structured guidance
- Model still generates output (OCTO doesn't replace generation)

**Why this is better than RAG:**
- OCTO has already extracted structure (model doesn't have to)
- OCTO has already applied domain rules (model doesn't have to)
- OCTO preserves provenance (auditable reasoning)
- OCTO emits constraints (not just suggestions)

**Current status:** Fully implemented, works with any model via prompt

### 7.3 Level 2: Native Coprocessor Mode (Strong Mode, Requires Backend)

```
Query → Retrieve + Plan + Reason → FusedSignal (latent vector) → Inject into hidden-state path → Token-time generation
```

**What changes:**
- OCTO doesn't produce prompt hints—produces latent vectors
- Vectors injected into model's forward pass (e.g., cross-attention, adapter layer)
- Influence happens at generation time (not post-hoc)
- No prompting overhead (purely inference-server integration)

**Requirements:**
- Inference server must support request-scoped context propagation
- Model must expose hidden-state or adapter hooks
- Example backend: ScalarLM (fork in `/rschiavi/octo`)

**Why this is the architectural goal:**
- True parallel reasoning: OCTO and model operate simultaneously
- Token-time influence: can guide generation at every step
- Clean separation: OCTO doesn't know about prompts
- Scalable: no prompt engineering, purely structural reasoning

**Current status:** Contract defined (`NativeIntegration`), backend prototype exists

---

## Part 8: Architectural Decisions and Trade-Offs

### 8.1 Graph-Based vs Document-Based

**Decision: Graph-Based (Nodes + Relations)**

**Rationale:**
- Domain structure (schemas, categories) is inherently relational
- Typed nodes enable semantic role discovery (GEOGRAPHIC, METRIC)
- Relations enable constraint application (foreign keys)
- Relation intersection enables complex queries (birds in Antarctica eating fish)

**Trade-off:**
- ✅ More expressive reasoning
- ✅ Auditable rules
- ❌ Requires domain modeling effort
- ❌ Less flexible for free-form text

### 8.2 Lightweight Retrieval vs FAISS

**Decision: Default to lightweight, make FAISS optional**

**Rationale:**
- Heuristic keyword matching (InMemoryGraphIndex) works well for structured schemas
- FAISS adds dependency complexity and memory overhead
- Can migrate to FAISS later when performance demands warrant it
- Phase 1 focuses on architecture, not optimization

**Current status:**
- Default: `use_ann=False` (InMemoryGraphIndex)
- Opt-in: `use_ann=True` (FAISS + SentenceTransformers)
- Future: Plan production migration to FAISS/HNSW

### 8.3 Linear Fusion vs Learned Attention

**Decision: Linear weighted blend**

**Rationale:**
- Interpretable: weights explicit in output
- Deterministic: no learned parameters
- Auditable: clear why graph/token weight changed
- Future-proof: attention can be added later as alternative

**Trade-off:**
- ✅ Debuggable
- ❌ Less expressive than attention
- ❌ Cannot learn complex interaction patterns

### 8.4 Versioned Models vs On-Demand Building

**Decision: FTI Pattern (Build Once, Version, Load)**

**Rationale:**
- Reproducible research (version-lock results)
- 3x faster iteration (no rebuild on every run)
- SOTA MLOps pattern (production-ready infrastructure)
- Clear separation of concerns (build vs reasoning)

**Trade-off:**
- ✅ Reproducible
- ✅ Fast
- ✅ Auditable
- ❌ Extra step to rebuild models
- ❌ Manifest management overhead

### 8.5 Model-Agnostic Domain Logic

**Decision: Rules and simulation in graphs, not model weights**

**Rationale:**
- No fine-tuning required (faster deployment)
- No model-specific constraints (OCTO works across base models)
- Easier to update (change rules, not retrain)
- Explainable (rules are code, not weights)

**Trade-off:**
- ✅ Flexible
- ✅ Explainable
- ❌ Cannot learn domain nuances
- ❌ Requires manual rule engineering

### 8.6 Two Integration Paths (Black-box + Native)

**Decision: Support both, recommend native for production**

**Rationale:**
- Weak mode unblocks experimentation today (works with Claude, GPT, Gemini)
- Strong mode enables architectural goal (true coprocessor)
- Gradual migration path (start weak, move to native)
- Meets models where they are (API vs open-source)

**Trade-off:**
- ✅ Flexible entry point
- ✅ Long-term vision clear
- ❌ More code to maintain
- ❌ Native mode requires backend work

---

## Part 9: Architectural Purity and Boundaries

### 9.1 The Boundary Rule

```
src/octo/ → Pure framework (no domain-specific logic)
implementations/ → Domain-specific implementations
examples/ → Demo entrypoints
```

**Rule:** `octo` must NOT import from `implementations`

**Why:**
- Keeps framework generic and reusable
- Shows third parties how to build on top of framework
- Prevents feature creep (domain logic stays out of core)
- Makes core auditable (small, focused codebase)

### 9.2 What Lives in Core

**Must be in `src/octo/`:**
- Runtime orchestration (OctoRuntime)
- Integration contracts (ModelIntegration)
- World model storage (WorldModel, WorldModelStore)
- Retrieval abstraction (InMemoryGraphIndex, FAISS)
- Fusion logic (FusionModule)
- Model data structures (SemanticFrame, CognitiveState, ControlPacket)

**Must NOT be in core:**
- Domain-specific rules (lives in implementations)
- Benchmark-specific harnesses (lives in examples)
- SQL generation logic (lives in implementations/bird)
- Schema introspection (lives in implementations/bird)

### 9.3 Extension Points (Where to Customize)

**Swap retrieval backend:**
```python
class MyCustomIndex:
 def search(query, top_k):
 # Your ANN implementation here
 pass

world_model._index = MyCustomIndex()
```

**Swap fusion strategy:**
```python
class AttentionFusion(FusionModule):
 def mix(token_signal, graph_signal, state):
 # Learned attention weights
 pass

runtime = OctoRuntime(world_model, fusion=AttentionFusion())
```

**Add domain-specific rules:**
```python
class MyDomainRules(RuleEngine):
 def apply(state):
 # Call super().apply(state)
 # Add my custom rules
 return state

runtime = OctoRuntime(world_model, rules=MyDomainRules())
```

**Add new integration backend:**
```python
class QuantumVLLMIntegration(ModelIntegration):
 def capture(query, hidden_state, decode_step, width):
 # Quantum-specific state capture
 pass
 
 def inject(frame, state, fused):
 # Quantum-specific output format
 pass

runtime = OctoRuntime(world_model, integration=QuantumVLLMIntegration())
```

---

## Part 10: Provenance and Auditability

### 10.1 Provenance by Design

Every stage of the pipeline adds provenance:

```python
state.add_provenance(
 stage="capture",
 reference="integration:black_box",
 detail="Captured a semantic frame from the model-side query state.",
 confidence=1.0
)

state.add_provenance(
 stage="retrieval",
 reference="retrieval:db_id",
 detail=f"Retrieved {label} from the world model.",
 confidence=retrieval.score
)

state.add_provenance(
 stage="rules",
 reference="rule:penguin_exception_override",
 detail="Applied the explicit penguin flight exception...",
 confidence=0.99
)

state.add_provenance(
 stage="fusion",
 reference="fusion:WeightedBlendFusion",
 detail="Mixed model-side state with graph-side state.",
 confidence=state.fused_signal.graph_weight
)
```

### 10.2 Auditability Benefits

**Why this matters:**

1. **Debugging:** If OCTO produces wrong output, trace exactly which stage failed
2. **Compliance:** Financial/medical domains require reasoning audit trails
3. **Trust:** Users can verify OCTO's logic, not just its output
4. **Improvement:** See which rules fired and why
5. **Versioning:** Provenance becomes part of reproducible results

### 10.3 Provenance in ControlPacket

The control packet includes complete provenance:

```python
ControlPacket(
 provenance=[
 "integration:black_box",
 "retrieval:db_id",
 "retrieval:table_x",
 "planner:spider_schema",
 "rule:penguin_exception",
 "fusion:WeightedBlendFusion",
 "injection:structured_control_context",
 ]
)
```

Downstream systems can:
- Log provenance alongside generated output
- Trace unexpected behavior back to source
- Improve rules based on failure patterns

---

## Part 11: Phase 1 Limitations (Intentional)

The codebase explicitly documents limitations that are **intentional Phase 1 scope**, not missing prerequisites:

### 11.1 Retrieval is Heuristic

**Current:** InMemoryGraphIndex uses keyword matching 
**Future:** FAISS/HNSW for semantic similarity 
**Why Phase 1?** Keyword matching works for schemas; ANN adds complexity

### 11.2 Native Integration is Contract + Prototype

**Current:** `NativeIntegration` defines contract; ScalarLM branch has reference backend 
**Future:** Production backends for vLLM, TGI, etc. 
**Why Phase 1?** Focus on core runtime; backend work is parallelizable

### 11.3 Simulation is Heuristic

**Current:** Rule-based feasibility checks 
**Future:** Domain-specific simulators (SQL query planner, etc.) 
**Why Phase 1?** Domain simulators are highly specialized; core runtime is generic

### 11.4 Results Depend on Base Model Quality

**Finding:** OCTO + Claude = 20% → 26% (30% improvement) 
**Finding:** OCTO + Gemma3 = 0% (no improvement) 

**Insight:** OCTO doesn't fix broken base models. If the base model can't generate SQL, OCTO's structured guidance helps but doesn't solve generation. This is expected—OCTO is a coprocessor, not a replacement.

---

## Part 12: Key Takeaways

### 12.1 OCTO is NOT...

- ❌ Another RAG framework (no raw text retrieval)
- ❌ A fine-tuning system (no model weights)
- ❌ A replacement for LLMs (works alongside them)
- ❌ A magic bullet (requires good base models)
- ❌ Vaporware (real, runnable code)

### 12.2 OCTO IS...

- ✅ A structured reasoning layer
- ✅ A graph-based knowledge system
- ✅ A typed entity/relation store
- ✅ A provenance-preserving pipeline
- ✅ An integration contract for LLMs
- ✅ A coprocessor that runs parallel to inference
- ✅ Production-ready MLOps infrastructure (FTI pattern)

### 12.3 The Architectural Moat

OCTO's defensibility comes from:

1. **Graph reasoning (not document retrieval)**
 - Typed entities and relations
 - Constraint application
 - Relation intersection

2. **Explicit planning and rules (not prompt engineering)**
 - Deterministic query intent detection
 - Semantic role discovery
 - Domain-specific rule application

3. **Provenance and auditability (not black-box reasoning)**
 - Every reasoning step logged
 - Confidence scores attached
 - Full audit trail in output

4. **Reproducible research infrastructure (FTI pattern)**
 - Versioned world models
 - Manifest tracking
 - 3x faster iteration

5. **Two-path integration (black-box + native)**
 - Works today with any model (weak mode)
 - Supports true coprocessor future (strong mode)
 - Gradual migration path

### 12.4 The Intended Future

**Short term (Levels 0-1):**
- Structured control mode available for Claude, Gemini, local models
- Experiments with weak-mode integration
- BIRD/Spider benchmarks using prompt-side consumption

**Medium term (Level 2):**
- ScalarLM backend integration (reference native implementation)
- vLLM adapter for token-time injection
- Production-grade retrieval (FAISS/HNSW)

**Long term:**
- True coprocessor: OCTO and model run in lockstep
- Token-time influence: OCTO modulates generation at every step
- Specialization: OCTO handles domain reasoning, LLM handles language

---

## Conclusion

OCTO represents a **fundamental shift from retrieval-based augmentation to runtime-based reasoning**. Rather than asking models to infer structure from retrieved text, OCTO:

1. Explicitly models domain knowledge as **typed graphs**
2. Reasons over graphs using **deterministic planning and rules**
3. Fuses graph signals with model signals using **weighted blending**
4. Produces **structured control packets** for downstream consumption
5. Maintains **complete provenance** throughout the pipeline

The architecture is **modular, extensible, and production-ready**. It adopts SOTA MLOps patterns (FTI) while preserving architectural purity through explicit boundaries between framework and domain logic.

OCTO's success is measured not by replacing models, but by making models **more structured, more explainable, and more constrained** in specialized domains.

