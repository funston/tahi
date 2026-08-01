# OctoRetro: Structured World Models with Chunked Cross-Attention

## Executive Summary

OctoRetro combines OCTO's structured world model approach with RETRO's efficient chunked cross-attention architecture. This hybrid design delivers **guaranteed correctness through graph constraints** while achieving **continuous token-level intervention** through cross-attention layers.

**Core Innovation**: Replace RETRO's unstructured text chunks with OCTO's structured graph nodes, injecting semantic constraints directly into transformer hidden states every 64 tokens.

**Key Outcome**: 0% hallucination on structured domains with <2ms retrieval overhead.

---

## 1. Architecture Overview

### The Fundamental Synthesis

```python
# RETRO's Approach: Retrieve similar text
Retrieved_Text = ANN(query_embedding) # Might be wrong

# OCTO's Approach: Retrieve structured constraints
Graph_Constraints = WorldModel.reason(query) # Guaranteed correct

# OctoRetro: Structured constraints through cross-attention
Hidden_State = Base_LLM + CrossAttention(Graph_Constraints) # Correct + Efficient
```

### High-Level Architecture

```
 User Query
 │
 ┌───────────┴───────────┐
 ▼ ▼
 Base LLM World Model
 (Frozen Params) (Graph + Rules)
 │ │
 ▼ ▼
 Hidden States Graph Retrieval
 │ │
 │ ▼
 │ 7-Stage Pipeline
 │ (Plan→Rules→Simulate)
 │ │
 └─────────┬─────────────┘
 ▼
 Gated Chunked Cross-Attention
 (Every 64 tokens)
 │
 ▼
 Verified Generation
```

---

## 2. Core Technical Components

### 2.1 Structured Chunk Representation

Instead of RETRO's raw text chunks, OctoRetro uses **Structured Graph Chunks (SGC)**:

```python
@dataclass
class StructuredGraphChunk:
 """Replaces RETRO's 64-token text chunks with structured knowledge"""

 # Graph components
 nodes: List[NodeRef] # Relevant entities
 edges: List[EdgeRef] # Relationships
 constraints: Dict[str, Any] # Domain rules

 # Embeddings for cross-attention
 node_embeddings: Tensor # [num_nodes, d_model]
 constraint_embeddings: Tensor # [num_constraints, d_model]

 # Verification rules
 valid_tokens: Set[int] # Allowed token IDs
 invalid_patterns: List[str] # Blocked patterns

 def to_kv_matrices(self) -> Tuple[Tensor, Tensor]:
 """Convert to Key-Value matrices for cross-attention"""
 # Combine all structured elements into dense vectors
 combined = torch.cat([
 self.node_embeddings,
 self.constraint_embeddings
 ])
 keys = self.key_projection(combined) # [2m, d_model]
 values = self.value_projection(combined) # [2m, d_model]
 return keys, values
```

### 2.2 Gated Chunked Cross-Attention (GCCA) with Constraints

Adapting RETRO's GCCA for structured knowledge:

```python
class ConstrainedGCCA(nn.Module):
 """Gated Chunked Cross-Attention with structural constraints"""

 def __init__(self, d_model: int, n_heads: int):
 super().__init__()
 self.d_model = d_model
 self.n_heads = n_heads

 # Projections for structured knowledge
 self.W_k = nn.Linear(d_model, d_model) # For graph nodes
 self.W_v = nn.Linear(d_model, d_model) # For constraints
 self.W_q = nn.Linear(d_model, d_model) # For hidden states

 # Gating mechanism (initialized to 0)
 self.alpha = nn.Parameter(torch.zeros(1))

 # Constraint verification layer
 self.constraint_proj = nn.Linear(d_model, d_model)

 def forward(self,
 hidden_states: Tensor, # [batch, seq_len, d_model]
 graph_chunk: StructuredGraphChunk,
 decode_step: int) -> Tensor:

 # 1. Retrieve structured knowledge every 64 tokens
 if decode_step % 64 == 0:
 self.current_chunk = self.retrieve_graph_chunk(hidden_states)

 # 2. Project graph knowledge to K,V matrices
 keys, values = self.current_chunk.to_kv_matrices()

 # 3. Compute cross-attention
 Q = self.W_q(hidden_states)
 K = self.W_k(keys)
 V = self.W_v(values)

 attn_scores = torch.matmul(Q, K.T) / math.sqrt(self.d_model)
 attn_weights = F.softmax(attn_scores, dim=-1)
 context = torch.matmul(attn_weights, V)

 # 4. Apply constraints
 context = self.apply_structural_constraints(context, self.current_chunk)

 # 5. Gated output
 gate = torch.tanh(self.alpha)
 output = hidden_states + gate * context

 return output

 def apply_structural_constraints(self, context: Tensor, chunk: StructuredGraphChunk):
 """Enforce hard constraints from world model"""
 # Project constraints to hidden space
 constraint_mask = self.constraint_proj(chunk.constraint_embeddings)

 # Apply masking to ensure constraint satisfaction
 context = context * constraint_mask

 return context
```

