# OCTO Falsification & Benchmark Plan

## Executive Summary

The RETRO-v2 falsification plan reveals a critical insight: **the real competitor isn't single-shot RAG, it's iterative/agentic RAG**. OCTO must prove it can deliver **iterative-RAG quality at single-shot cost** through structured world models.

We propose building **Multi-Hop World Coprocessors** using Wikipedia + multi-hop QA datasets to prove OCTO's superiority over both RETRO and iterative RAG on **compositional reasoning**.

---

## Part 1: Critical Insights from RETRO-v2 Analysis

### The Hidden Truth: GCCA's Real Competitor

The falsification plan exposes what the main doc obscures:
> "The real baseline is **iterative RAG** (free continuous retrieval), not single-shot RAG."

This changes everything. OCTO isn't competing with simple RAG - it's competing with **agents that can iteratively retrieve**.

### The Multi-Hop Signal

RETRO's entire value proposition depends on **hidden bridge entities**:
```
Question: "What's the capital of the country where the author of [book X] was born?"
Single-shot: Can't retrieve the right chunks (doesn't know author or country yet)
Iterative: First retrieves author → then country → then capital
OCTO: Has the full knowledge graph - can traverse: Book → Author → Country → Capital
```

**OCTO's advantage**: We don't need to "discover" the bridge entities through retrieval - they're explicitly encoded in our graph structure!

### The Tier 0 Kill Test We Should Adopt

Before building anything complex:
> "On a multi-hop set, run single-shot RAG vs iterative/agentic RAG. If iterative does NOT beat single-shot → continuous retrieval doesn't help → STOP."

**OCTO's version**: If graph traversal doesn't beat iterative RAG on multi-hop → structured knowledge doesn't help → STOP.

---

## Part 2: Multi-Hop World Coprocessors with Provable Benchmarks

### The Core Hypothesis

**OCTO can solve multi-hop reasoning in O(1) graph traversals while iterative RAG needs O(n) retrieval rounds.**

### Benchmark Suite Design

#### Tier 1: Wikipedia Knowledge Graph Coprocessor

**Dataset**: Wikipedia (for HotpotQA, 2WikiMultiHopQA, MuSiQue)

**World Model Structure**:
```python
@dataclass
class WikipediaWorldModel:
 """Multi-hop reasoning over Wikipedia entities"""

 # Core entity types
 entities = {
 "person": ["birth_place", "occupation", "works", "education"],
 "place": ["country", "capital", "population", "located_in"],
 "work": ["author", "genre", "published", "publisher"],
 "organization": ["founded", "headquarters", "founder", "industry"]
 }

 # Multi-hop relations (the key to beating iterative RAG)
 multi_hop_paths = {
 "author_birthplace_capital": ["work", "author", "birth_place", "capital"],
 "company_founder_education": ["company", "founder", "education", "institution"],
 "book_publisher_headquarters": ["book", "publisher", "headquarters", "city"]
 }

 def traverse_path(self, start_entity: str, path: List[str]) -> str:
 """Single graph traversal solves multi-hop in O(1)"""
 current = self.get_entity(start_entity)
 for relation in path:
 current = self.follow_edge(current, relation)
 return current
```

**Provable Metrics**:
```python
class MultiHopBenchmark:
 def evaluate(self, world_model: WikipediaWorldModel):
 results = {
 "single_hop_accuracy": 0, # Should match iterative RAG
 "multi_hop_accuracy": 0, # Should BEAT iterative RAG
 "traversal_steps": [], # Should be O(1) vs O(n)
 "latency_ms": [], # Should be faster
 "correctness_guarantee": [] # Should be 100% on structured queries
 }

 # The key discriminator: hidden bridge entities
 for question in self.multi_hop_questions:
 # OCTO: 1 traversal
 octo_path = world_model.find_path(
 question.start_entity,
 question.target_attribute
 )

 # Iterative RAG: n retrievals
 rag_retrievals = self.simulate_iterative_rag(question)

 # OCTO should win on:
 # 1. Fewer steps (1 vs n)
 # 2. Guaranteed correctness (path exists or doesn't)
 # 3. No hallucination of bridge entities
```

#### Tier 2: FRAMES Compositional Reasoning

**FRAMES** tests systematic generalization - perfect for OCTO's structured approach:

