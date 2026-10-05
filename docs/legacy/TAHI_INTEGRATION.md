# TAHI on an existing knowledge graph

_2026-08-06_

For an organisation that already operates a knowledge graph with a curated ontology and
entity resolution — RelationalAI, Palantir, Stardog, Neo4j with an OWL/SHACL layer,
TigerGraph.

---

## The coupling surface

TAHI needs one function from the graph:

```python
supported(question: str) -> set[str]     # entity names the graph will vouch for
```

That is the entire interface. `GraphConstrainedLogits` takes a `Sequence[str]` and a
tokenizer; nothing else about the graph reaches it:

```python
GraphConstrainedLogits(tokenizer, allowed_names, *, prompt_len, eos_token_id,
                       separator=", ", min_items=1, max_items=None)
```

The post-generation loop takes the same set and diffs a generated answer against it.

Everything upstream of that function — schema, entity resolution, query language, access
control, freshness — stays with the graph vendor. TAHI does not parse the ontology, does not
store triples, and does not need write access.

---

## What each side supplies

| | supplied by the graph platform | supplied by TAHI |
|---|---|---|
| ontology / schema | ✔ | |
| entity resolution, canonical IDs | ✔ | |
| query execution (Rel, Cypher, SPARQL) | ✔ | |
| row-level access control | ✔ | |
| question → query | shared | |
| query result → allowed entity set | | ✔ |
| decode-step logit constraint | | ✔ |
| post-generation diff-and-correct loop | | ✔ |
| measurement harness, A/B, McNemar | | ✔ |

`tahi.graph.kuzu_store.KuzuGraphStore` already issues Cypher (`neighbors`, `expand`,
`shared_entity_documents`) rather than hand-rolled traversal, so swapping the backing store
for an external engine is a driver change, not an architecture change.

---

## Why an existing graph removes the biggest limitation

The measured results (`docs/STATUS.md`) rest on MetaQA, where the graph is the dataset's
ground truth. Extraction quality was never a variable. That is the largest caveat on every
number, and it is untested: LLM extraction on enterprise prose scores −0.12 against its own
source documents.

**A customer with a curated KG has already solved that problem.** Their graph is maintained,
resolved and governed. The condition that makes the MetaQA results clean is the condition
they operate in permanently.

The second-largest limit likely improves as well. Traversal recall on MetaQA is 0.790 —
`MetaQAGraph.walk` cannot reach a gold answer on 21% of questions, and that is the hard
ceiling on the post-generation loop. That ceiling is a property of a 148-line BFS, not of the
approach. A production query engine with a real query language replaces it.

Two limits do **not** improve and should be stated in any customer conversation:

- **Schema size.** MetaQA has 9 relations. Chain derivation by enumeration is O(|R|³) and
  does not survive hundreds of relation types. Question → query is the open problem, and on
  a customer graph it is their semantic layer's job as much as ours.
- **Entity linking.** `q_entity` is supplied by the dataset in every measured arm. On real
  questions, resolving the subject span to a node is required and unmeasured here.

---

## What TAHI adds that prompt-stuffing a KG does not

Same graph, same query, same model, same candidates, MetaQA 3-hop, n = 100:

| how the graph result reaches the model | exact set match |
|---|---:|
| pasted into the prompt as a candidate list | 0.18 |
| diffed against the answer, errors handed back | **0.79** |
| masked into the logits at every decode step | 0.37 (1.5B local model) |

Prompt-stuffing a knowledge graph is the common integration and it is the weakest of the
three. The decode-time constraint is the one that cannot be ignored by the model: entities
the graph does not support are not merely unlikely, they are unreachable. Measured
intervention rate is 0.440 — the constraint overrides the model's own argmax on 44% of decode
steps.

No configuration has turned a correct answer wrong. `broken = 0` across every arm.

---

## Proving it on their data

A three-week engagement with a pre-registered outcome. Nothing here requires their graph to
leave their environment.

**Week 1 — wire the interface.** Implement `supported(question) -> set[str]` against their
query engine. Build a held-out question set from their existing analytics or support logs,
with answers that are entity lists so scoring is exact set equality and no LLM judge is
involved. If their questions are not entity-list shaped, this is where that surfaces, and it
is a real finding rather than a reason to substitute a softer metric.

**Week 2 — run three arms.** Same questions, same model, paired.

```
their current RAG                              baseline
+ graph result in the prompt                   the usual KG integration
+ TAHI decode constraint / correction loop     the claim
```

**Week 3 — report.** Per-question transitions, McNemar exact on the discordant cells, and
the `fixed` / `broken` counts. `broken` is the number that matters: a corrector that fixes
some answers and breaks others cannot be deployed in a regulated setting, because you cannot
tell which happened to any given answer.

**Pre-registered pass condition, stated before the run:** `fixed > 0`, `broken = 0`, and
McNemar p < 0.05 against the prompt-stuffing arm — not against the no-graph baseline, which
is the easier comparison and the one that flatters us.

**What counts as failure, also stated up front:** if the decode constraint does not beat
prompt-stuffing on their graph, the honest conclusion is that their semantic layer already
extracts most of the available value through the prompt, and TAHI's contribution is limited
to the audit trail.

---

## What TAHI does not do

- **Gated cross-attention does not work.** `tahi.native.gcca_layer` is built, wired
  correctly (α = 0 reproduces the base model with 0 mismatches) and trained for 15 epochs. On
  500 EnterpriseRAG-Bench questions it moves exact match +0.002 and moves fact coverage down.
  It is not part of any proposal.
- **Graph expansion in `world_state.py` does not change retrieval results.** Expanded
  candidates are scored `own_cosine × seed_score × decay` and lose every slot to unscaled
  dense hits.
- **TAHI does not build or maintain a graph.** With a customer who has one, it does not
  need to. With a customer who does not, the extraction question is unanswered and is the
  first thing that would have to be measured.

---

## Status of the evidence

Single benchmark (MetaQA 3-hop), single seed, n = 100, 9 relations, entity-list answers,
subject entity supplied by the dataset. Published MetaQA 3-hop for scale: GraftNet 77.7,
PullNet 91.4, EmbedKGQA 94.8.

Full numbers, methodology and regeneration commands: `docs/STATUS.md`.
