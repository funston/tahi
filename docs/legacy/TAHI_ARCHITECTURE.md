# TAHI architecture

_2026-08-06. The code that produced the numbers in `docs/STATUS.md`._

---

## Three places the graph can act

```
                    ┌──────────────────────────────────────────┐
   question ───────►│  1. PRE-GENERATION                       │
                    │     traverse, paste results in prompt    │──► 0.18
                    └──────────────────────────────────────────┘

                    ┌──────────────────────────────────────────┐
   question ───────►│  2. IN-GENERATION                        │
                    │     traverse, mask logits every step     │──► 0.37
                    └──────────────────────────────────────────┘

                    ┌──────────────────────────────────────────┐
   question ───────►│  3. POST-GENERATION                      │
                    │     answer, traverse, diff, re-ask       │──► 0.79
                    └──────────────────────────────────────────┘
```

All three share one upstream step — turning a question into an entity set — and differ only
in what they do with it.

---

## The shared step: question → supported entity set

`tahi.graph.metaqa_graph.MetaQAGraph`

**Load.** `kb.txt` is `head|relation|tail`. Two adjacency maps are built, `out` and `inn`, so
traversal can walk an edge in either direction. Entity types are not given in the file; they
are recovered from the schema — whatever sits in the tail of `in_language` is a Language,
whatever sits in the head of `directed_by` is a Movie. No per-dataset table of entity kinds.

**Chain derivation.** A 3-hop question needs an ordered triple of relations, e.g.
`starred_actors → starred_actors → in_language`. Traversal is bidirectional, which is what
makes "movies that share actors with X" expressible as `starred_actors, starred_actors` —
the first walks Movie→Person, the second walks Person→Movie. Two methods:

| method | how | cost |
|---|---|---|
| few-shot | LLM sees the 9-relation schema plus 3 worked examples, returns 3 relation names | 1 LLM call |
| `--enumerate` | all 9³ = 729 chains traversed with **no LLM**; ~58 return non-empty; LLM picks a result set | 1 LLM call, 729 walks |

Nothing is hardcoded per question template. MetaQA has 150 templates; hardcoding them would
score near 100% and prove only that a parser was written.

**Walk.** `MetaQAGraph.walk(start, max_hops, allowed_relations=...)` does a breadth-first
expansion carrying `(node, steps, visited)`. Two rules do the work:

- **No node is revisited within a path.** This is why `X → D → X` is not counted as an answer
  about `X`.
- Endpoints are recorded per `(node, hop)` so the same node at the same depth is not
  duplicated.

`chain_endpoints()` in the run scripts then keeps only paths whose relation sequence equals
the requested chain exactly, and drops the seed entities.

**Measured effect of the no-revisit rule**, same 100 chains, against a naive traversal that
lacks it:

| | `MetaQAGraph.walk` | naive |
|---|---:|---:|
| gold answers fully contained | 0.790 | 1.000 |
| set equals gold exactly | **0.790** | 0.530 |
| mean candidate set size | 11.1 | 12.3 |

Smaller set on 55 of 100 questions, larger on zero. It trades recall for precision — across
those 55 it drops 70 non-gold entities and 51 gold ones. Under exact-set-match scoring the
trade wins, 0.636 against 0.164 end-to-end on that subset.

The 0.790 containment figure is a **hard ceiling**: on 21% of questions the walk cannot reach
a gold answer, so no downstream mechanism can recover them.

---

## 1. Pre-generation — `scripts/metaqa_verify.py`

The conventional integration. Traverse, format the candidates as text, paste into the prompt,
generate once.

```
prompt = f"Question: {q}\nCandidates from a knowledge graph: {', '.join(cands)}\nAnswer:"
```

Scores 0.18. Included as the floor, because it is what most graph-RAG systems ship.

---

## 2. In-generation — `tahi.validate.constrained.GraphConstrainedLogits`

A `transformers.LogitsProcessor`. The graph is consulted at **every decode step**; no graph
text appears in any prompt and there is no second generation.

```python
for each decode step:
    logits = model(...)
    logits = GraphConstrainedLogits(input_ids, logits)   # ← mask applied here
    token  = argmax(logits)
```

**Construction.** Each allowed entity name is tokenised twice — bare, and prefixed with the
separator — because a name tokenises differently at the start of a reply than after `", "`.

**State.** At each step the processor re-derives its position from the generated token ids
rather than tracking it incrementally. Slower, immune to the desync bugs that make this class
of code produce silently wrong constraints. The automaton is: emit an entity, then a
separator, then another entity, until the allowed set is exhausted or EOS is permitted.

**Matching is longest-first** among unused names, so `IL1` cannot shadow `IL1B`. Each name is
consumed at most once, so the model cannot pad its answer by repeating an allowed entity.

**Masking.** Every token that cannot continue a live prefix is set to `-inf`. EOS is permitted
only at an entity boundary, never mid-name. If nothing is allowed, only EOS is.