```python
class FRAMESWorldModel:
 """Compositional reasoning with explicit structure"""

 def __init__(self):
 # FRAMES tests combinations of facts
 self.fact_types = {
 "location": Graph(),
 "temporal": Graph(),
 "causal": Graph(),
 "hierarchical": Graph()
 }

 # The key: OCTO can compose these systematically
 self.composition_rules = {
 "transitive": lambda a, b, c: self.infer_transitive(a, b, c),
 "temporal_ordering": lambda events: self.order_events(events),
 "causal_chain": lambda causes: self.trace_causality(causes)
 }

 def solve_compositional_query(self, query):
 """Solve through systematic graph operations, not retrieval"""
 # Decompose query into atomic facts
 atoms = self.decompose(query)

 # Apply composition rules (guaranteed correct)
 result = self.compose(atoms, self.composition_rules)

 # This is deterministic and verifiable!
 return result, self.generate_proof_trace()
```

### Benchmark Implementation Plan

```python
class OctoBenchmarkSuite:
 """Prove OCTO beats iterative RAG on multi-hop reasoning"""

 def __init__(self):
 self.datasets = {
 "hotpot_qa": HotpotQA(), # 2-hop factoid
 "2wiki_multihop": Wiki2Hop(), # 2-4 hop chains
 "musique": MuSiQue(), # 2-4 hop with distractors
 "frames": FRAMES(), # Compositional generalization
 "popqa": PopQA(), # Single-hop control
 "triviaqa": TriviaQA() # Single-hop control
 }

 def run_tier_0_kill_test(self):
 """First prove structured helps at all"""

 results = {}
 for dataset in ["hotpot_qa", "2wiki_multihop"]:
 # Compare approaches
 single_shot = self.run_single_shot_rag(dataset)
 iterative = self.run_iterative_rag(dataset)
 octo = self.run_octo_coprocessor(dataset)

 # Kill criteria
 if iterative <= single_shot:
 return "STOP: Continuous retrieval doesn't help"

 if octo <= iterative:
 return "STOP: Structure doesn't beat iteration"

 return "CONTINUE: OCTO shows promise"

 def run_decisive_experiment(self):
 """The full comparison"""

 systems = {
 "base_llm": BaseLLM(),
 "single_shot_rag": SingleShotRAG(),
 "iterative_rag": IterativeRAG(), # The real competitor
 "retro_gcca": RetroGCCA(),
 "octo": OctoCoprocessor()
 }

 # The 2x2 scoring matrix
 results = {
 "accuracy": {}, # OCTO should match/beat iterative
 "efficiency": {} # OCTO should match single-shot
 }

 # Critical: Multi-hop vs Single-hop performance
 for system in systems:
 results["multi_hop_gain"] = (
 system.multi_hop_accuracy - system.single_hop_accuracy
 )

 # OCTO wins if:
 # 1. Highest multi_hop_gain (structure helps most)
 # 2. Accuracy >= iterative_rag
 # 3. Efficiency >= single_shot_rag

 return results
```

---

## Part 3: Standalone Embedding Pipeline for World Model Coprocessors

### Architecture: Hybrid Graph-Vector Pipeline

You're right that we need a hybrid approach. Here's why and how:

```python
class WorldModelEmbeddingPipeline:
 """
 Standalone pipeline that builds BOTH:
 1. Structured knowledge graph (for correctness)
 2. Dense vector embeddings (for retrieval)
 """

 def __init__(self):
 # The hybrid storage
 self.graph_store = GraphDatabase() # Neo4j or similar
 self.vector_store = VectorDatabase() # FAISS/Pinecone
 self.bridge_index = BridgeIndex() # Maps between them

 # Key insight from RETRO: Late chunking preserves context
 self.chunking_strategy = "late" # Full doc → embed → chunk

 def process_document(self, doc):
 """Build structured + vector representations"""

 # 1. Extract structured knowledge (OCTO's strength)
 entities = self.extract_entities(doc)
 relations = self.extract_relations(doc, entities)
 constraints = self.extract_constraints(doc)

 # 2. Build graph representation
 graph_nodes = self.build_graph(entities, relations, constraints)

 # 3. Generate embeddings WITH structure awareness
 # This is the key: embeddings that know about graph structure
 structured_embeddings = self.embed_with_structure(
 doc,
 context=graph_nodes, # Include graph context
 strategy="late_chunking" # RETRO insight
 )

 # 4. Create hybrid index entries
 for node in graph_nodes:
 # Each graph node has vector representation
 node.embedding = structured_embeddings[node.id]

 # Store in both systems
 self.graph_store.add(node)
 self.vector_store.add(node.id, node.embedding)

 # Bridge index maintains mapping
 self.bridge_index.link(
 graph_id=node.id,
 vector_id=node.embedding_id,
 metadata=node.metadata
 )

 return graph_nodes, structured_embeddings
```

