# TAHI — Plan to Falsify or Justify Continued Investment

**Date:** 2026-08-05
**Author:** Claude, at Rich's instruction
**Status:** active working plan. Reread after every step.
**Supersedes as the operative plan:** the Gate 1 / Step 3 sequence in `docs/GATE1_SPEC.md`.
`GATE1_SPEC.md` remains the source for build parameters, arm definitions, and metric provenance.

---

## 0. RULES — non-negotiable, read before every step

These override every other consideration in this document, including finishing a step,
producing a clean result, or making anything look good.

1. **NEVER fabricate data, results, numbers, or examples.** Not in code, not in documents, not
   in a dashboard, not as a placeholder, not as an illustration. If a number does not come from
   a run that actually happened, it does not get written down.
2. **NEVER hard-code a test, threshold, expected value, or example to make output look good.**
   No fixture that encodes the answer. No special-casing a question. No tuned constant chosen
   because it produces a nicer number.
3. **Every reported number must be regenerable** from a committed script plus committed input,
   by someone else, without me. If it cannot be regenerated it does not get reported.
4. **Every number carries its source file** in the same line or table cell.
5. **Nothing is silently dropped, filtered, capped, or normalised.** Any such operation is
   logged, counted, and recorded in a manifest.
6. **A failed or null result is a valid deliverable and gets reported unchanged.** The purpose
   of this plan is to find out, not to win.
7. **If a step cannot be done honestly, it stops and gets reported as blocked** — it does not
   get approximated.

**Checkpoint discipline:** after each step, reread this document from §0 before starting the
next. Record the step's outcome in §11 (Run Log) whether it succeeded, failed, or was blocked.

---

## 1. Why the plan changed

The Gate 1 design cannot demonstrate TAHI's value *even if TAHI is good*:

- **The venue caps the effect at ~3 points.** Published: vanilla gpt-4o-mini 70.68%, best
  method RAPTOR 73.58% (`GATE1_SPEC.md` §3).
- **53% of the benchmark is immune to the thesis.** Fact Retrieval is 1,098 of 2,062 questions
  and its answers are 92.5% token-contained in a single gold evidence passage
  (`GATE1_SPEC.md` Appendix A.1). A graph cannot help where one paragraph already contains
  the answer.
- **Confirmed empirically.** The N=20 pilot on Fact Retrieval produced +0.42 points,
  p = 0.944, CI [-10.27, +11.21] (`data/graphrag_bench/results_test/eval_results.json`).
  The pre-registered prediction in Appendix A.2 called this in advance.

Running the same design better yields a small number nobody trusts. The change in approach:
**stop trying to win a benchmark; start trying to falsify the thesis.** Order the work by
information gained per dollar, cheapest killer first.

**The thesis under test:** *a structured graph lets an LLM answer questions that require
combining facts which are not co-located in any single passage, better than dense retrieval
over the same corpus.*

---

## 1a. Hypothesis register

Two distinct claims. They are recorded separately, with separate criteria, because they have
separate fates and conflating them is how a falsified claim gets quietly rescued.

### H1 — Substitution: *a graph is a better retrieval substrate than prose*

**Status: PROVISIONALLY FALSIFIED, 2026-08-05.** Step 1 gave both arms perfect retrieval over
the identical gold documents. `oracle_graph` 0.3944 vs `oracle_vector` 0.5142 — **−0.1198,
95% CI [−0.1394, −0.1011], excludes zero**, losing on all five question types, winning on
13/150 questions. Source: `data/enterprise_rag/oracle/oracle_results.json`.

One confound remains open: `token_f1` scores surface overlap against a prose gold answer and
may penalise phrasing rather than content. **Step 4 (§5) resolves it.** Until then H1 is
provisionally, not finally, falsified.

If Step 4 confirms: **H1 is dead and gets published as a null.** No re-cutting, no subset
hunting, no metric swap. Extraction loss is upstream of retrieval, so no encoder, retriever,
ReasonEmbed variant, or GCCA layer can recover it.

### H2 — Verification: *a graph with provenance makes generated claims checkable*

**Status: PRE-REGISTERED 2026-08-05, before any H2 measurement exists.**

H2 is **not** a rescue of H1 and must never be presented as one. It is a different claim about
a different property, and it was independently motivated before Step 1 ran — see
`CLAUDE_CHALLENGES.md` §4, which recorded per-edge `source_chunk_id` provenance as the only
differentiator that survived audit, while H1 was still untested.