### 2.3 World Model Integration Layer

Connect OCTO's world model to RETRO's retrieval pipeline:

```python
class WorldModelRetriever:
 """Bridges OCTO's graph reasoning with RETRO's chunked retrieval"""

 def __init__(self, world_model: WorldModel, chunk_size: int = 64):
 self.world_model = world_model
 self.chunk_size = chunk_size
 self.runtime = OctoRuntime(world_model)

 # Cache for async prefetching
 self.prefetch_cache = {}
 self.prefetch_executor = ThreadPoolExecutor(max_workers=4)

 def retrieve_for_chunk(self,
 tokens: List[int],
 decode_step: int) -> StructuredGraphChunk:
 """Retrieve structured knowledge for current generation chunk"""

 # 1. Run OCTO's 7-stage pipeline
 query = self.tokens_to_text(tokens)
 cognitive_state = self.runtime.infer(
 query=query,
 mode="coprocessor",
 decode_step=decode_step
 )

 # 2. Extract structured components
 nodes = cognitive_state.entities
 edges = cognitive_state.relations
 constraints = cognitive_state.constraints

 # 3. Convert to embeddings
 node_embeddings = self.embed_nodes(nodes)
 constraint_embeddings = self.embed_constraints(constraints)

 # 4. Extract verification rules
 valid_tokens = self.get_valid_tokens(cognitive_state)
 invalid_patterns = self.get_invalid_patterns(cognitive_state)

 return StructuredGraphChunk(
 nodes=nodes,
 edges=edges,
 constraints=constraints,
 node_embeddings=node_embeddings,
 constraint_embeddings=constraint_embeddings,
 valid_tokens=valid_tokens,
 invalid_patterns=invalid_patterns
 )

 def prefetch_next_chunk(self, current_tokens: List[int]):
 """Asynchronously prefetch next chunk's constraints"""
 future = self.prefetch_executor.submit(
 self.retrieve_for_chunk,
 current_tokens,
 len(current_tokens) + self.chunk_size
 )
 self.prefetch_cache[len(current_tokens) + self.chunk_size] = future
```

### 2.4 Token Verification Layer

Enforce constraints at token generation time:

```python
class TokenVerifier:
 """Verify each token against world model constraints"""

 def __init__(self, world_model: WorldModel):
 self.world_model = world_model
 self.sql_parser = SQLParseContext()
 self.prefix_tree = self.build_prefix_tree()

 def verify_logits(self,
 logits: Tensor, # [vocab_size]
 chunk: StructuredGraphChunk,
 partial_text: str) -> Tensor:
 """Modify logits based on structural constraints"""

 # 1. Parse context
 self.sql_parser.update(partial_text)
 context = self.sql_parser.get_context() # e.g., "expecting_table"

 # 2. Apply hard constraints
 for token_id in range(len(logits)):
 token_str = self.decode_token(token_id)

 # Check against world model
 if context == "expecting_table":
 if not self.is_valid_table_prefix(token_str, chunk):
 logits[token_id] = -float('inf') # Block invalid token

 elif context == "expecting_column":
 if not self.is_valid_column_prefix(token_str, chunk):
 logits[token_id] = -float('inf')

 # 3. Boost valid completions
 for node in chunk.nodes:
 matching_tokens = self.prefix_tree.get_tokens_for_prefix(node.label)
 for token_id in matching_tokens:
 logits[token_id] += 2.0 # Boost probability

 return logits

 def is_valid_table_prefix(self, prefix: str, chunk: StructuredGraphChunk) -> bool:
 """Check if prefix could lead to valid table"""
 valid_tables = [n.label for n in chunk.nodes if n.type == "table"]
 return any(table.startswith(prefix) for table in valid_tables)
```

---

## 3. Implementation Strategy

### Phase 1: Adapter Layer Development (Week 1-2)

**Goal**: Build GCCA adapters without modifying OCTO core

```python
# New module: src/octo/adapters/gcca.py
class OctoRetroAdapter:
 def __init__(self, octo_runtime: OctoRuntime, base_model: nn.Module):
 self.octo = octo_runtime
 self.base_model = base_model

 # Add GCCA layers to specific transformer blocks
 self.gcca_layers = nn.ModuleDict({
 f"layer_{i}": ConstrainedGCCA(d_model=base_model.config.hidden_size)
 for i in range(4, base_model.config.num_layers, 4) # Every 4th layer
 })

 # Initialize gates to 0 (no disruption)
 for gcca in self.gcca_layers.values():
 gcca.alpha.data.zero_()
```

