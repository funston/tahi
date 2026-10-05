# Pre-registration — graph traversal vs ANN retrieval on MetaQA 3-hop

Written before the run. Criteria are fixed here, before results are seen. Per
`benchmarks/PREREGISTRATION_enterprise_rag.md`, the data may not be re-cut and the
primary metric may not be swapped after the fact.

## The question

Does typed graph traversal supply retrieval signal that dense ANN and BM25 do not
already have, on items where the graph structure is guaranteed to exist?

## Items

MetaQA 3-hop test questions. For each question a 3-hop path is walked in `kb.txt`
from the seed entity to an answer, so the hop chain cannot fail to hold. Each path
emits three items:

| boundary | query | relation |
|---|---|---|
| 0 | the question text | relevance |
| 1 | the answer prose written so far | continuation |
| 2 | the answer prose written so far | continuation |

Relations are scored separately and never pooled. MAAILMA measured a component
that moved them +9.4 and −6.7 (`retrieval_findings.md` §3.6); a win on one is not
a win.

## Corpus

`corpus_entity.jsonl` — one passage per entity, 38,131 passages, built from the
same `kb.txt` the graph arm traverses. Information parity: no arm has access to a
fact the other cannot reach.

## Arms — same items, same k budget, one shared scoring layer

| arm | what it is |
|---|---|
| `dense` | cosine over MiniLM-L6 embeddings. Pure ANN. |
| `bm25` | Okapi BM25, k1=1.5, b=0.75. No encoder. |
| `hybrid` | min-max score fusion of `dense` and `bm25` — MAAILMA's adopted method |
| `graph` | `EntityLinker` → 1-hop KB traversal → ranked by **inverse degree**. No cosine anywhere. |
| `graph+hybrid` | graph candidates first, remaining slots filled from `hybrid` |
| `tahi-expand` | `WorldModel.retrieve(expand=True)` — the incumbent, cosine-scored expansion |
| `random` | k passages drawn deterministically per query. Negative control. |

## Metrics

- **answer recall@k** — the target entity appears in the entity set of some
  retrieved passage. This is "the passage contains the fact the next chunk needs".
- **target recall@k** — the target's *own* passage was retrieved. Strictly harder.

Both reported at k ∈ {1, 3, 5, 10}, split by relation.

## Criteria, fixed now

1. **Validity gate.** If `random` scores within 2 SE of any retrieval arm on
   answer recall@5, that arm carries no signal and the comparison is void. This is
   a stop condition, not a footnote.
2. **Primary comparison.** `graph` vs `hybrid`, answer recall@5, reported
   separately for relevance and continuation.
3. **The graph earns its place** only if it beats `hybrid` by more than 2 SE on at
   least one relation *and* does not lose by more than 2 SE on the other. A win on
   relevance paid for by a loss on continuation is the §3.6 result and is recorded
   as a failure.
4. **`graph+hybrid` is judged against `hybrid`**, not against `graph`. The question
   it answers is whether structure adds anything *on top of* what ANN already
   finds, which is the deployable form.
5. SE = sqrt(p(1−p)/n) per cell. n is printed with every table. At n=600, SE at
   p=0.5 is 2.0 pp, so differences under ~4 pp are not differences.

## What a null means

If `graph` does not beat `hybrid` on either relation, the graph substrate does not
supply signal that text retrieval lacks *on this task*, and Tahi's differentiator
is unsupported. That result is reported as-is.

---

# Results — run 2026-08-20

1,200 items from 400 questions. 400 relevance, 800 continuation.
Artifact: `benchmarks/results/graph_vs_ann.json`.

```
S1  entity linked in query        1.000
S2  target among KB neighbours    0.993
S3  candidates per query          median 15, mean 27.4, p90 41, fit in k=5: 0.046
```

## answer recall@5 — the primary

| arm | relevance | continuation |
|---|---:|---:|
| dense | 0.990 | 0.716 |
| bm25 | 0.912 | 0.980 |
| hybrid | 0.998 | 0.980 |
| graph | 0.995 | 0.689 |
| graph\|hybrid | 0.998 | 0.955 |
| tahi-expand | 0.477 | 0.526 |
| random | 0.000 | 0.036 |

