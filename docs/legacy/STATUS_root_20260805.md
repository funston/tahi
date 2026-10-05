# TAHI — What we're doing

_Last updated: 2026-08-05_

## The claim

TAHI says: if you give an LLM a **knowledge graph** instead of a **pile of text**, it
answers better.

Plain text search finds paragraphs that *look* like the question. A graph stores actual
facts and how they connect — *this cancer spreads to that organ, that organ is tested by
this scan* — so you can follow a chain of facts instead of hoping a single paragraph
happens to contain the whole answer.

That's the bet. It is currently unproven.

## Why we can't just try it and see

Every previous attempt in this project produced a number, and every number turned out to
be worthless — because **we built the scoring system too**. If the same person writes the
test and grades the work, a good score proves nothing.

The fix is to use someone else's test.

## The test: GraphRAG-Bench

A public benchmark. **2,062 medical questions.** Three things make it the right choice:

- It ships **its own scoring code** — we cannot tilt the grading.
- **Nine other systems already published scores on it** (LightRAG, Microsoft GraphRAG,
  HippoRAG, RAPTOR, and five more) — real competition, not a strawman.
- Every question ships with **an answer key of the facts required** — so we can check the
  graph is any good *before* testing TAHI on it.

Question mix: Fact Retrieval 1,098 · Complex Reasoning 509 · Contextual Summarize 289 ·
Creative Generation 166.

## What we run

Same questions, same model, three versions. **Only the retrieval changes.**

| Arm | What it gets | Role |
|---|---|---|
| `base` | nothing — answers from memory | floor |
| `vector_rag` | plain text search | **the thing to beat** |
| `tahi_graph` | TAHI's graph | the claim |

If TAHI beats plain text search, the bet pays. If it doesn't, that's a real answer too,
and worth publishing.

## The order — this matters

**1. Build the graph → 2. Check the graph is good → 3. Test TAHI.**

Step 2 is not optional. If the graph is missing the facts, TAHI cannot win, and without
checking there is no way to tell "the graph is empty" apart from "the retrieval is
broken." We would spend the money and learn nothing.

The benchmark hands us step 2 for free: its `evidence_recall` metric takes the gold facts
and asks whether they are present, and its `indexing_eval` scores graph structure. Neither
is our code.

## What to expect

The gap between the best published system and no-retrieval-at-all is about **3 points**
(RAPTOR 73.58% vs vanilla GPT-4o-mini 70.68%).

That is a narrow margin. So the question is not "will TAHI be amazing" — it is **"does the
graph help at all, measurably, by someone else's ruler."** Sloppiness anywhere swamps a
3-point effect, which is why the process below is strict.

## Which model, and why not the DGX

The benchmark standardised on **GPT-4o-mini** for graph building, generation, and judging,
across all nine published systems. Using anything bigger would confound "TAHI is better"
with "our extraction model is better."

The DGX is still useful and is officially supported — the benchmark ships an Ollama client.
Plan: **DGX for iteration** (rebuilding the graph while fixing extraction is free locally),
**GPT-4o-mini for the reported run** (comparability). Embeddings are local BGE either way.

Estimated cost of the reported run: **$15–25.** About a day of work.

## Where we are

**Done**
- Dataset downloaded — corpus, 2,062 questions, answer keys
- The benchmark's own scoring code vendored and running
- Schema derived from the dataset instead of guessed
- Research written up as a spec with sources: `docs/GATE1_SPEC.md`
- Proved our earlier MetaQA numbers were void — the failures were our own retrieval
  settings, not TAHI (see `docs/TAHI_ENDGAME_PLAN.md` §0.2)

**Not done**
- **The graph is not built.** Therefore no results exist.

**Blocked on**
- Sign-off on `docs/GATE1_SPEC.md`.

## Three open decisions (Rich's call)

1. **Step 2's pass mark.** We measure whether the gold facts are in the graph and report
   the number. No threshold picked deliberately — nobody should be marking their own
   homework.
2. **Should `vector_rag` chunk identically to the graph build?** Recommend **yes** —
   otherwise a score difference could be chunking rather than graph structure.
3. **Pilot size** before the full 2,062. Recommend **100**.

## Rules for this run

1. Every metric comes from the benchmark's code. **No metric written by us.**
2. Every threshold, cap, or filter is named in writing with who chose it.
3. Nothing is rejected silently — extractor output that fails a schema gets **logged**,
   not dropped.
4. Step 2's number is reported before Step 3 runs.
5. All three arms share one generation path; retrieval is the only difference.
6. Research → sources → written spec → implementation. In that order.

## Documents

| File | What it is |
|---|---|
| `STATUS.md` | this — the plain-English overview |
| `docs/GATE1_SPEC.md` | the build/test spec, with sources cited |
| `docs/TAHI_ENDGAME_PLAN.md` | full gate structure, decision log, knobs audit |
| `third_party/graphrag_bench_eval/` | the benchmark's scoring code (not ours) |