H2 is compatible with H1 being false. Today's data supports that combination directly: prose
retrieval beat base by +0.2010 (CI excludes zero), so prose wins as the *substrate* — while the
graph independently beat base by +0.0812 (CI excludes zero), so it carries real signal that can
serve as a *check* over that substrate.

**H2's criterion is fixed here, before the measurement:** attribution accuracy (§6 protocol)
must separate TAHI from prompt-RAG with a 95% CI excluding zero at the n set by §7's power
calculation. If it does not, H2 is dead too, and TAHI's remaining claim is cost/latency —
which is not a research result and does not justify further spend.

---

## 1b. Ablation control matrix

Every arm defined before running. The load-bearing comparison is named so it cannot be
substituted afterwards for a friendlier one.

| # | arm | retrieval | representation | purpose |
|---|---|---|---|---|
| A0 | `base` | none | — | parametric floor |
| A1 | `vector_rag` | dense top-k | prose chunks | **the thing to beat** |
| A2 | `tahi_graph` | graph retrieval | triples | H1 under real retrieval |
| A3 | `oracle_vector` | perfect (gold docs) | prose chunks | prose ceiling |
| A4 | `oracle_graph` | perfect (gold docs) | triples | **graph ceiling** |
| A5 | `oracle_scrambled` | perfect (gold docs) | degree-shuffled triples | structure negative control |
| A6 | `tahi_verify` | dense top-k | prose + graph check | H2 primary |

**Load-bearing for H1: A4 vs A3.** Same documents, same generator, same prompt — representation
is the only variable. Run 2026-08-05; result above.

**Load-bearing for H2: A6 vs A1 on attribution accuracy.** A1 must be included and must be able
to score, or the metric is rigged. Prompt-RAG can cite the chunk it retrieved; that is a real
opponent.

Held constant across all arms: model, prompt template, decoding parameters, `top_k`, token
budget, question set, seed.

---

## 1c. Acceptance gates — blocking, each with a negative control

A gate that cannot fail proves nothing. Each gate below names the condition that must make it
fail; if the negative control does not trip the gate, the gate is broken and the result is void.

| # | gate | negative control |
|---|---|---|
| G1 | **No answer-key leak.** No arm receives gold answers, gold `evidence` text, or gold `evidence_relations`. Gold ids are used only to select source material. | Inject a gold answer into one arm's context; the leak assertion must fire. |
| G2 | **Arm parity.** All arms share model, prompt, decoding, `top_k`, token budget. Context token counts per arm are logged and reported. | Change one arm's encoder; the parity check must fail. |
| G3 | **Sampling integrity.** No head slices on a type-sorted file. Every sample is seeded, stratified, and its composition reported. | Request a prefix sample; the guard must refuse or flag it. |
| G4 | **Metric provenance.** Every reported metric traces to a committed function in `third_party/` or `src/tahi/eval/`. No metric authored inline for a run. | Point a run at an inline metric; the manifest check must reject it. |
| G5 | **Artifact regenerability.** Every reported number exists in a committed JSON with per-item scores. A headline with no artifact is void. | Delete the artifact; the report step must fail rather than print a remembered number. |

G1 is the sharp one. `CLAUDE_AUDIT.md` and the dashboard's fabricated `commonly_affects` edge are
the record of what happens without G5.

---

## 1d. Signal audit — detecting "built but carrying nothing"

The graph analogue of MAAILMA's §3.J adapter diagnostics (Frobenius drift, effective rank, linear
probe): tests that distinguish a graph that carries information from one that merely exists.
None requires an LLM call.

1. **Scrambled-graph delta (A5).** Degree-preserving, relation-label-preserving edge shuffle. If
   A4 ≈ A5, the *structure* contributes nothing and any A4 signal is node-name overlap.
2. **Relation concentration.** Report the share of edges carried by the top-10 relations and the
   singleton count. Current enterprise build: **3,436 distinct relations, 2,100 singletons, most
   frequent relation `mentions` (1,678)** — a large fraction of edges are near-contentless.
3. **Path availability.** Fraction of question entity pairs connected at shortest-path length
   **≥2** (distance 1 is a single edge and requires no traversal). Distribution, not a binary.
   `scripts/run_path_connectivity.py` currently reports `has_path` with no cutoff, which returns
   ≈100% inside a giant component and answers nothing — **must be fixed before it is cited.**
