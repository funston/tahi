# SQL World Model POC Project Plan

## Current State Analysis

### What Already Exists ✅

1. **Core Infrastructure**
 - `WorldModel` class - generic graph structure for nodes/edges
 - `WorldModelStore` - FTI pattern for versioned world model storage
 - `OctoRuntime` - orchestrates the 7-stage pipeline
 - `BlackBoxIntegration` - prompt-level injection (working)

2. **SQL-Specific Components**
 - `SQLSchemaSnapshot` - represents database schemas
 - `snapshot_to_world_model()` - converts SQL schemas to world models
 - `SQLSchemaCoprocessor` - wraps runtime with SQL-specific logic
 - `SQLSchemaPlanner` - identifies relevant tables/columns
 - Database introspectors (Postgres, SQLite)

3. **Working Features**
 - Schema extraction from databases
 - Graph representation of tables/columns/foreign keys
 - Semantic retrieval of relevant schema elements
 - Prompt-level hints for SQL generation
 - 30% improvement on SQL benchmarks

### What's Missing for Complete POC ❌

1. **Token-Level Integration**
 - No actual vLLM integration
 - No token marshaling/verification
 - No logit modification
 - NativeIntegration is just a stub

2. **SQL Parsing During Generation**
 - No stateful SQL parser
 - No context tracking (SELECT/FROM/WHERE)
 - No prefix matching for partial identifiers

3. **Real-time Verification**
 - No token blocking mechanism
 - No prefix validation against schema
 - No incremental parsing

4. **Production Features**
 - Limited to Postgres/SQLite (no MySQL, Snowflake, etc.)
 - No efficient prefix trees for large schemas
 - No caching layer for repeated queries
 - No async/streaming support

## Project Plan: Building a Working SQL POC

### Phase 1: Complete Current Architecture (1-2 weeks)

#### 1.1 Enhance World Model Retrieval
```python
# TASK: Add prefix matching to WorldModel
class WorldModel:
 def find_nodes_with_prefix(self, prefix: str, node_type: str = None):
 """Find all nodes whose labels start with prefix"""
 # Implementation needed

 def build_prefix_tree(self):
 """Build trie for efficient prefix matching"""
 # Implementation needed
```

**Tasks:**
- [ ] Implement prefix matching in WorldModel
- [ ] Add prefix tree/trie for efficient lookups
- [ ] Cache frequently accessed prefixes
- [ ] Add fuzzy matching for typos

#### 1.2 SQL Context Parser
```python
# TASK: Build stateful SQL parser
class SQLParseContext:
 def __init__(self):
 self.current_clause = None # SELECT/FROM/WHERE
 self.expecting = None # table/column/function
 self.active_tables = []
 self.partial_identifier = ""

 def update_with_token(self, token: str):
 """Update parse state with new token"""
 # Implementation needed
```

**Tasks:**
- [ ] Implement SQL grammar state machine
- [ ] Track clause transitions
- [ ] Identify expected token types
- [ ] Handle nested queries

#### 1.3 Enhanced SQL Planner
```python
# TASK: Improve SQLSchemaPlanner
class EnhancedSQLSchemaPlanner(SQLSchemaPlanner):
 def plan_with_context(self, query: str, partial_sql: str, state: CognitiveState):
 """Plan with awareness of partial SQL being generated"""
 # Parse partial SQL to understand context
 # Narrow down candidates based on context
 # Return context-aware constraints
```

**Tasks:**
- [ ] Parse partial SQL during generation
- [ ] Context-aware table/column filtering
- [ ] Handle JOIN path discovery
- [ ] Support subquery context

### Phase 2: Mock Token-Level Integration (1 week)

#### 2.1 Simulated Token Verification
```python
# TASK: Build token verification simulator
class MockTokenVerifier:
 def __init__(self, world_model: WorldModel):
 self.world_model = world_model
 self.parse_context = SQLParseContext()

 def verify_token_sequence(self, tokens: List[str]) -> List[VerificationResult]:
 """Simulate token-by-token verification"""
 results = []
 for token in tokens:
 self.parse_context.update_with_token(token)
 result = self.verify_single_token(token)
 results.append(result)
 return results

 def verify_single_token(self, token: str) -> VerificationResult:
 """Check if token is valid given context"""
 # Implementation needed
```

**Tasks:**
- [ ] Build token sequence validator
- [ ] Simulate blocking invalid tokens
- [ ] Test with real SQL examples
- [ ] Measure accuracy improvements

#### 2.2 Integration Test Harness
```python
# TASK: Test harness for token verification
class SQLGenerationSimulator:
 def generate_with_verification(self, prompt: str, world_model: WorldModel):
 """Simulate SQL generation with verification"""
 # Generate SQL token by token
 # Verify each token
 # Block/correct invalid tokens
 # Return verified SQL
```

