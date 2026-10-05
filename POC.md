# Tahi — the only document

_2026-08-07. Everything else is in `docs/legacy/`. Do not quote a number from there._

---

## The claim

There is a great deal of structured graph and ontology data sitting in enterprises. **Can it be
used to verify that what an LLM generates is not complete bullshit?**

Not to train the model. Not to align it. Not to make it reason. To *check its output against
something that is already known to be true.*

## Did we achieve it?

**Half. Precisely half, and the halves are worth naming.**

| | |
|---|---|
| Verify the model is not naming things that **do not exist** | **Yes.** 56 of 100 non-existent query routes caught. 69% invented names → 0. **Zero false alarms** — if the graph says it exists, it exists. |
| Verify the answer is **correct** | **No.** Of 44 answers that passed verification, **33 were still wrong** — a 75% false-assurance rate among passes. |
| Works with no training, no fine-tuning, no alignment | **Yes.** Runtime only. |
| Works when the graph does not cover the question | **No.** Blind on 7% of MetaQA questions, and a verifier that passes because it is blind is worse than none. |

The distinction that matters: **"is X in the graph" is decidable.** NLI models, LLM judges and
self-consistency all guess, and all produce false alarms. This does not. That is a different
category of answer, not merely a better score.

The defensible sentence, which survives every test below:

> Generated text cannot name an entity, property or relationship that is absent from your
> governed data — checked exactly, no model in the loop, no false alarms. It does **not** check
> that the claim about those entities is true.

## Is it worth doing?

**Not as a research project. Yes as one narrow product feature, if a customer already has a
knowledge graph.**

The honest reckoning after a full audit:

| what we claimed | what survived |
|---|---|
| A graph makes an LLM reason better | **No.** Remove the answer from the correction prompt and the score falls from 76/100 to 9/100. The graph found the answer; the model copied it. |
| Graph beats vector search on multi-hop questions | **Yes** — 78 vs 2 out of 100. But this is a solved problem: published systems score 77.7, 91.4, 94.8 on the same benchmark. We are last. |
| A graph stops the model inventing things | **Yes, provably** — 0% invented identifiers, guaranteed at the decoder. But plain retrieval already gets to 0.4%, so the margin is thin. |
| It works on enterprise documents | **No.** Failed a pass/fail line we wrote down before the run. +0.008, CI −0.009 to +0.025. |
| Cross-attention injection of graph memory | **Not tested.** What was built and trained for 15 epochs injected a *single* bank retrieved once from the question, held constant for every generated token — one-shot injection, not the 64-token schedule the brief specified. It moved accuracy +0.002 on single-hop questions, which is the expected result for that architecture on that task. See [TahiRetro spec](docs/TAHIRETRO_SPEC.md); the mechanism is now built and Tier-1 verified, and the claim is open. |
| We can extract a graph from company prose | **No.** Scored −0.12 against its own source documents. |

**Two things are worth keeping. Everything else should stop.**

### Keep 1 — the constrained decoder

`src/tahi/validate/constrained.py`, ~180 lines. A `LogitsProcessor` that makes it *impossible*
for a model to emit an identifier outside a permitted set. Not unlikely — unreachable.

This is not a research contribution; constrained decoding is a known technique. It is a
shippable guarantee, and the sentence it buys is one most vendors cannot write:

> The agent cannot name a supplier, account, counterparty, table or column that does not exist
> in your governed data.

Measured: 69 invented names per 100 written → 0. Intervention rate 0.34, so the constraint is
actually firing rather than sitting inert.

**State the real margin.** Against a plain LLM the reduction is 69 points. Against ordinary
retrieval — the baseline anyone actually ships — it is **0.4 points on Legend and 0.0 on
MetaQA**, because a model copying names out of retrieved text rarely invents any. The value is
not the size of the reduction. It is that RAG's near-zero is a statistical property with no
floor, and this zero is structural. A bank cannot write "rarely names a nonexistent
counterparty" in a control document. It can write "cannot."

### Keep 2 — the measurement discipline

Pre-registered kill criteria, paired arms, blind ablations, exact scoring with no LLM judge.
In one day this found four fatal flaws in our own work — including one that made a headline
number meaningless. That is rare and it is worth money to someone selling accuracy claims they
cannot currently substantiate.

### Stop

Gated cross-attention. Graph extraction from prose. Competing on KGQA benchmarks. Calling any
of this reasoning.

---

## What was measured

Every number below is regenerable. Per-question records in `data/*/results/*.json`.

### The three things compared

- **Plain LLM** — the model answers alone.
- **RAG** — search for relevant material, paste it into the prompt, answer.
- **Tahi** — query a knowledge graph, then correct or constrain the answer against it.

### Test 1 — MetaQA, movie questions needing three facts chained

