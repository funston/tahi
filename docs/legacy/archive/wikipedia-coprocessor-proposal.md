# Proposal: TAHI Wikipedia Multi-Hop QA World Coprocessor

**Goal:** Build a TAHI world coprocessor over Wikipedia and evaluate it on HotpotQA, 2WikiMultiHopQA, MuSiQue, and FRAMES. Prove that structured world-state retrieval (entity graph + relation paths + chunk evidence) is viable against RAG and RETRO-style baselines.

**Constraint:** This proposal only uses new files prefixed with ``.

---

## 1. The core idea

Multi-hop QA is a natural test for TAHI because the answer depends on traversing explicit relationships between entities:

> *"What is the capital of the country where the author of [book X] was born?"*

The hidden bridge entities are:

1. **book X** → author **A**
2. **A** → born in **country C**
3. **C** → capital **K**

A single-shot RAG system retrieves chunks matching the whole question and may miss the bridge. A TAHI world coprocessor can:

1. Identify seed entities from the question (book X).
2. Traverse the entity graph to find author A, country C, and capital K.
3. Retrieve evidence chunks for each hop.
4. Generate an answer grounded in the traversed path and evidence.

This turns multi-hop QA into a **structured pathfinding + evidence retrieval** problem, not just a similarity-search problem.

---

## 2. World model design

The world model is a **hybrid graph-and-vector structure**:

### 2.1 Graph layer

Nodes:

- `wiki_page` — one per Wikipedia article (title, summary, categories).
- `wiki_section` — major sections within a page.
- `wiki_entity` — named entities extracted from page text (people, places, organizations, works).
- `wiki_category` — Wikipedia category taxonomy nodes.

Edges:

- `page_links_to` — explicit Wikipedia internal link.
- `page_has_section` — page → section.
- `section_contains` — section → entity mention.
- `entity_instance_of` — entity → category.
- `entity_mentioned_in` — entity → page.
- `related_via_embedding` — top-k semantic neighbors (added from vector index).

### 2.2 Vector layer

- Each `wiki_page` and `wiki_section` node has an embedding text.
- A `FaissIndex` (or `InMemoryGraphIndex`) supports semantic search over pages/sections.
- Each retrieved vector is mapped back to a graph node, so retrieval returns structured entities, not raw text.

### 2.3 Why hybrid?

The graph gives TAHI:

- Explicit multi-hop paths.
- Deterministic traversal (no embedding luck).
- Provenance: every answer can be traced to a path.

The vector index gives TAHI:

- Semantic retrieval for question-to-seed matching.
- Coverage when graph links are sparse.
- A bridge back to raw evidence chunks.

This is exactly the architecture TAHI is designed for: structured world state + retrievable evidence.

---

## 3. Coprocessor pipeline

```
Question
 │
 ▼
[Capture] ──► semantic frame + query terms
 │
 ▼
[Retrieve seed entities] ──► vector search over wiki_page nodes
 │
 ▼
[Plan] ──► identify required hops (author, birthplace, capital)
 │
 ▼
[Graph traversal] ──► follow page_links_to / entity relations
 │
 ▼
[Retrieve evidence] ──► get text chunks for nodes on the path
 │
 ▼
[Rules / simulation] ──► validate the path satisfies the question
 │
 ▼
[Fuse] ──► combine graph signal + query embedding
 │
 ▼
[Inject / generate] ──► prompt LLM with structured context + evidence
 │
 ▼
Answer + provenance path
```

The `wikipedia_coprocessor.py` implementation will follow this flow using TAHI's existing runtime.

---

## 4. Benchmarks and metrics

### 4.1 Datasets

| Dataset | Type | Hop count | Size | Notes |
|---|---|---|---|---|
| **HotpotQA** | Multi-hop | 2 | ~90k train / 7.4k dev | Wikipedia-based, bridge entities |
| **2WikiMultiHopQA** | Multi-hop | 2–4 | ~15k train / 12.5k dev | Synthetic but structured |
| **MuSiQue** | Multi-hop | 2–4 | ~20k train / 2.4k dev | Harder, compositional |
| **FRAMES** | Multi-hop / fact-checking | 2–15 | ~600 dev | Long-tail, requires synthesis |

