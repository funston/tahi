# TAHI

A knowledge graph consulted while an LLM answers, so the model does not assert entities the
graph cannot support.

---

## Mechanisms

| | module | where it acts |
|---|---|---|
| **Logit constraint** | `tahi.validate.constrained.GraphConstrainedLogits` | masks logits at every decode step; entities the graph does not support are unreachable |
| **Gated cross-attention** | `tahi.native.gcca_layer.GatedCrossAttention` | projects a graph memory tensor into hidden states, gated by `tanh(α)` |
| **Post-generation correction** | `tahi.graph.metaqa_graph.MetaQAGraph` + diff loop | traverses the graph, hands back only what is provably wrong, asks again |

---

## Benchmark

MetaQA 3-hop: 134,741 triples, 9 relations, 14,274 held-out questions. Answers are entity
lists, so scoring is exact set equality with no LLM judge. The KB is the dataset's ground
truth, so extraction quality is not a variable.

The RAG corpus is that same KB written out as sentences. Text arm and graph arm hold identical
information; the only difference is access method.

---

## Results

n = 100, seed 0, exact set match. **w/o TAHI** — the model answers on its own, nothing added.
**with TAHI** — same model, same prompt, same everything, except TAHI blocks it from naming
anything the graph does not contain.

| | w/o TAHI | with TAHI | fixed | broken | McNemar |
|---|---:|---:|---:|---:|---|
| Post-generation correction, loop to stable | 0.020 | **0.790** | 77 | **0** | p = 0.0000 |
| Post-generation, 1 round | 0.020 | 0.690 | 67 | **0** | p = 0.0000 |
| Post-generation, **no few-shot examples** (`--enumerate`) | 0.020 | **0.590** | 57 | **0** | p = 0.0000 |
| In-generation logit constraint | 0.000 | **0.370** | 37 | **0** | p = 0.0000 |
| Pre-generation prompt stuffing | 0.010 | 0.180 | 17 | **0** | p < 0.0001 |

Rows 1, 2, 3 and 5 use gpt-4o-mini with BGE-large-en-v1.5; w/o TAHI there is ordinary dense
retrieval. Row 4 is a local Qwen2.5-1.5B-Instruct with no retrieval at all, and a **mean
intervention rate of 0.440** — the share of decode steps where TAHI overrode the model's own
top choice.

**Nothing has ever turned a correct answer wrong.**

### Gated cross-attention does not work

EnterpriseRAG-Bench Level 3, 500 questions, trained 15 epochs:

| | exact | token F1 | fact coverage |
|---|---:|---:|---:|
| w/o TAHI | 0.036 | 0.075 | 0.017 |
| with TAHI, gate off (a wiring check) | 0.036 | 0.075 | 0.017 |
| with TAHI, trained | 0.038 | 0.063 | 0.011 |

With the gate off it reproduces the plain model exactly, 0 mismatches, so the wiring is right.
Trained, it moves exact match +0.002 and moves fact coverage down.

### Legend — a knowledge model as the constraint

366 `.pure` files from `finos/legend-engine`, parsed into 756 classes and 560 property names.
Nothing extracted — a parse of the file legend-engine compiles. Asked 100 times: *what
properties does class X declare?* The answer is in the file, so scoring is exact.

| | w/o TAHI | with TAHI |
|---|---:|---:|
| exact property-set match | 0.000 | 0.000 |
| **made-up names written down** | **0.631** | **0.000** |

Left alone, 63% of the property names it writes exist nowhere in the model. With TAHI it cannot
write them. It still never names the right ones — TAHI supplies vocabulary, not knowledge.

---

## Diagnostics

Same 100 chains through both traversal implementations:

| | `MetaQAGraph.walk` | naive traversal |
|---|---:|---:|
| gold answers fully contained | 0.790 | 1.000 |
| set equals gold exactly | **0.790** | 0.530 |
| mean candidate set size | 11.1 | 12.3 |

`MetaQAGraph.walk` forbids revisiting a node within a path, giving a smaller candidate set on
55 of 100 questions and never a larger one. It trades recall for precision — across those 55 it
drops 70 non-gold entities and 51 gold ones — and under exact-set-match scoring the trade wins:
0.636 against 0.164 end-to-end on that subset.

**End-to-end loop accuracy (0.790) equals the traversal's exact-match rate (0.790).** The
correction loop drives the model to transcribe the supported set; the model contributes nothing
beyond transcription, and traversal precision is the ceiling.

Prompt shape is worth more than the graph: identical graph, query, model and candidates score
0.18 as a candidate list and 0.79 as a diff of errors.

---

## Limits

1. The MetaQA graph is dataset ground truth. Extraction is untested; LLM extraction on
   enterprise prose scores −0.12 against its own source documents.
2. Nine relations. Chain derivation by enumeration is O(|R|³) and does not scale.
3. Few-shot examples carry most of the retrieval lift: gold coverage is 0.02 from the schema
   alone, 0.26 with a bidirectionality hint, 0.92 with three worked examples. The
   `--enumerate` arm removes them entirely and costs 20 points (0.79 → 0.59).
4. Seed entity is supplied by the dataset. No entity linking is performed.
5. RAG baseline is 2%.
6. Published MetaQA 3-hop: GraftNet 77.7, PullNet 91.4, EmbedKGQA 94.8.
7. Single seed, n = 100.
8. Graph expansion in `world_state.py` does not change retrieval results.
9. Traversal recall is 0.790, not 1.0 — 21% of questions have a gold answer the walk cannot
   reach. That is the hard ceiling on the post-generation loop.
10. Prior work: KiRAG (Fang, Meng & MacDonald, ACL 2025) does iterative knowledge-triple
   retrieval with reasoning inside the retrieval loop.

---

## Next

1. Seeds 1–4 on the post-generation loop.
2. Run the loop on a graph extracted from text rather than supplied by the dataset.
3. Replace chain derivation with a method that is not O(|R|³).

Methodology and regeneration commands: `docs/STATUS.md`.
Integration with an existing knowledge graph: `docs/TAHI_INTEGRATION.md`.

How the code works: `docs/TAHI_ARCHITECTURE.md`.