**Tasks:**
- [ ] Build generation simulator
- [ ] Create test suite with known bad SQLs
- [ ] Measure hallucination prevention
- [ ] Benchmark performance

### Phase 3: Real vLLM Integration (2-3 weeks)

#### 3.1 vLLM Hook Development
```python
# TASK: Actual vLLM integration
class VLLMOctoIntegration:
 def __init__(self, model, world_model):
 self.model = model
 self.world_model = world_model
 self.verifier = TokenVerifier(world_model)

 def generate(self, prompt: str):
 """Custom generation with verification"""
 # Hook into vLLM generation loop
 # Modify logits based on verification
 # Return grounded SQL
```

**Tasks:**
- [ ] Study vLLM architecture
- [ ] Implement logit modification hook
- [ ] Test with small model (7B)
- [ ] Measure latency impact

#### 3.2 Native Integration Implementation
```python
# TASK: Complete NativeIntegration
class NativeIntegration(ModelIntegration):
 def inject(self, frame, state, fused):
 # Access model internals
 # Modify hidden states
 # Bias token probabilities
 return ControlPacket(
 hidden_state_delta=computed_delta,
 logit_bias=token_constraints,
 verification_rules=sql_rules
 )
```

**Tasks:**
- [ ] Implement hidden state modification
- [ ] Build logit bias computation
- [ ] Test with different models
- [ ] Optimize for performance

### Phase 4: Production Hardening (2 weeks)

#### 4.1 Database Support
**Tasks:**
- [ ] Add MySQL introspector
- [ ] Add Snowflake introspector
- [ ] Add BigQuery introspector
- [ ] Test with large schemas (1000+ tables)

#### 4.2 Performance Optimization
**Tasks:**
- [ ] Implement async retrieval
- [ ] Add Redis caching layer
- [ ] Optimize prefix trees for memory
- [ ] Profile and optimize hot paths

#### 4.3 Robustness
**Tasks:**
- [ ] Handle malformed SQL gracefully
- [ ] Support multiple SQL dialects
- [ ] Add timeout mechanisms
- [ ] Implement retry logic

### Phase 5: Evaluation & Benchmarking (1 week)

#### 5.1 Benchmark Suite
**Tasks:**
- [ ] Run on Spider benchmark
- [ ] Run on BIRD benchmark
- [ ] Run on custom enterprise schemas
- [ ] Compare with/without OCTO

#### 5.2 Metrics
**Tasks:**
- [ ] Measure schema hallucination rate
- [ ] Measure syntactic correctness
- [ ] Measure semantic accuracy
- [ ] Track inference latency

## Implementation Priority Order

### Week 1-2: Foundation
1. **Prefix matching in WorldModel** - Critical for token verification
2. **SQL parse context tracker** - Needed to understand generation state
3. **Mock token verifier** - Prove the concept works

### Week 3: Integration Prep
4. **Enhanced SQL planner** - Context-aware planning
5. **Test harness** - Validate approach
6. **Performance baseline** - Measure current metrics

### Week 4-5: vLLM Integration
7. **vLLM hooks** - Real token intervention
8. **Native integration** - Complete the implementation
9. **End-to-end testing** - Verify it works

### Week 6: Polish
10. **Additional databases** - Expand support
11. **Performance optimization** - Make it fast
12. **Documentation** - Make it usable

## Success Metrics for POC

### Must Have
- ✅ 0% schema hallucination (tables/columns that don't exist)
- ✅ Works with at least one LLM (e.g., Llama 7B)
- ✅ Demonstrates token-level intervention
- ✅ 50%+ reduction in syntax errors

### Nice to Have
- ⭐ <100ms latency overhead per query
- ⭐ Works with multiple SQL dialects
- ⭐ Supports 1000+ table schemas
- ⭐ Streaming token verification

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| vLLM integration too complex | High | Start with mock implementation |
| Performance overhead too high | Medium | Optimize hot paths, use caching |
| Token verification breaks generation | High | Fallback to prompt-level hints |
| Prefix matching too slow | Medium | Use tries, cache common prefixes |

## Next Steps

1. **Start with Phase 1.1** - Implement prefix matching
2. **Build SQL parse context** - Track generation state
3. **Create mock verifier** - Prove concept
4. **Test with real queries** - Validate approach
5. **Then tackle vLLM integration** - Make it real

## Code Locations

- World Model: `src/octo/world_state.py`
- SQL Coprocessor: `implementations/sql/sql_coprocessor.py`
- Integration: `src/octo/integration.py`
- Runtime: `src/octo/runtime.py`
- Tests: `tests/test_simple_sql_with_octo.py`

## Estimated Timeline

**Total: 6-8 weeks for complete POC**

- Week 1-2: Foundation (prefix matching, parsing)
- Week 3: Mock implementation
- Week 4-5: vLLM integration
- Week 6: Polish and optimization
- Week 7-8: Buffer for unknowns

This plan provides a clear path from the current prompt-level integration to true token-level verification for SQL generation.