### 4.2 Baselines

1. **Base LLM** — no retrieval.
2. **Single-shot RAG** — retrieve top-k Wikipedia chunks, prepend to prompt.
3. **Iterative RAG** — re-retrieve after each reasoning step / entity extraction.
4. **TAHI world coprocessor** — graph traversal + evidence retrieval.
5. *(Optional)* **GCCA adapter** — if native adapter training is available.

### 4.3 Metrics

**Primary:**

- Exact Match (EM) and F1 vs. gold answer.
- Accuracy on answer-only and evidence-supported subsets.

**Diagnostic (TAHI-specific):**

- **Bridge-entity recall** — did the system retrieve the hidden bridge entity?
- **Path correctness** — is the traversed entity/relation path correct?
- **Evidence chunk precision/recall** — were the right chunks used?
- **Hallucination rate** — how often does the system invent entities or relations?
- **Cost per correct answer** — embedding/build cost + inference cost.

**Efficiency:**

- tokens/sec
- peak memory
- number of LLM calls (iterative RAG vs. TAHI)

---

## 5. Implementation plan

### Phase 1 — Ingestion pipeline (1–2 weeks)

Build `scripts/build-world-model.py` to:

1. Load Wikipedia dump or preprocessed JSON.
2. Parse pages, sections, internal links, categories.
3. Extract named entities (spaCy or LLM-based NER).
4. Build the graph layer as a TAHI `WorldModel`.
5. Compute embeddings for pages/sections.
6. Build a `FaissIndex` or `InMemoryGraphIndex` for vector retrieval.
7. Save the world model via `WorldModelStore`.

### Phase 2 — Coprocessor (1–2 weeks)

Build `implementations/wikipedia/wikipedia_coprocessor.py`:

1. `WikipediaPlanner` — identify hops from the question.
2. `WikipediaRuleEngine` — validate paths and surface bridge entities.
3. `WikipediaCoprocessor` — wraps TAHI runtime and generates answers.

### Phase 3 — Benchmark harness (1 week)

Build `examples/wikipedia_benchmark.py`:

1. Load HotpotQA / 2WikiMultiHopQA / MuSiQue / FRAMES.
2. Run all baselines + TAHI.
3. Execute generated answers against gold labels.
4. Emit JSON report with all metrics.

### Phase 4 — Analysis and native-mode roadmap (1 week)

1. Compare TAHI vs. baselines.
2. Identify failure modes (sparse links, ambiguous entities, missing relations).
3. Write `docs/wikipedia-results.md`.
4. If TAHI wins on accuracy, draft Level 2/3 adapter plan.

---

## 6. Expected outcomes

**Best case:** TAHI matches or beats iterative RAG on multi-hop accuracy while using fewer LLM calls, because graph traversal replaces repeated retrieval.

**Realistic case:** TAHI wins on bridge-entity recall and provenance but ties or slightly lags on final answer EM due to generation quality. This still validates the structured-representation hypothesis.

**Kill case:** Iterative RAG does not beat single-shot RAG, or TAHI graph traversal cannot find bridge entities. Then continuous structured retrieval is not the right mechanism for these datasets.

---

## 7. Files to create

All new files use the `` prefix:

- `docs/retro-v2-review.md` ✅ — review of RETRO-v2 and verification gaps.
- `docs/wikipedia-coprocessor-proposal.md` ✅ — this document.
- `scripts/build-world-model.py` — standalone embedding/world-model pipeline.
- `implementations/wikipedia/__init__.py`
- `implementations/wikipedia/wikipedia_coprocessor.py`
- `examples/wikipedia_demo.py`
- `examples/wikipedia_benchmark.py`
- `tests/test_wikipedia_coprocessor.py`
- `docs/wikipedia-results.md` — after benchmark run.

---

## 8. Why this matters for TAHI

This is the cheapest, most direct test of TAHI's core thesis:

> **Structured world-state retrieval improves correctness in constrained, multi-step reasoning tasks.**

If it works on Wikipedia multi-hop QA, TAHI has a credible path beyond SQL and biomarkers into general knowledge work. If it fails, we learn exactly where the world-model representation breaks and can fix it.