### Key Design: Composite Multi-Aspect Keys (from RETRO)

RETRO had a good insight with Composite Multi-Aspect Keys. OCTO should adopt and improve:

```python
class CompositeWorldModelKey:
 """Enhanced keys that combine structure + similarity"""

 def __init__(self):
 self.aspects = {
 "local": None, # 64-token local context (RETRO)
 "document": None, # Document-level embedding
 "graph": None, # Graph neighborhood embedding
 "semantic": None, # Semantic role in domain
 "temporal": None # Temporal context if applicable
 }

 def build_key(self, chunk, graph_context):
 """Build multi-aspect key for retrieval"""

 # Local context (from RETRO)
 self.aspects["local"] = embed_chunk(chunk)

 # Graph structure (OCTO's addition)
 self.aspects["graph"] = embed_graph_neighborhood(
 chunk.entity,
 hop_distance=2
 )

 # Semantic role (OCTO's addition)
 self.aspects["semantic"] = encode_semantic_role(
 chunk.entity.type,
 chunk.entity.domain_role
 )

 # Composite scoring
 return self.weighted_combination()

 def weighted_combination(self):
 """Different weights for different query types"""
 if self.query_type == "multi_hop":
 # Emphasize graph structure
 weights = {"graph": 0.5, "semantic": 0.3, "local": 0.2}
 elif self.query_type == "factual":
 # Emphasize local and document
 weights = {"local": 0.4, "document": 0.4, "graph": 0.2}

 return sum(w * self.aspects[k] for k, w in weights.items())
```

### The Critical Innovation: Structure-Aware Embeddings

Standard embeddings don't know about structure. OCTO's should:

```python
class StructureAwareEmbedder:
 """Embeddings that understand graph structure"""

 def __init__(self):
 # Base encoder (BERT/BGE)
 self.text_encoder = AutoModel.from_pretrained("BAAI/bge-base")

 # Graph encoder (GraphSAGE/GCN)
 self.graph_encoder = GraphNeuralNetwork()

 # Fusion layer
 self.fusion = CrossModalFusion()

 def embed(self, text, graph_context=None):
 """Generate embeddings aware of graph structure"""

 # Standard text embedding
 text_emb = self.text_encoder(text)

 if graph_context:
 # Encode graph neighborhood
 graph_emb = self.graph_encoder(graph_context)

 # Fuse text and graph signals
 # This is where OCTO beats pure vector search
 combined = self.fusion(text_emb, graph_emb)

 # The key: embeddings that "know" about constraints
 # When retrieved, they bring their graph context
 return combined

 return text_emb
```

### Production Pipeline Architecture

```python
class OctoWorldModelBuilder:
 """Complete pipeline for building world model coprocessors"""

 def __init__(self, config):
 self.stages = {
 "ingestion": DocumentIngestion(),
 "extraction": KnowledgeExtraction(),
 "graph_build": GraphConstruction(),
 "embedding": StructureAwareEmbedder(),
 "indexing": HybridIndexer(),
 "validation": ConstraintValidator()
 }

 # Adopting RETRO's staged approach
 self.deployment_stages = {
 "poc": {"docs": 10_000, "hardware": "single_gpu"},
 "dev": {"docs": 1_000_000, "hardware": "dgx"},
 "prod": {"docs": 100_000_000, "hardware": "cluster"}
 }

 def build_world_model(self, domain, documents):
 """End-to-end pipeline"""

 # 1. Extract knowledge
 knowledge = {
 "entities": [],
 "relations": [],
 "constraints": [],
 "metadata": {}
 }

 for doc in documents:
 # Domain-specific extraction
 if domain == "wikipedia":
 k = WikipediaExtractor().extract(doc)
 elif domain == "scientific":
 k = ScientificExtractor().extract(doc)
 elif domain == "sql":
 k = SQLExtractor().extract(doc)

 knowledge.update(k)

 # 2. Build graph
 graph = self.stages["graph_build"].build(knowledge)

 # 3. Generate structure-aware embeddings
 embeddings = self.stages["embedding"].embed_graph(graph)

 # 4. Create hybrid index
 index = self.stages["indexing"].index(graph, embeddings)

 # 5. Validate constraints
 validation = self.stages["validation"].validate(graph)

 return WorldModel(
 graph=graph,
 embeddings=embeddings,
 index=index,
 validation_report=validation
 )
```

