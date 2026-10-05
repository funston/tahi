# TAHI — status

_2026-08-06_

## What TAHI is

A knowledge graph consulted while an LLM answers, so the model does not assert entities the
graph cannot support. Two mechanisms put the graph inside the generation loop, plus one that
runs after it.

| mechanism | module | where it acts |
|---|---|---|
| logit constraint | `tahi.validate.constrained.GraphConstrainedLogits` | every decode step |
| gated cross-attention | `tahi.native.gcca_layer.GatedCrossAttention` | hidden states, per forward pass |
| post-generation correction | `tahi.graph.metaqa_graph.MetaQAGraph` + diff loop | after a complete answer exists |

---

## Benchmark

**MetaQA 3-hop.** 134,741 triples, 9 relations, 14,274 held-out test questions.

- The KB is the dataset's ground truth. Nothing is extracted, so extraction quality is not a
  variable in these numbers.
- Answers are entity lists. Scoring is exact set equality — no LLM judge.
- The RAG corpus is the same KB written out as sentences, one document per subject entity.
  The text arm and the graph arm hold identical information; the only difference is access
  method, similarity search versus traversal.

`data/metaqa/kb.txt`, `data/metaqa/qa_3hop_test.json`.

**EnterpriseRAG-Bench Level 3.** 500 questions, 10,000 documents, 20,666 edges, in-process
PyTorch, Qwen2.5-1.5B-Instruct. `data/enterprise_rag/questions.jsonl`.

---

## Results

All MetaQA runs: n = 100, seed 0, exact set match.

### Post-generation correction — `scripts/metaqa_loop_tahi.py`

gpt-4o-mini · BGE-large-en-v1.5 · top-10 · max 3 rounds · `MetaQAGraph.walk`

**w/o TAHI** — the model answers on its own, nothing added. **with TAHI** — same model, same prompt, same everything, except TAHI blocks it from naming anything the graph does not contain.

| how the query is derived | w/o TAHI | with TAHI, one pass | with TAHI, repeat to stable | fixed | broken | McNemar |
|---|---:|---:|---:|---:|---:|---|
| few-shot, 3 worked examples | 0.020 | 0.690 | **0.790** | 77 | **0** | p = 0.0000 |
| `--enumerate`, no examples, all 9³ chains | 0.020 | 0.530 | **0.590** | 57 | **0** | p = 0.0000 |

Rounds used: `{0:5, 1:80, 2:15}` few-shot, `{0:3, 1:84, 2:10, 3:3}` enumerate.

`--enumerate` traverses all 729 relation chains with no LLM and no worked examples, then the
model picks a result set. It removes the template dependency in limit 3 at a cost of 20 points.

The correction hands back only what is provably wrong, never the answer:

```
- NOT in the graph, remove: <asserted, unsupported>
- IN the graph, you omitted: <supported, unasserted>
```

### In-generation logit constraint — `scripts/metaqa_ingen_tahi.py`

Qwen2.5-1.5B-Instruct, local, bf16 · `GraphConstrainedLogits`

| | exact set match |
|---|---:|
| w/o TAHI — the model answers on its own | 0.000 |
| with TAHI — same model; TAHI blocks any entity the graph does not support | **0.370** |

37 fixed, **0 broken**, McNemar exact p = 0.0000.
**Mean intervention rate 0.440** — the share of decode steps where the constraint overrode the
model's own argmax. No graph text enters any prompt; there is no second generation.

**Disclosure.** This arm reuses relation chains from `verify_results.json` via `--chains-from`.
Those chains were derived by the few-shot prompt running on gpt-4o-mini, not by the 1.5B doing
the generating. Holding chain derivation fixed is deliberate — it isolates the injection
mechanism — but it means this arm inherits the template dependency in limit 3 and borrows a
stronger model for the query step. **0.370 is an upper bound on what this model could reach
end-to-end unaided.**

### In-generation gated cross-attention — `benchmarks/run_l3_native.py`

500 questions · 7 GCCA blocks, interleave 4, max 16 slots · `checkpoints/gcca/gcca_epoch14.pt`

| | exact | token F1 | fact coverage | unsupported rate |
|---|---:|---:|---:|---:|
| w/o TAHI | 0.036 | 0.075 | 0.017 | 1.000 |
| with TAHI, gate off (α = 0, a wiring check) | 0.036 | 0.075 | 0.017 | 1.000 |
| with TAHI, trained | 0.038 | 0.063 | 0.011 | 0.909 |

Identity control passes with 0 mismatches — the α = 0 arm reproduces base exactly, so the
wiring is correct. **Trained GCCA moves exact match +0.002 and moves fact coverage down.**
This mechanism does not work.

`benchmarks/results/l3_native_run.json`.

### Traversal diagnostics, same 100 chains, both implementations

| | `MetaQAGraph.walk` | `metaqa_verify.traverse` |
|---|---:|---:|
| gold answers fully contained | 0.790 | 1.000 |
| set equals gold exactly | **0.790** | 0.530 |
| mean candidate set size | 11.1 | 12.3 |

`MetaQAGraph.walk` forbids revisiting a node within a path. That yields a smaller candidate
set on 55 of 100 questions and never a larger one. Across those 55 it drops 70 non-gold
entities and 51 gold ones. Under exact-set-match scoring the trade is strongly positive:
end-to-end loop accuracy on those 55 questions is 0.636 against 0.164.