4. **Extraction loss accounting.** Tokens of source prose in, triples out, and what fraction of
   gold `answer_facts` survive extraction. This is the direct measurement of the H1 failure.

---

## 1e. Reasoning-intensity dose-response *(primary reported outcome, not a footnote)*

From ReasonEmbed (arXiv:2510.08252), **used as an instrument, not a component.** The encoder is
swappable by anyone and is not defensible ground; the measurement design is the contribution.

Reasoning intensity (RI) gives a computed per-question score for how much reasoning a question
requires, replacing reliance on the benchmark's own type labels. It converts a claim from one
delta into a curve:

> **Does the advantage grow with reasoning intensity?**

A flat line means the mechanism is not doing what it claims, whatever the headline says. A rising
line is a dose-response relationship, which is substantially harder to produce by accident than a
single number and is what would survive a hostile reviewer.

Applies to H2 as well as H1: attribution accuracy should hold or improve as RI rises, since
harder questions are where unverified claims are most costly.

**Cost:** local on the DGX. No API budget.

---

## 1f. Cost ladder — decision point at every rung

Spend stops at any rung that fails. Actuals recorded as they land.

| rung | work | budget | actual | gate to pass before next rung |
|---|---|---:|---:|---|
| 0 | enterprise graph build | $1 | **$0.89** | build completes, failures counted |
| 1 | Step 1 oracle (A3 vs A4) | $5 | **$0.20** | H1 ceiling measured |
| 2 | Step 4 claim-level metric | $20 | — | resolves the `token_f1` confound |
| 3 | scrambled control (A5) | $5 | — | only if H1 survives rung 2 |
| 4 | attribution protocol (A6 vs A1) | $20 | — | H2 primary |
| 5 | powered confirmatory run | $50 | — | only with a surviving hypothesis |

Rungs 3 and 5 are conditional. **If rung 2 confirms H1 is dead, rung 3 is not run** — a structure
control on a representation that already lost to prose answers a question nobody is asking.

---

## 2. Step 1 — Oracle ceiling test *(RUN 2026-08-05 — result in §11)*

The highest-information experiment available, and it had never been run.

Remove retrieval from the equation entirely and compare **representations** at their ceilings.

| arm | what it is served |
|---|---|
| `oracle_vector` | the gold evidence chunks for that question |
| `oracle_graph` | triples from **our built graph**, seeded by the gold entities |

**Critical design constraint — do not fudge this.** `oracle_graph` must be served triples that
**actually exist in `graph_clean/graph.json`**. It must NOT be served the gold
`evidence_relations` verbatim. Serving the answer key would test "does gold evidence help",
which is not the question. The gold entities are used **only** to seed perfect entity linking;
what comes back is whatever our graph actually contains about them.

This separates two failures the current design confounds:
- retrieval is bad → oracle arms score far above the retrieved arms
- the representation is bad → `oracle_graph` fails to reach `oracle_vector`

**Decides:**
- `oracle_graph` ≈ `oracle_vector` → **the representation carries no advantage.** No retriever,
  encoder, or extraction improvement can help. Thesis dead. Stop and publish.
- `oracle_graph` ≫ `oracle_vector` → thesis alive, downstream engineering justified.
- Both ≫ retrieved arms → the bottleneck is retrieval, and that is fixable.

**Artifacts:** `scripts/run_oracle_ceiling.py`, `data/graphrag_bench/oracle/oracle_results.json`
(per-question scores), manifest with seed, n, sample construction, model, cost.

---

## 3. Step 2 — Negative control: scrambled graph *(~$5, hours)*

Degree-preserving edge shuffle: keep every node's degree, keep the relation-label distribution,
randomise which nodes connect to which. Re-run the identical `tahi_graph` arm against it.

**Decides:** if the scrambled graph scores the same as the real graph, the structure contributes
nothing and any apparent win is retrieval-adjacent, not structural.

This is the first thing a skeptical reviewer asks for. Without it a positive result is not
believable — including to us. Seed recorded; shuffle script committed.

**Artifacts:** `scripts/scramble_graph.py`, `data/graphrag_bench/graph_scrambled/`,
control results with the same metric and n as the real arm.

---

## 4. Step 3 — Build the decisive subset

Stop averaging over questions where the thesis cannot apply.