### Why Hybrid (Graph + Vector) is Correct

You're absolutely right about needing both:

1. **Graph for Correctness**:
 - Hard constraints (SQL schemas, type systems)
 - Multi-hop traversal (entity relationships)
 - Compositional reasoning (systematic generalization)

2. **Vectors for Coverage**:
 - Semantic similarity (finding related concepts)
 - Soft matching (typos, paraphrases)
 - Efficient retrieval (ANN search)

3. **The Synthesis**:
 ```python
 # Pure vector: Might retrieve wrong but similar
 vector_result = vector_store.search(query) # Fast but unsafe

 # Pure graph: Might miss relevant but differently-phrased
 graph_result = graph_store.traverse(query) # Safe but rigid

 # OCTO hybrid: Vector retrieval → Graph validation
 candidates = vector_store.search(query, top_k=10) # Fast retrieval
 validated = graph_store.validate(candidates) # Ensure correctness
 result = graph_store.expand(validated) # Add structure
 ```

---

## Part 4: Falsification Criteria for OCTO

Adopting RETRO's falsification approach:

### Tier 0: Kill Test (1 day, $0)
```python
def tier_0_kill_test():
 """Does structure help at all?"""

 # Simple test on HotpotQA sample
 dataset = load_dataset("hotpot_qa", split="validation[:100]")

 # Compare without building anything complex
 single_shot = evaluate_single_shot_rag(dataset)
 iterative = evaluate_iterative_rag(dataset)
 graph_mock = evaluate_simple_graph_lookup(dataset)

 if graph_mock <= iterative:
 return "KILL: Structure doesn't beat iteration"

 return "PROCEED: Structure shows promise"
```

### Tier 1: Mechanism Validation (1 week, MacBook)
```python
def tier_1_mechanism_test():
 """Do the graph operations work correctly?"""

 tests = {
 "traversal": test_multi_hop_traversal(),
 "constraints": test_constraint_enforcement(),
 "composition": test_compositional_reasoning(),
 "no_hallucination": test_impossible_paths()
 }

 if not all(tests.values()):
 return "FIX: Core mechanisms broken"

 return "PROCEED: Mechanisms validated"
```

### Tier 2: Decisive Experiment (2 weeks, 1 GPU)
```python
def tier_2_decisive_experiment():
 """OCTO vs all baselines on real benchmarks"""

 results = run_full_benchmark_suite()

 # Success criteria
 wins_needed = {
 "multi_hop_accuracy": results["octo"] > results["iterative_rag"],
 "efficiency": results["octo"].latency < results["iterative_rag"].latency,
 "no_hallucination": results["octo"].hallucination_rate == 0,
 "systematic_generalization": results["octo"].frames_score > all_others
 }

 if sum(wins_needed.values()) < 3:
 return "KILL: Insufficient advantage"

 return "SCALE: Clear superiority demonstrated"
```

---

## Recommendations

1. **Start with Tier 0 immediately** - One day could save months
2. **Build Wikipedia world model first** - It covers 4/5 benchmarks
3. **Use hybrid graph+vector from the start** - Don't commit to pure approach
4. **Adopt RETRO's staged hardware plan** - But with OCTO's structured approach
5. **Focus on multi-hop as the discriminator** - This is where OCTO theoretically dominates

The key insight from the RETRO analysis: **The real competition isn't single-shot RAG, it's iterative/agentic RAG.** OCTO must prove it can deliver iterative quality at single-shot cost through structured world models.