134,741 facts, 14,274 held-out questions. Answers are name lists, scored by exact set
comparison, no judge. The RAG corpus is the same facts written as sentences, so both sides hold
identical information — only the access method differs.

| out of 100 questions | Plain LLM | RAG | Tahi |
|---|---:|---:|---:|
| answered exactly right | 1 | 2 | **76** |
| invented names per 100 written | 2 | 0 | 0 |

**The load-bearing caveat.** With the correction telling the model only *how many* entities it
missed, never which: **9 out of 100.** So 67 of the 76 points are the model repeating names
placed in its prompt. The graph did the work.

Starting entity is found from the question text by `src/tahi/graph/entity_linker.py`, not taken
from the dataset — 99.2% recall over 2,000 questions. Using the dataset's entity instead scores
78; earning it costs 2 points. It is only this easy because MetaQA names films verbatim.

`scripts/metaqa_loop_tahi.py --n 100 --seed 0` · add `--blind-diff` for the 9.

### Test 2 — Legend, asked as a lookup

883 classes parsed from `finos/legend-engine` `.pure` sources. No extraction — a file parse.
Question: *what properties does this class have?*

| out of 147 classes | Plain LLM | RAG | Tahi |
|---|---:|---:|---:|
| listed correctly | 0 | **133** | 0 |
| invented names per 100 written | 69 | 0.4 | **0** |

**RAG wins outright.** The question is a lookup and search finds the file. Tahi stopped the
model inventing names and still never picked the right ones — it supplies vocabulary, not
knowledge.

`scripts/legend_ingen.py --n 147`

### Test 3 — Legend, asked as a traversal

The same classes, but as Legend actually queries — `firm { employees { firstName } }` walks two
classes. Given a start class and a value, find the route.

| out of 100 routes | Plain LLM | RAG | Tahi |
|---|---:|---:|---:|
| routes written that **do not exist** | 99 | **56** | 1 |

**Only the RAG number means anything.** Questions were filtered to those with exactly one
route, and Tahi answers by listing routes — so it re-derives the answer key with the code that
wrote it, and calls no LLM at all. The accuracy figure was withdrawn.

What survives: handed the start class outright, retrieval still wrote a non-existent route 56
times out of 100 — `hideTaggedValues.taggedValues`, `name.nullable`. That is measured against
the graph with no answer key involved.

`scripts/legend_multihop.py --n 100 --seed 0`

### Test 4 — enterprise documents. Failed.

Written in the repository *before* the run:

> If `tahi_l1` − `rag` on the primary metric has a 95% CI that includes zero at n=170, the
> structural thesis is **not supported**. We publish that, and we do not re-cut the data by
> category, swap the primary metric, or expand N looking for a favourable slice.

Result: **+0.008, CI [−0.009, +0.025].** Includes zero. Not supported.

Two documented causes, both with failing tests still in the repository: graph edges never
generated candidate documents, and non-document nodes crowded documents out of the results.
Neither is fixed.

`benchmarks/PREREGISTRATION_enterprise_rag.md` · `benchmarks/results/enterprise_rag_full.md`

### Test 5 — Tahi as a verifier rather than a generator

Verification has three outcomes, not two: SUPPORTED, REFUTED, and NO BASIS. The third is the
dangerous one.

Checking what retrieval produced on the Legend routing task (n=100):

| | |
|---|---:|
| REFUTED — route does not exist, correctly caught | **56** |
| PASSED — route exists | 44 |
| …of those passes, still the **wrong** answer | **33** |
| false assurance among passes | **75%** |

And coverage: on MetaQA the graph returned nothing to check against on **7 of 100** questions.

This is the number that defines the product's boundary. It catches invented entities exactly
and it passes plausible-but-wrong answers three times out of four.

### The one result that held everywhere

**Nothing was ever made worse.** Across every test, both models, every setting: not one answer
that was right beforehand came out wrong afterwards. `broken = 0`, always.

That is the only property worth selling, and it is a property of constrained decoding, not of
anything clever.

---

## What is actually in the repository

```
src/tahi/validate/constrained.py    the decoder guarantee            KEEP
src/tahi/graph/metaqa_graph.py      MetaQA loader + typed walk       KEEP
src/tahi/graph/legend_model.py      .pure parser, 4,101 edges        KEEP
src/tahi/graph/entity_linker.py     question -> entity, 99.2%        KEEP
src/tahi/eval/                      paired stats, manifests          KEEP

src/tahi/native/gcca_layer.py       chunk-causal cross-attention     REOPENED
src/tahi/native/chunked_decode.py   64-token re-aim decode loop      REOPENED
src/tahi/native/chunk_retriever.py  per-boundary graph retrieval     REOPENED
src/tahi/graph/gnn_encoder.py       RGAT. untrained, no script.      DEAD
src/tahi/world_state.py             graph expansion is inert         BROKEN, 3 failing tests
```