Construct, from existing data at zero API cost, the subset of questions whose gold `evidence`
spans **≥2 non-adjacent chunks**. On these, a single top-k dense retrieval is structurally
handicapped — the facts are not co-located — and TAHI should win *large*, not by fractions.

**Rules:** the selection criterion is written down before the subset is built, applied
mechanically, and the resulting subset is committed. Question counts per type are reported.
No hand-picking. If the subset is too small to power a test, that is reported as a finding —
it would mean the benchmark contains almost no genuinely multi-hop questions.

**Artifacts:** `scripts/build_decisive_subset.py`, `data/graphrag_bench/decisive_subset.json`,
with the criterion and per-type counts in its manifest.

---

## 5. Step 4 — Use metrics that can detect the claim

ROUGE-L is nearly blind to what TAHI asserts. The project's own history records the failure
mode: negating every gold answer moved `fact_coverage` by 0.0000. A fluent wrong answer and a
fluent right answer score alike.

If the claim is "fewer false assertions", measure assertions:

- **Answer Correctness** — vendored, `third_party/graphrag_bench_eval/metrics/answer_accuracy.py`
- **Faithfulness** — vendored, `third_party/graphrag_bench_eval/metrics/faithfulness.py`
- **Coverage** — vendored, `third_party/graphrag_bench_eval/metrics/coverage.py`

All three are already in the repo and **have never been run**. Per `GATE1_SPEC.md` Rule 1, no
metric is written by us. ROUGE-L stays for comparability with published baselines; it stops
being the headline.

---

## 6. Step 5 — Make provenance a measured primary outcome

Provenance is the only differentiator that survived audit. Today it is asserted. Measure it.

> For each generated claim, the system names a source. **Is that source the chunk that actually
> contains the fact?**

Vector RAG can also cite its top-k chunks, so this is a fair head-to-head — and one where TAHI
should separate decisively rather than by noise. Checkable, cheap, and in a regulated domain
worth more than 3 accuracy points.

**Attribution accuracy** becomes a reported primary outcome alongside correctness, not a
marketing bullet. It competes where TAHI is strong instead of where nine other systems already
are.

### 6.1 Protocol — fixed 2026-08-05, before any measurement

**Definition.** For a generated answer A over source set S:

1. Decompose A into atomic claims `c₁…cₙ` (`src/tahi/validate/claim_extractor.py`).
2. Each arm returns, per claim, the source identifier it attributes that claim to.
3. A judge sees **only** the cited source text and the claim, and rules `supported` /
   `not_supported`. It never sees the gold answer, the other arms, or which arm produced it.
4. **attribution_accuracy** = supported citations / total claims.
5. **unattributed_rate** = claims carrying no citation / total claims. Reported alongside;
   a system can trivially maximise accuracy by citing almost nothing.

**Arms and what each can cite** — A1 is included precisely so the metric is not rigged:

| arm | citation unit | can it score? |
|---|---|---|
| `base` | none | no — floor by construction |
| `vector_rag` (A1) | retrieved chunk id | **yes** — the honest opponent |
| `tahi_verify` (A6) | graph edge → `source_chunk_id` | yes, finer granularity |
| GCCA-style dense injection | none available | **structurally cannot** |

The last row is the architectural point, and it is only credible **because A1 can score.** A
metric only TAHI can score on is marking our own homework, which is the failure this whole plan
exists to end. GCCA scoring zero is a property of injecting dense vectors into the residual
stream — there is no text span to cite — not a property of the benchmark being unfair.

**Pre-registered H2 criterion.** A6 − A1 attribution accuracy, 95% paired bootstrap CI excluding
zero, at the n fixed by §7, with `unattributed_rate` reported for both. A win on accuracy
accompanied by a materially higher `unattributed_rate` is **not** a win and is recorded as a
null.

**Why this metric and not another:** it needs no answer key, so it runs on any customer corpus
on day one — which is also what makes it the enterprise A/B instrument (§ enterprise notes).

---

## 7. Step 6 — Power the study before running it; pre-register the analysis

The N=20 pilot had a ±10-point CI against a ~3-point effect. That design could not have
detected the result even if it existed.

Before any generation run:

1. Compute the **minimum detectable effect** for the proposed n, per question type.
2. Choose n from the effect that needs to be seen — not from convenience or budget.
3. Write the analysis plan down **before** the run: arms, metrics, subset, test, alpha.
4. Do not change it afterward. Any deviation is recorded as a deviation.
5. Report **bootstrap 95% CIs** beside every point estimate, per question type. Never a bare mean.