**The guarantee is structural**, not statistical: an entity the graph does not support is not
merely unlikely, it is unreachable. This rules out one failure mode — naming unsupported
entities — and no others. It says nothing about whether a claim *about* those entities is true.

**`intervention_rate`** is exposed and reported: the share of decode steps where the
unconstrained model's argmax was something the graph forbade. **Measured 0.440.** Near zero
would mean the constraint was inert and any improvement came from elsewhere.

Scores 0.37 on a local Qwen2.5-1.5B-Instruct against a 0.00 free-generation baseline.

**Dependency.** The allowed set comes from chains derived earlier by the few-shot prompt on
gpt-4o-mini (`--chains-from`), not by the 1.5B. This isolates the injection mechanism — the
thing the script exists to measure — at the cost of inheriting the template dependency and
borrowing a stronger model for query derivation. 0.37 is an upper bound on unaided end-to-end
performance for this model.

---

## 3. Post-generation — `scripts/metaqa_loop_tahi.py`

The strongest arm. Generate normally, then check and correct.

```
answer  = LLM(rag_prompt)
support = supported_set(question)          # MetaQAGraph.walk

repeat up to 3 times:
    d = diff(answer, support)
    if d is None: stop
    answer = LLM(correction_prompt(question, answer, d))
    if answer unchanged: stop
```

`diff()` returns **only what is provably wrong** — never the answer itself:

```
- NOT in the graph, remove: <asserted but unsupported>
- IN the graph, you omitted: <supported but unasserted>
```

The model does the correcting. The graph only states the discrepancy.

Scores 0.79 (few-shot chain) / 0.59 (`--enumerate`, no worked examples). 77 fixed, 0 broken.

**Important property.** End-to-end accuracy (0.790) equals the traversal's own exact-match
rate (0.790). The loop drives the model to transcribe the supported set; the model contributes
nothing beyond transcription. Traversal precision is the score.

This is *not* iterative RAG. Nothing is retrieved mid-reasoning — the graph is consulted only
after a complete answer exists. KiRAG (Fang, Meng & MacDonald, ACL 2025) interleaves retrieval
with reasoning to build the answer in the first place.

---

## The mechanism that does not work — `tahi.native.gcca_layer`

Gated cross-attention from a graph memory tensor into the frozen model's hidden states.

```
H_out = H + tanh(α) · CrossAttn(LayerNorm(H), E_retrieved)      α initialised to 0.0
```

`E_retrieved` is `[B, K, d_retriever]`; `W_K` and `W_V` project it to `d_model`; an
`nn.MultiheadAttention` cross-attends with the hidden states as queries. Attached to 7 frozen
decoder blocks at interleave 4, max 16 memory slots.

**Result on EnterpriseRAG-Bench L3**, 500 questions, trained 15 epochs:

| arm | exact | token F1 | fact coverage |
|---|---:|---:|---:|
| base | 0.036 | 0.075 | 0.017 |
| α = 0 identity control | 0.036 | 0.075 | 0.017 |
| trained | 0.038 | 0.063 | 0.011 |

The identity control passes with 0 mismatches, so the plumbing is correct. Trained, it moves
exact match +0.002 and moves fact coverage down.

**Two things about this run bound what the negative result proves:**

1. **No graph topology reached the memory.** `run_l3_native.py` defaults to `--gnn off`. The
   RGAT (`SubgraphRGATEncoder`) has no training script and no validated checkpoint, so running
   it would project every slot through random weights. The memory tensor therefore held
   encoded text for retrieved nodes and **no relational structure at all**.
2. **The retrieval feeding it is known not to work.** Graph expansion in `world_state.py`
   scores expanded candidates `own_cosine × seed_score × decay`, so they lose every slot to
   unscaled dense hits.

So the honest reading is: *this* cross-attention adapter, over *this* memory, does nothing.
Whether cross-attention over a memory that actually carried graph structure would do something
is untested.

---

## What is not in the loop

| module | status |
|---|---|
| `graph/gnn_encoder.py` (RGAT) | untrained, no training script, off by default |
| `graph/kuzu_store.py` | Cypher store; `expand()` returns `count(DISTINCT a.id) AS support`, wired to nothing |
| `world_state.py` graph expansion | 3 failing tests in `tests/test_graph_retrieval.py` assert it changes retrieval; it does not |

---

## Dependencies of the whole result

```
MetaQAGraph.walk            ── the score. Precision here is end-to-end accuracy.
   │
   ├── chain derivation     ── few-shot examples carry most of the lift
   │                           (schema 0.02 → +bidirectional hint 0.26 → +3 examples 0.92)
   │
   └── seed entity          ── supplied by the dataset. No entity linking anywhere.
```

Full results, limits and regeneration: `docs/STATUS.md`.
Integration with an existing knowledge graph: `docs/TAHI_INTEGRATION.md`.