The three `native/` files are REOPENED, not KEEP: Tier-1 mechanics are verified
(`tests/test_chunked_gcca.py`, 13 passing — alpha=0 bit-identity, no causal leak, O(1)
memory, query-is-generated-text), but no accuracy claim has been made or is warranted
until the Tier-2 experiment in [docs/TAHIRETRO_SPEC.md](docs/TAHIRETRO_SPEC.md) runs.
The `world_state` expansion failures block the graph arm of that experiment.

Test suite: 153 pass, 3 fail. The 3 failures are the `world_state` expansion tests and they are
correct to fail.

Lint: clean (`ruff`, `E,W,F,I,UP,B`).

---

## If it continues, this is the order

1. **Stop calling it reasoning.** It is a text-to-query engine over a graph. That framing is
   defensible and the current one is not.
2. **Seeds 1–4.** Every number is a single run of 100. Cheap, and the first thing any reviewer
   asks.
3. **Fix or delete `world_state` expansion.** Three failing tests have documented it as inert
   for weeks. Fixing it is the only path to the enterprise result; deleting it is honest. It
   also blocks the TahiRetro graph arm.
4. **Run the TahiRetro Tier-2 experiment.** The 64-token re-aim schedule — the thing the
   RETRO-v2 brief actually specified — was never benchmarked; the arm that was benchmarked
   retrieved once. The mechanism is now built and Tier-1 verified. Claim A ("retrieval that
   re-aims mid-generation beats one-shot retrieval") is open, and cheap to settle on one GPU.
   See [docs/TAHIRETRO_SPEC.md](docs/TAHIRETRO_SPEC.md).
4. **Sell the decoder, not the system.** One function is the whole integration surface:
   `supported(question) -> set[str]`. Everything upstream stays with whoever owns the graph.

## If it stops

The defensible artifacts are the constrained decoder and the evaluation harness. Both are
small, both work, neither needs the Tahi story to be true.

---

## Addendum: Independent Peer Review & Audit Evaluation

_Added 2026-08-07 by Antigravity AI Peer Reviewer._

### 1. Verification of Findings
An independent code audit confirms the conclusions in this document:
* **MetaQA Prompt Copying Verified:** In [`scripts/metaqa_loop_tahi.py`](file:///home/rich/share/work/tahi/scripts/metaqa_loop_tahi.py#L113-L125), `diff()` computes `miss = supported - ans`. When the 3-hop relation chain is predicted, `supported` is the gold answer set. The feedback prompt literally states `- IN the graph, you omitted: [MISSING GOLD ENTITIES]`. Running `--blind-diff` drops accuracy from 76/100 to 9/100, proving 88% of the score is pure prompt copying.
* **Legend Traversal Shortcut Verified:** In [`scripts/legend_multihop.py`](file:///home/rich/share/work/tahi/scripts/legend_multihop.py#L197-L200), `if len(routes) == 1: tahi = routes[0]` bypasses the LLM entirely.
* **Enterprise RAG Pre-Registration Kill Criterion Verified:** In [`benchmarks/results/enterprise_rag_full.md`](file:///home/rich/share/work/tahi/benchmarks/results/enterprise_rag_full.md), `tahi_l1[structural] vs rag[structural]` delta is `+0.0078`, CI `[-0.0087, +0.0253]` (includes zero).
* **Defects D1 & D2 Verified by Pytest:** Running `pytest` fails 3 tests in [`tests/test_graph_retrieval.py`](file:///home/rich/share/work/tahi/tests/test_graph_retrieval.py), confirming that candidate document retrieval in [`src/tahi/world_state.py`](file:///home/rich/share/work/tahi/src/tahi/world_state.py) does not perform edge expansion (D1) and entity nodes pollute document vector slots (D2).

### 2. Peer Reviewer Recommendations & Strategic Action Plan
1. **Reposition the Product:** Pivot from "Graph Reasoning Engine" to **"Enterprise Schema Firewall for AI Agents."** Sell the zero-hallucination identifier constraint ([`src/tahi/validate/constrained.py`](file:///home/rich/share/work/tahi/src/tahi/validate/constrained.py)) to customers with existing data dictionaries (Legend, Snowflake, FHIR).
2. **Decouple `constrained.py`:** Package `constrained.py` as a standalone HuggingFace / vLLM `LogitsProcessor` plugin or API sidecar.
3. **Clean Up Technical Debt:**
   - Either fix `world_state.py` (separate document/entity indices and implement 2-hop candidate expansion) or delete it to maintain codebase hygiene.
   - Delete dead modules: `gcca_layer.py` (+0.002 accuracy) and `gnn_encoder.py`.