Appendix A.2 proved this project can pre-register and be right. Apply it to the whole design.

---

## 8. Step 7 — Timebox and pre-registered kill criterion

**Budget: two weeks, ~$100.** Written down now, before any result is known.

Criteria are now per-hypothesis (§1a), because H1 and H2 have separate fates.

### H1 — substitution

**CONTINUE** requires all three:
1. `oracle_graph` beats `oracle_vector`, CI excluding zero;
2. the scrambled-graph control **fails** (real graph beats scrambled, CI excluding zero);
3. the result survives the claim-level metric, not only `token_f1`.

**Criterion 1 has already failed** (−0.1198, CI [−0.1394, −0.1011]). Step 4 is the single
permitted check, because the confound it tests was named in advance. If Step 4 confirms:

> **STOP on H1 and publish:** *"LLM-extracted triples carry less answerable content than the
> prose they were extracted from — controlled evidence at matched retrieval."*

No subset hunting, no metric swap, no expanding n for a friendlier slice. One pre-named check,
then the verdict stands.

### H2 — verification

**CONTINUE** requires: A6 − A1 attribution accuracy, CI excluding zero, at powered n, without a
materially worse `unattributed_rate` (§6.1).

**STOP** otherwise. Then TAHI's remaining claim is cost and latency, which is engineering, not a
result, and does not justify further research spend.

### The discipline this section exists to enforce

H1 failed today. The temptation is to promote H2 as though it were the plan all along. §1a
guards against that: H2 is dated, its motivation is traceable to `CLAUDE_CHALLENGES.md` §4
written *before* Step 1 ran, and its criterion was fixed before any H2 number existed.

**If H2 also fails, the honest output is that TAHI does not work and the evidence is published.**
That outcome is written here, in advance, while it is still cheap to mean it.
That is a genuine contribution, and this project has never allowed itself to finish a result.

**Ambiguous outcomes are reported as ambiguous.** No re-running until a favourable number
appears. If the analysis plan is run twice, both runs are reported.

---

## 9. Prerequisite finding that constrains everything

`data/graphrag_bench/graph_clean/evidence_recall_stratified.json`: overall stratified evidence
recall is **29.55%** (N=100, 25/type); Contextual Summarize is **8.44%**.

The graph contains roughly 30% of the facts the benchmark requires. This is the ceiling on every
retrieved arm. Per `GATE1_SPEC.md` §2.4 this gates Step 3 and has not been ruled on.

**Implication for this plan:** the oracle test (§2) is unaffected — it measures the ceiling of
what the graph *does* contain, which is exactly the right question. But no retrieved-arm result
should be treated as a test of the thesis until recall is materially higher. **Extraction recall
is a Step 1 problem and gets fixed before any further retrieved-arm spend** — and only if §2
says the representation is worth it.

---

## 10. Order of work

Revised 2026-08-05 after Step 1. Ordering is now conditional, not sequential.

| # | step | cost | status | decides |
|---|---|---:|---|---|
| 1 | Oracle ceiling A3 vs A4 (§2) | $0.20 | **DONE** | H1 ceiling — **failed**, −0.1198 |
| 2 | Claim-level metric (§5) | ~$20 | **NEXT** | whether −0.1198 is content loss or a `token_f1` artifact |
| 3 | Attribution protocol A6 vs A1 (§6.1) | ~$20 | queued | **H2 primary** |
| 4 | Path availability + relation concentration (§1d) | $0 | queued | whether the graph can support traversal at all |
| 5 | Scrambled control A5 (§3) | ~$5 | **conditional** | run only if step 2 rescues H1 |
| 6 | Decisive subset (§4) | $0 | **conditional** | run only if step 2 rescues H1 |
| 7 | RI dose-response (§1e) | $0 (local) | queued | whether any surviving advantage scales with reasoning demand |
| 8 | Powered confirmatory run (§7) | ~$50 | conditional | only with a surviving hypothesis |
| 9 | Decide (§8) | — | — | continue, or publish the null |

**Step 2 is the fork.** It resolves H1 and it costs $20.