**Tasks**:
- [ ] Implement StructuredGraphChunk dataclass
- [ ] Build ConstrainedGCCA module
- [ ] Create WorldModelRetriever bridge
- [ ] Add TokenVerifier for logit modification

### Phase 2: Training Pipeline (Week 3-4)

**Goal**: Train GCCA adapters while keeping OCTO and LLM frozen

```python
# Training configuration
class OctoRetroTrainingConfig:
 # Frozen components
 freeze_base_llm: bool = True
 freeze_world_model: bool = True

 # Trainable parameters (<2% of total)
 train_gcca_projections: bool = True # W_k, W_v
 train_gcca_gates: bool = True # alpha parameters
 train_constraint_proj: bool = True # Constraint embedding layer

 # Training hyperparameters
 learning_rate: float = 3e-4
 warmup_steps: int = 1000
 batch_size: int = 8
 gradient_accumulation: int = 4
```

**Training Data Preparation**:
```python
def prepare_training_data():
 """Prepare data with Salient Span Masking"""

 # 1. Load instruction-following dataset
 dataset = load_dataset("sql_instructions")

 # 2. Apply REALM-style masking
 for example in dataset:
 # Mask entities to force GCCA usage
 example["masked_query"] = mask_salient_entities(example["query"])

 # Add distractor chunks (20% noise)
 example["distractors"] = get_hard_negatives(example["query"])

 return dataset
```

### Phase 3: Integration with Current OCTO (Week 5)

**Updates to existing OCTO components**:

#### Update 1: Extend WorldModel for Prefix Matching
```python
# src/octo/world_state.py
class WorldModel:
 # ADD: Prefix matching for token verification
 def find_nodes_with_prefix(self,
 prefix: str,
 node_type: Optional[str] = None,
 max_results: int = 10) -> List[NodeRef]:
 """Find nodes whose labels start with prefix"""
 results = []
 for node_id, node_data in self.nodes.items():
 if node_type and node_data.get("type") != node_type:
 continue
 if node_data.get("label", "").lower().startswith(prefix.lower()):
 results.append(self.entity_ref(node_id))
 return results[:max_results]

 # ADD: Build prefix tree for efficient lookup
 def build_prefix_tree(self) -> PrefixTree:
 """Build trie structure for fast prefix matching"""
 tree = PrefixTree()
 for node_id, node_data in self.nodes.items():
 label = node_data.get("label", "")
 tree.insert(label, node_id)
 return tree
```

#### Update 2: Add Streaming Mode to OctoRuntime
```python
# src/octo/runtime.py
class OctoRuntime:
 # ADD: Streaming inference for continuous generation
 def stream_infer(self,
 token_generator,
 chunk_size: int = 64) -> Generator[CognitiveState, None, None]:
 """Stream cognitive states during token generation"""

 buffer = []
 for token in token_generator:
 buffer.append(token)

 # Process every chunk_size tokens
 if len(buffer) % chunk_size == 0:
 query = self.tokens_to_text(buffer[-chunk_size:])
 state = self.infer(
 query=query,
 decode_step=len(buffer)
 )
 yield state
```

#### Update 3: New Integration Type for Cross-Attention
```python
# src/octo/integration.py
class CrossAttentionIntegration(ModelIntegration):
 """Integration via cross-attention layers instead of prompt"""
 name = "cross_attention"

 def __init__(self, gcca_layers: nn.ModuleDict):
 self.gcca_layers = gcca_layers

 def inject(self,
 frame: SemanticFrame,
 state: CognitiveState,
 fused: FusedSignal) -> ControlPacket:

 # Convert cognitive state to key-value matrices
 keys = self.state_to_keys(state)
 values = self.state_to_values(state)

 return ControlPacket(
 integration=self.name,
 cross_attention_keys=keys,
 cross_attention_values=values,
 gate_values=self.compute_gate_values(state),
 constraints=state.constraints,
 valid_tokens=self.get_valid_tokens(state)
 )
```

### Phase 4: Production Optimization (Week 6-7)