**The loop's end-to-end accuracy (0.790) equals the traversal's exact-match rate (0.790).**
The correction loop drives the model to transcribe the supported set, so accuracy tracks
traversal precision 1:1 and the model contributes nothing beyond transcription.

### Legend — a knowledge model as a decode-time constraint — `scripts/legend_ingen.py`

366 `.pure` source files from `finos/legend-engine`, parsed by `tahi.graph.legend_model` into
756 classes and 560 distinct property names. Nothing is extracted or inferred — this is a parse
of the file legend-engine itself compiles.

Question, asked 100 times: *what properties does class X declare?* The answer is in the file,
so scoring is exact set comparison with no judge. TAHI's allowed set is **every property name
in the whole model**, not the target class's own — constraining to the answer would be an
oracle.

Qwen2.5-1.5B-Instruct, local.

| | w/o TAHI | with TAHI |
|---|---:|---:|
| exact property-set match | 0.000 | 0.000 |
| **made-up names written down** | **0.631** | **0.000** |
| answers containing a made-up name | 0.770 | 0.000 |

Left alone, 63% of the property names the model writes exist nowhere in the model — it emits
`output_name`, `is_idempotent`, `inverse_name`, plausible-looking and wrong (Legend uses
camelCase). With TAHI it cannot write them at all.

**It never names the right properties either.** TAHI supplies vocabulary, not knowledge. Here
the allowed set is 560 names and the answer is roughly 4 of them — too wide to help it choose,
unlike MetaQA where a traversal narrowed it to ~11.

An earlier run showed 0.009 made-up names with TAHI on. All 12 cases were the final item and
each was a prefix of a real name (`join`/`joins`, `isChildren`/`isChildrenExecutionParallelizable`)
— generation hit the token budget mid-identifier. Not a constraint failure. The script now
detects non-EOS termination and drops the partial tail.

`data/legend/results/legend_ingen.json`.

---

## Limits

1. **The MetaQA graph is dataset ground truth.** Extraction quality is untested. LLM
   extraction on enterprise prose scores −0.12 against its own source documents.
2. **Nine relations.** The chain-derivation step is not shown to survive a schema with
   hundreds of relation types. Enumeration is O(|R|³).
3. **Few-shot examples carry most of the retrieval lift.** Gold coverage by prompt variant:
   schema only 0.02; + "the same relation walks both ways" 0.26; + 3 worked examples 0.92.
   `--enumerate` removes them entirely and costs 20 points (0.790 → 0.590). The in-generation
   arm inherits this dependency — see the disclosure above.
4. **Seed entity is given, not linked.** `q_entity` comes from the dataset in every arm.
5. **RAG baseline is 2%.** Two weak systems are being compared, not a strong baseline against
   a stronger one.
6. **Published MetaQA 3-hop:** GraftNet 77.7, PullNet 91.4, EmbedKGQA 94.8.
7. **Single seed.** Every number is seed 0, n = 100.
8. **Graph expansion in `world_state.py` does not change retrieval.** Expanded candidates are
   scored `own_cosine × seed_score × decay` and lose every slot to unscaled dense hits.
   `tests/test_graph_retrieval.py` has 3 failing tests that assert otherwise.
9. **Traversal recall is 0.790, not 1.0.** On 21% of questions the walk cannot reach a gold
   answer. That is the hard ceiling on the post-generation loop.
10. **`third_party/graphrag_bench_eval/` has never been run.**

---

## Repository

```
src/tahi/
  validate/constrained.py     GraphConstrainedLogits — logit masking
  graph/metaqa_graph.py       MetaQA loader, bidirectional typed walk
  graph/kuzu_store.py         Kùzu property graph store
  graph/gnn_encoder.py        RGAT encoder
  native/gcca_layer.py        gated cross-attention
  native/huggingface_adapter.py, memory.py, memory_store.py
  eval/                       metrics, NLI, stats, manifests
  world_state.py              vector + graph retrieval

scripts/
  metaqa_loop_tahi.py         post-generation correction        0.02 -> 0.79
  metaqa_ingen_tahi.py        in-generation logit constraint    0.00 -> 0.37
  metaqa_verify.py            pre-generation prompt stuffing    0.01 -> 0.18
  metaqa_loop_tahi.py --enumerate                                   0.02 -> 0.59
  probe_graph_query.py        no-LLM retrieval ladder

benchmarks/
  run_l3_native.py            EnterpriseRAG-Bench L3, GCCA arms

data/metaqa/results/*.json    per-question rows for every number above
benchmarks/results/*.json
```

Test suite: 115 passed, 3 failed (the graph-expansion assertions in limit 8).

---

## Regenerate

```bash
.venv/bin/python scripts/metaqa_loop_tahi.py  --n 100 --seed 0   # 0.02 -> 0.79
.venv/bin/python scripts/metaqa_ingen_tahi.py --n 100 --seed 0   # 0.00 -> 0.37
.venv/bin/python scripts/metaqa_verify.py     --n 100 --seed 0   # 0.01 -> 0.18
.venv/bin/python benchmarks/run_l3_native.py                     # GCCA arms
```

`OPENAI_API_KEY` required for the first and third. The second and fourth are local.

---

## Next

1. Seeds 1–4 on the post-generation loop.
2. Run the loop on a graph extracted from text rather than supplied by the dataset.
3. Replace chain derivation with a method that does not scale as O(|R|³).
4. Run `third_party/graphrag_bench_eval/`.

How the code works: `docs/TAHI_ARCHITECTURE.md`.