Steps 5 and 6 exist to strengthen H1 and are now conditional on H1 surviving step 2. Running a
structure control on a representation that already lost to prose would be answering a question
nobody is asking — and spending to look busy after an unfavourable result is exactly the habit
this plan exists to break.

Steps 3, 4 and 7 proceed regardless: H2 and the signal audit are independent of H1's fate.

---

## 11. Run Log

Append one entry per step: date, step, command, artifact path, outcome, and whether the plan
changed as a result. Failures and blocks are recorded here identically to successes.

| date | step | outcome | artifact |
|---|---|---|---|
| 2026-08-06 | **H2 — A6 with candidate-set parity: VERDICT** | **NULL.** n=150, 891 claims. `vector_rag_cite` 0.7125 · `tahi_dense` **0.7265**. Delta **+0.0141, CI [−0.0404, +0.0690] — includes zero.** `unattributed_rate` 0.1623 vs 0.0711 (−0.0912, CI excludes zero — TAHI better). Decomposed: TAHI cites 92.9% at 78.2% precision; prompt-RAG cites 83.8% at 85.1%. Equal net accuracy, different trade-off. **The earlier −0.3277 was a candidate-set confound in the harness (403 docs vs 2.81), not a property of TAHI.** Per §8, CI-includes-zero is a NULL, not a trend. **H2 STOPS.** | `data/enterprise_rag/verify_parity/verify_results.json` |
| 2026-08-06 | **PROGRAMME VERDICT** | **STOP.** H1 dead twice (Aug 2 pre-registered null n=170 full corpus; Aug 5 oracle ceiling −0.1198). H2 null at parity. What survives is engineering, not a result: mechanical edge-level citation matching an LLM self-citation baseline at equal accuracy and better coverage. Per §8 that does not justify further research spend. Carry the citation mechanism into MRAG's attribution layer as a cheaper implementation of a solved problem, not as a differentiator. | this file |
| 2026-08-05 | Step 1 — enterprise graph build | **RUNNING.** 170 structural-pool questions → 403 gold docs (all located on disk, 0 missing) → 803 chunks. Concurrency 12, timeout 120s, 3 retries. Smoke test on 3 docs: 99 nodes / 93 edges / $0.0042, no failures. | `scripts/build_enterprise_graph.py`, `data/enterprise_rag/graph_gold/` |
| 2026-08-05 | **Step 1 — enterprise oracle: RESULT** | **UNFAVOURABLE.** n=150 structural pool. `base` 0.3132 · `oracle_vector` **0.5142** · `oracle_graph` **0.3944**. Graph − vector = **−0.1198**, 95% CI [−0.1394, −0.1011], **excludes zero**. Loses on all 5 question types (−0.094 to −0.171). Graph beats prose on **13/150** questions. Zero questions had empty graph context; mean 147.5 triples served. 0 generation errors. Cost $0.20. | `data/enterprise_rag/oracle/oracle_results.json` |
| 2026-08-05 | Step 1 — enterprise graph build | **COMPLETE.** 403 gold docs → 803 chunks → 21,480 nodes / 20,937 edges. $0.89, 952s, concurrency 12. Failures counted not dropped: 0 API errors, 13 JSON parse failures, 4 chunks yielding zero triples. 3,436 distinct relations, **2,100 singletons**; most frequent relation is `mentions` (1,678). | `data/enterprise_rag/graph_gold/manifest.json` |
| 2026-08-05 | Step 1 — medical oracle | **BLOCKED** (§0 rule 7). GraphRAG-Bench Medical gold `evidence` is *paraphrased, not quoted*: only **2 of 200** evidence strings appear verbatim in `medical_corpus.json`. Gold chunks therefore cannot be located by containment, and the token-overlap fallback fired on **12/12** smoke items. No medical oracle number is reported. A validated evidence→chunk mapping is required first. | `scripts/run_oracle_ceiling.py` (`build_medical_items`) |

### Consequence of the medical block

Two things follow, both recorded rather than worked around:

1. **Enterprise is the sound venue for Step 1.** Its `expected_doc_ids` are explicit document
   identifiers — no matching, no ambiguity, nothing to approximate.
2. **The 29.55% evidence recall carries a new caveat.** If gold evidence is synthesized
   paraphrase rather than corpus text, part of that shortfall may be the graph failing to
   contain *paraphrases* rather than failing to contain *facts*. This does not invalidate the
   number; it changes what it licenses us to conclude, and it must be stated wherever the
   number is cited.