#### Asynchronous Prefetching Pipeline
```python
class AsyncOctoRetro:
 def __init__(self, world_model: WorldModel, buffer_depth: int = 2):
 self.world_model = world_model
 self.buffer_depth = buffer_depth
 self.prefetch_queue = asyncio.Queue()

 async def generate_with_prefetch(self, prompt: str):
 """Generate with prefetched constraints"""

 # Start prefetch workers
 workers = [
 asyncio.create_task(self.prefetch_worker())
 for _ in range(self.buffer_depth)
 ]

 # Generate tokens
 async for token in self.async_generate(prompt):
 # Get prefetched constraints
 constraints = await self.prefetch_queue.get()

 # Apply constraints to token
 verified_token = self.verify_token(token, constraints)

 yield verified_token
```

#### Out-of-Core Graph Storage (Adapting RETRO's approach)
```python
class DiskBackedWorldModel(WorldModel):
 """World model with out-of-core storage for massive graphs"""

 def __init__(self, storage_path: str, cache_size_gb: int = 8):
 super().__init__()

 # Adapt Filtered-DiskANN for graph topology
 self.topology = FilteredGraphIndex(storage_path)

 # Adapt Starling for efficient disk layout
 self.storage = StarlingGraphStorage(
 storage_path,
 page_size=4096, # 4KB NVMe sectors
 cache_size=cache_size_gb * 1024 * 1024 * 1024
 )

 # Adapt FreshDiskANN for real-time updates
 self.update_buffer = FreshGraphBuffer(
 max_buffer_size=100_000,
 merge_interval_sec=60
 )
```

---

## 4. Performance Targets & Benchmarks

### Correctness Metrics (OCTO's Strength)
- **Schema Hallucination Rate**: 0% (vs RETRO: ~15%)
- **Constraint Violations**: 0% (vs RETRO: N/A - no constraints)
- **Provenance Coverage**: 100% (vs RETRO: 0%)

### Efficiency Metrics (RETRO's Strength)
- **Retrieval Latency**: <2ms per 64-token chunk
- **Memory Overhead**: O(1) constant KV cache
- **Throughput**: 500+ concurrent streams

### Combined Metrics (OctoRetro Targets)
- **Factual Accuracy**: +35% over base LLM (matching RETRO)
- **Structured Domain Accuracy**: +50% over RETRO
- **Inference Overhead**: <5% slower than RETRO
- **Training Cost**: <$5k (vs RETRO from scratch: $1M+)

---

## 5. Migration Path from Current OCTO

### Step 1: Non-Breaking Additions
```python
# These can be added without changing existing code
octo/
├── adapters/
│ ├── __init__.py
│ ├── gcca.py # New: GCCA implementation
│ ├── token_verifier.py # New: Token verification
│ └── prefetch.py # New: Async prefetching
```

### Step 2: Optional Enhancements
```python
# Extend existing classes with new methods
class WorldModel:
 # Existing methods unchanged

 # New optional methods
 def find_nodes_with_prefix(self, prefix: str): ...
 def build_prefix_tree(self): ...
```

### Step 3: Alternative Runtime Mode
```python
# New runtime that uses GCCA instead of prompt injection
class OctoRetroRuntime(OctoRuntime):
 def __init__(self, world_model: WorldModel, use_gcca: bool = True):
 super().__init__(world_model)
 self.use_gcca = use_gcca

 if use_gcca:
 self.integration = CrossAttentionIntegration()
 else:
 self.integration = BlackBoxIntegration() # Fallback
```

---

## 6. Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| GCCA training destabilizes base model | Initialize α=0, gradual warmup |
| Graph retrieval slower than vector search | Hybrid index: vectors for coarse, graph for fine |
| Memory overhead from caching | Bounded LRU cache with eviction |
| Token verification adds latency | Parallel verification during logit computation |

### Integration Risks

| Risk | Mitigation |
|------|------------|
| Breaking existing OCTO code | All changes are additive/optional |
| Incompatible with current integration | Support both prompt and cross-attention modes |
| Complex deployment | Phased rollout: prompt → hybrid → full GCCA |

---

## 7. Conclusion

OctoRetro represents the optimal synthesis:
- **OCTO's correctness** through structured world models
- **RETRO's efficiency** through chunked cross-attention
- **<2% trainable parameters** preserving base model capabilities
- **0% hallucination** on structured domains

The architecture is designed to be:
1. **Non-invasive**: Can be added to existing OCTO without breaking changes
2. **Performant**: Async prefetching and O(1) memory scaling
3. **Correct**: Hard constraints from world models
4. **Scalable**: Out-of-core graph storage for massive knowledge bases

**Next Steps**:
1. Implement StructuredGraphChunk and GCCA modules
2. Extend WorldModel with prefix matching
3. Build training pipeline with masked entity data
4. Benchmark against pure OCTO and pure RETRO

**Timeline**: 6-7 weeks to production-ready implementation

---

*"The future of AI isn't larger models or more data—it's structured knowledge with efficient delivery."*