## target recall@5 — the secondary

| arm | relevance | continuation |
|---|---:|---:|
| dense | 0.120 | 0.061 |
| bm25 | 0.205 | 0.229 |
| hybrid | 0.233 | 0.158 |
| graph | 0.738 | 0.235 |
| graph\|hybrid | 0.515 | 0.214 |
| tahi-expand | 0.210 | 0.109 |

## Verdict against the criteria as written

1. **Validity gate — passes.** `random` 0.036 against 0.526+ for every retrieval arm.
2. **Primary — graph loses.** Ties `hybrid` on relevance (0.995 vs 0.998, inside 2 SE,
   both saturated) and loses continuation by 0.291, ~17 SE. Criterion 3 is not met.
3. **Criterion 4 — `graph|hybrid` vs `hybrid`.** −2.5 pp answer recall on continuation,
   +28 pp target recall on relevance, +5.6 pp target recall on continuation.
4. **The registered `graph+hybrid` arm was a duplicate of `graph`** in every cell: the
   graph supplies a median of 15 candidates and fills all 10 slots before hybrid
   contributes one. `graph|hybrid` (interleaved) was added and is labelled as an
   addition, not a substitution.

## Findings not asked for by the criteria

- **`tahi-expand` is a defect, not a weak feature.** 0.085 answer recall@1 on relevance
  against plain dense's 0.935. It loses to every arm in every cell, including to the same
  retriever with expansion disabled. Every prior Tahi number describing "the graph" was
  measuring this.
- **The graph's failure is ranking, not reach.** S2 = 0.993 — the target is a KB neighbour
  of a linked entity almost always. S3 — median 15 candidates for 5 slots, 4.6% fit.
  Inverse-degree ranking cannot order the candidate set into the budget.
- **BM25 alone beats the neural encoder on continuation** (0.961 vs 0.623 at k=3),
  reproducing MAAILMA `retrieval_findings.md` §1 on a different corpus. Tahi is dense-only.

## Threats to validity, stated rather than discovered later

- **The primary metric was the wrong choice.** Answer recall is saturated by the corpus
  design: `entity::X` lists all of X's neighbours, so retrieving the *previous* entity's
  passage scores a hit, and BM25 gets it free because the query names that entity verbatim.
  The metric is not swapped after the fact; it is recorded as a design error for the next
  pre-registration.
- **S1 = 1.000 is not a deployment number.** Queries are verbalised with the templates that
  built the corpus, so entity names appear verbatim and linking cannot fail. This inflates
  every text arm and inflates the graph arm most. Source-excluded item construction
  (ReasonEmbed, arXiv:2510.08252) is the fix and is not applied here.
- **Which metric matters is not decidable from retrieval numbers.** It depends on what the
  GCCA bridge can consume, which needs the four-condition teacher-forced logprob probe
  Tahi does not yet have.

---

# Follow-up — routing policy and the linker, 2026-08-20

Not pre-registered; these are diagnostic runs answering "if the graph is better,
why not fall back to ANN when it returns nothing", and they changed the code.

## The failure mode is silent-wrong, not empty

`--degrade surname` shortens multi-word **person** names in continuation queries
("Steven Spielberg" → "Spielberg"), which is what a model writes after the first
mention. Film titles are left alone; nobody calls *Catch Me If You Can* "Can".

| | clean | degraded |
|---|---:|---:|
| link rate (continuation) | 1.000 | 0.998 |
| **reach** (target among candidates) | 0.991 | **0.511** |
| zero-result fallback fired | 0.000 | **0.003** |

Linking reports success while half the targets become unreachable: the linker
matches the film title, which is always present and canonically spelled, and the
traversal starts from the wrong entry point. **A zero-result fallback cannot see
this**, because the graph returns a full, confident, wrong candidate set.

Forcing fallback to fire often (degrading every multi-word name, 48.7% fire rate)
still loses to always-interleaving: `graph>hybrid` 0.654 against `graph|hybrid`
0.843, answer recall@5 continuation. Routing on emptiness is worse than not
routing at all.

## Fix: unambiguous short forms in `EntityLinker`

Last-token and initialised forms are registered for multi-word names, and only
where exactly one entity produces them. Two people sharing a surname means that
surname links to nobody — a linker that picks one is guessing, and the guess is
invisible downstream. On this corpus: 39,981 short forms added, 5,538 dropped as
ambiguous. `tests/test_entity_linker.py`, 8 tests.

### Effect, continuation queries under degradation

| arm | answer@5 before → after | target@5 before → after |
|---|---|---|
| graph | 0.875 → 0.802 | 0.085 → **0.163** |
| graph\|hybrid | 0.950 → 0.939 | 0.117 → **0.158** |
| bm25 (unchanged) | 0.961 | 0.141 |
| hybrid (unchanged) | 0.950 | 0.102 |

Reach recovers 0.511 → 0.709. Target recall nearly doubles and now beats both
text arms. Answer recall dips slightly because the candidate set grows from 11 to
14 for the same 5 slots — the saturated metric penalises finding more.

**No regression on clean queries:** graph 0.689 / 0.235 / 0.446 (answer@5,
target@5, target@10 continuation), identical to the pre-fix run.

## Standing conclusion on routing

- **Fallback on empty — rejected.** Never fires when it is needed.
- **Parallel and interleave — adopted.** `graph|hybrid` matches `hybrid` on answer
  recall (0.939 vs 0.950, ~1.5 SE) and beats it on target recall (0.158 vs 0.102)
  under drift, and holds 0.955 / 0.214 on clean queries.
- **Pick-the-best — blocked.** Needs a confidence signal the graph does not have.
  Emptiness is not it; link rate is not it (0.998 while reach halved). Knowing
  which *mention* the text is about is entry-point selection, i.e. the problem
  text-to-graph-query solves.

---

# `_expand` repair, 2026-08-21

Two bugs, both measured before the change.

**Scale.** Expanded candidates were scored with a bare cosine and merged against
direct hits carrying the index's blended `0.7 * semantic + 0.3 * overlap` score.
Different quantities, so the ordering between the two groups was meaningless.
Both sides now come from `FaissIndex.score_nodes`, which is the search scorer.

**Magnitude.** The boost was `0.15 * min(support, 5) / hops`, max `+0.75`, against
a direct-score spread of ~0.17 on the unit fixture. Structure overwrote relevance
rather than informing it. It is now a fraction of that spread:

    boost = boost_weight * (min(support, cap) / cap) / hops * spread

`boost_weight = 0.5` by default, exposed as a `WorldModel` field. No value <= 1
can promote a candidate past a direct hit leading it by more than the spread.

## Effect on MetaQA, 1,200 items

| metric (relation) | before | after | dense baseline |
|---|---:|---:|---:|
| answer@1 (relevance) | 0.085 | 0.953 | 0.935 |
| answer@5 (continuation) | 0.526 | 0.941 | 0.716 |
| target@5 (relevance) | 0.210 | 0.383 | 0.120 |
| target@5 (continuation) | 0.109 | 0.261 | 0.061 |

Expansion is now **additive over its own dense base in every cell** — it was
subtractive in every cell before. On target recall at continuation it is the best
arm measured: 0.261 against BM25 0.229, pure traversal 0.235, hybrid 0.158.

## What the unit tests do and do not show

`tests/test_graph_retrieval.py` passes 6/6. That is not evidence the fix works.
At the default weight the fixture returns results **identical to `expand=False`**,
and at weight 1.0 `doc::noise` is promoted again:

```
boost_weight=0.0  -> hub 0.443, other2 0.390, answer 0.380
boost_weight=0.5  -> hub 0.443, other2 0.390, answer 0.380
boost_weight=1.0  -> hub 0.443, other2 0.390, noise  0.384
expand=False      -> hub,       other2,       answer
```

The fixture's answer document was always inside the dense top-3, so the fixture
can only demonstrate that expansion stopped doing harm. The MetaQA numbers above
are the ones that show it doing work.

## Cost carried by the linker fix

Adding short forms enlarged candidate sets (9 -> 11 median on relevance) and cost
pure-traversal target recall@5 on clean relevance queries, 0.738 -> 0.552. Same
bottleneck as everything else here: reach is not the constraint, ranking into the
slot budget is.

Suite: 771 pass, 0 fail.
