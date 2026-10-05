# TahiRetro — what we are building

_Authoritative as of 2026-08-17. Supersedes the Level 3 / GCCA description in `POC.md`
and everything in `docs/legacy/`._

---

## The one sentence

**Keep the model frozen, and let it re-aim retrieval while it is writing — every 64
generated tokens, keyed on the text it just produced, injected into the residual
stream instead of the prompt.**

Concretely: as the model generates, every 64 tokens it hits a boundary. At that
boundary we take what it just wrote, use that as a query against the world model, and
pull back the closest nodes. Those nodes are cross-attended into hidden states partway
up the layer stack. The context window never sees any of it.

The retrieval substrate is Tahi's graph — vector search seeds entity nodes, typed edges
expand to neighbours — rather than RETRO's flat text chunks. That substitution is the
Tahi half. The 64-token schedule is the RETRO half. Neither alone is the thing.

## What makes it different from what already exists

| | prompt-RAG | one-shot injection | **TahiRetro** |
|---|---|---|---|
| Where retrieval enters | prompt window | intermediate layers | intermediate layers |
| **When** | once, at step 0 | **once, at step 0** | **every 64 tokens** |
| Query is | the question | the question | **the last 64 tokens written** |
| Retrieved unit | text chunk | graph nodes | graph nodes + edge expansion |
| Resident memory | O(L) | O(1) | O(1) |
| Serving | off-the-shelf | off-the-shelf | custom decode loop |

The middle column is what the 2026-08-04 benchmark measured. It differs from prompt-RAG
in *where* only, and InstructRetro's own result says *where* alone buys little. The bet
has always been the **When** row.

## Why the mechanism should win

Single-shot retrieval cannot fetch what the question does not name. Take the hidden
bridge entity:

> *"What is the capital of the country where the author of [book X] was born?"*

Query on the question and you retrieve about the book. You cannot retrieve the author's
birth country, because you do not yet know the author. Re-aim at token 64 — after the
model has written "the author is **Neruda**" — and hop 2 becomes reachable.

`examples/tahiretro_chunked_demo.py` shows exactly this on a real `WorldModel`: the
hop-2 node is first retrieved at boundary 1, never at boundary 0.

## The mechanism, precisely

Sequence split into chunks of `m = 64`. Bank `u` is retrieved from chunk `u`'s own
tokens. It may be attended **only** by positions at or after `u*m + m - 1` — the last
token of chunk `u`, the first token whose prediction may legally depend on all of
chunk `u`. Positions `[0, m-1)` attend nothing.

```
H_out = H + tanh(alpha) * CrossAttention(LayerNorm(H_u^+), W_k E_u, W_v E_u)
```

Off by one chunk and the model attends a retrieval keyed on text it has not written
yet. That inflates every downstream score and is **invisible in the metric** — which is
why `tests/test_chunked_gcca.py` asserts the alignment by perturbing a bank and diffing,
not by reading the reshape.

Chunks are counted from absolute position 0, **including the prompt**. Counting over
generated tokens alone puts decode on a different grid than teacher forcing whenever
the prompt is not a multiple of `m`; `chunking.active_query_chunk` is the single source
of truth for both.

Frozen base model. Trainable: `W_k`, `W_v`, the block LayerNorm and the scalar gate
`alpha` per GCCA block, attached every 4th layer. Identity at init comes from zeroing
either `alpha` or `W_v` — `wv-zero` is preferred, see the MAAILMA section — so an
untrained adapter is bit-exact identity and the bridge must be *learned* open.

## What is in the repo now

Tier 1 of `docs/retro-v2-falsification-plan.md` — the mechanics — is **built and
passing**, hermetically on CPU.

| file | what it is |
|---|---|
| `src/tahi/native/chunking.py` | the causal offset as data — no torch, no model |
| `src/tahi/native/gcca_layer.py` | GCCA driven by the plan; `[B,L,K,d]` banks |
| `src/tahi/native/chunked_decode.py` | the custom decode loop; re-aims on the absolute chunk grid |
| `src/tahi/native/chunk_retriever.py` | boundary retrieval: graph, flat control, static control |
| `src/tahi/native/huggingface_adapter.py` | freezes base, attaches GCCA every 4th layer, per-block diagnostics |
| `tests/test_chunking.py` | 596 property cases on the offset |
| `tests/test_chunked_gcca.py` | 22 tests — identity, causality, O(1), schedule, init modes |
| `examples/tahiretro_chunked_demo.py` | boundary trace on a real `WorldModel` |

Verified properties:

- **`alpha = 0` is bit-identical to the base model**, end to end through the chunked
  loop with retrieval firing at every boundary. `torch.equal` on tokens and per-step
  logits, not `allclose`.
- **No causal leak.** Bank `u` changes nothing before `u*m + m - 1`, and does change
  its own window (so it is not merely inert).
- **O(1) resident memory.** One bank is resident during generation whatever the
  position; only the query *count* scales.
- **The query is the generated text, on the absolute chunk grid.** Each boundary's
  query is asserted equal to the decoded source chunk `[u*m, (u+1)*m)` of
  prompt-plus-generated — the exact line the old arm got wrong, now counted the same
  way the teacher-forced path counts it.
- **Decode and teacher forcing agree chunk for chunk.** Asserted directly against
  `build_chunk_banks`, so an adapter is never trained on one grid and run on another.
- **Identity holds under both init modes**, and each has a negative control that
  perturbs the factor that mode actually zeroes.

## What is not built

**Tier 2 — the decisive experiment.** Nothing below has been run, and no accuracy claim
should be made until it has.

- Adapter training under the chunked schedule (banks per chunk, salient-span masking,
  20% distractors). `scripts/train_gcca.py` still trains against a single static bank.
- A multi-hop evaluation set with hidden bridge entities. `data/enterprise_rag` is
  single-shot QA and, per the falsification plan §4, has **no discriminating power**
  even with the mechanism correct.
- **Iterative/agentic RAG as the baseline.** Plain prompt-RAG is not the competitor.
  The win condition is *iterative-RAG quality at single-shot cost*.
- Single-hop control (PopQA/TriviaQA). TahiRetro should win on multi-hop and **tie** on
  single-hop. Winning on both is a confound, not the mechanism.
- Generation long enough to re-aim. Call `assert_schedule_is_expressible()` on the run
  shape first: at `m = 64`, answers must run to several hundred tokens or the schedule
  collapses to one-shot regardless of the architecture.

### Blocker: graph expansion has three failing tests

`tests/test_graph_retrieval.py` has three long-standing failures against
`WorldModel._expand` (`test_edges_produce_candidates`,
`test_expansion_is_selective_not_exhaustive`,
`test_graph_retrieval_beats_vector_only_on_two_hop`). The `tahiretro_graph` arm routes
every boundary through that code path.

Expansion is **not** globally inert — on the demo world model, `expand=True` and
`expand=False` return different nodes for 2 of 3 boundary queries. But "different" is
not "correct", and the third failing test is specifically two-hop recall, which is the
property the whole thesis rests on. **Fix these before running the graph arm**, or a
graph-vs-flat comparison measures a bug.

`tahiretro_flat` is unaffected and can be run first.

### Arms for the Tier 2 run

| arm | schedule | substrate | role |
|---|---|---|---|
| `base` | none | — | floor |
| `rag_prompt` | once | text in prompt | standard baseline |
| `iterative_rag` | continuous | text in prompt | **the real competitor** |
| `oneshot_inject` | once | graph, layers | reproduces the 2026-08-04 arm |
| `tahiretro_flat` | **every 64** | text chunks, layers | isolates schedule |
| `tahiretro_graph` | **every 64** | graph + expansion, layers | the thesis |

`tahiretro_flat` exists so schedule and substrate vary independently. Without it a win
cannot be attributed and the result answers no question anyone asked.

## What the MAAILMA project already settled

`/home/rich/share/work/maailma` is a sibling implementation of this same
architecture — RETRO-v2 Stage 1/2, frozen Qwen, GCCA every 4th layer, 64-token
chunks — and it is months ahead. Its measured results are load-bearing here and
several were direct bugs in the first cut of this code.

### Adopted, and now in the code

| finding | where it landed |
|---|---|
| **Chunk geometry belongs in a dependency-free module**, so the causal rule is property-tested with no model loaded rather than read out of a tensor reshape | `src/tahi/native/chunking.py`, `tests/test_chunking.py` (596 cases) |
| **Incremental decode must track absolute position.** A plan built for the prompt describes position 0; under a KV cache every span falls outside the one-token window and cross-attention silently does nothing. MAAILMA measured **EM 0.250 → 1.000** on one checkpoint from this alone | `window_plan` / `active_query_chunk`, threaded through `set_retrieved_memory(..., plan=)` |
| **Never repair NaN in the gated path.** `h + 0.0 * x == h` exactly in IEEE-754, so identity survives while the path is genuinely exercised — and a NaN propagates and gets caught. The first cut called `torch.nan_to_num`, which would have hidden exactly the bug the identity gate exists to find | `gcca_layer.forward`; absent banks are now skipped via the plan, so no NaN arises |
| **`W_v = 0` beats `α = 0` for the identity init.** Identity needs the *product* to vanish. Under `α = 0` both `∂L/∂W_k` and `∂L/∂W_v` are **exactly** zero — they carry a factor of `tanh(α)` — so the bridge cannot learn until α has bootstrapped through the main loss. Measured on Qwen2.5-0.5B: grad norm at step 0 **0.185 → 0.641**, final `ΔW_k` drift **0.94 → 2.08**, and the ramp hyperparameter disappears | `set_identity_mode("wv-zero", alpha=0.3)` |
| **The negative control must perturb what is actually zeroed.** Under `wv-zero`, moving α no longer breaks identity, so an α-perturbing control passes forever | `test_negative_control_for_wv_zero_perturbs_w_v_not_alpha` |
| **`contribution = ‖tanh(α)·CCA(H)‖ / ‖H‖`** distinguishes a shut gate from a gate open onto useless memory. α alone cannot | `GatedChunkedCrossAttention.last_contribution`, `adapter.contributions()` |
| **A run whose generation is shorter than a chunk cannot express the schedule.** MAAILMA's QA pairs tokenised to 38–52 tokens, landed entirely in `C_0` which never retrieves, and *every* gradient vanished — training was vacuous and silent | `assert_schedule_is_expressible()` |

That last one retro-diagnoses the 2026-08-04 run a second time. Its arms generated
a mean of **9.8–18.4 tokens** at `chunk_size=64`. Even with the schedule correctly
implemented, retrieval could not have re-aimed once during generation. The run had
two independent reasons to be null before the substrate is even discussed.

### Not yet adopted — open work, with the measured reason

1. **Cross-attention wants token-level states, not pooled vectors.** MAAILMA feeds
   `(b, k·2m, d_ret)` — at k=2, m=64 that is **256 token positions** per bank,
   re-encoded on GPU from the neighbour span plus its continuation. Tahi feeds
   **16 pooled sentence-transformer vectors**, one per graph node. Their retrieval
   log is blunt about why this matters: mean pooling dilutes exactly the rare
   tokens that carry answers, and *"every fix that kept the pooling and reweighted
   it gained ~1 pp, while the two that bypassed it entirely gained ~9 pp each.
   When compression is the bottleneck, go around it."* This is very likely a
   second, independent reason the 2026-08-04 arm moved nothing, and it is
   orthogonal to the schedule. **Highest-value change not yet made.**

2. **Borrow `W_Q`/`W_O` from the frozen layer's self-attention.** Tahi allocates a
   full `nn.MultiheadAttention` per block — trainable `in_proj` (q,k,v) *and*
   `out_proj`. MAAILMA borrows Q/O from the host layer and trains only
   `W_k`, `W_v`, LayerNorm and α: **0.32%** of base params, against a measured
   **3.62%** (0.5B) / **4.90%** (14B) for freshly allocated Q/O. Tahi's README
   claims "<2% trainable overhead" and the current layer does not meet it.

3. **The retrieval relation is wrong, and this is the deep one.** GCCA at
   generation time queries with `C_{i-1}` and needs **continuation** — "does this
   chunk follow this text". Standard retrievers score **relevance** — "does this
   passage answer this query". MAAILMA measured the gap: question→passage R@3
   **0.649**, continuation R@3 **0.218**, on the same index. Worse, a
   cross-encoder reranker *helped* the question relation (**+9.4 pp**) while
   *hurting* continuation (**−6.7 pp**) — an improvement on the dashboard that
   degrades what the architecture actually consumes.

   `WorldModelChunkRetriever` calls `WorldModel.retrieve`, a pure relevance
   retriever, and feeds it a continuation query. **This is Tahi's clearest
   opportunity, not just a defect.** A typed edge from the entity the model just
   wrote to its graph neighbours is structurally "what comes next", which is the
   continuation relation expressed without text similarity at all. If the graph
   substrate wins anywhere, this is where — and it is testable directly, by
   scoring continuation R@k for graph expansion against flat dense retrieval on
   the same corpus, with no adapter trained and no GPU.

4. **EM is unusable as the metric.** MAAILMA: at 2–6 hits per 200 pairs, EM's
   standard error swamps every effect; it scored the best-NLL checkpoint at the
   parametric floor. Metric of record is **held-out gold-answer NLL** (continuous,
   teacher-forced, needs no generation, and is what training optimises), with
   token F1 second. Their trained bridge moved gold NLL **4.90 → 2.52** (2.38
   nats) while EM stayed pinned at 0.0100 across all three arms. Tahi's
   2026-08-04 run reported EM at 0.030–0.038 — 15–19 hits in 500 — and drew a
   program-level conclusion from it.

5. **Their three-arm attribution design.** `no retrieval` / `oracle chunk +
   random bridge, gate open` / `oracle chunk + trained bridge`. The middle arm is
   what makes a result attributable: a random bridge with α at the trained value
   sits at the floor, so any gain belongs to the learned `W_k`/`W_v` rather than
   to the gate being open or the residual stream being perturbed. Worth copying
   verbatim into the Tier 2 arm table.

6. **Retrieval quality is a separate axis, and hybrid beats dense.** BM25 alone
   (0.578) beat their neural encoder (0.550); hybrid score-fusion reached 0.649.
   Their ceiling — answer present in any single chunk — was 0.889.

7. **Rank bottleneck.** `W_k` maps `d_ret → d_model`, so its image is at most
   `d_ret`-dimensional inside the key space. At Tahi's d_ret=384 into a 1536-wide
   model that is 25%. If the bridge plateaus with `W_k` already spanning its full
   384 dimensions, the fix is a wider retriever, not more training.

## First measurement: continuation vs relevance (2026-08-17)

`scripts/eval_continuation.py`, 200 MetaQA 3-hop questions → 600 boundary items
(200 relevance, 400 continuation), k budget identical across arms.
Artifact: `benchmarks/results/continuation_eval.json`.

Answer recall@5. Worst-case SE 3.5 pp (relevance) and 2.5 pp (continuation), so
anything under ~7 pp is noise.

| arm | relevance@5 | continuation@5 |
|---|---:|---:|
| flat-A (one fact per passage) | 0.835 | 0.253 |
| **flat-B (one entity per passage)** | **0.980** | **0.890** |
| graph-B (flat-B + Tahi expansion) | 0.505 | 0.492 |
| random-A (control) | 0.000 | 0.018 |
| random-B (control) | 0.000 | 0.028 |

**Level 0 passes, decisively.** flat-B 0.890 against random-B 0.028 on the
continuation relation. There is real signal for cross-attention to select
between; "the memory is uninformative" is ruled out as an explanation for
anything downstream.

**Graph expansion is a net negative at every budget.** flat-B beats graph-B at
@1 (0.180 vs 0.083), @3 (0.863 vs 0.328), @5 (0.890 vs 0.492) and @10 (0.902 vs
0.830). Expansion never wins. The mechanism is visible in the code: `_expand`
was rewritten to fix a multiplicative-damping bug that made expanded candidates
*always lose* (they were scaled by ~0.45 before competing), and the replacement
adds a structural bonus of up to +0.15 in a combined-score space where direct
hits sit around 0.25–0.9. The fix overshot: expanded candidates now displace
better direct hits. Same failure, opposite sign.

This is a baseline reading of the code as it stands, taken *before* any fix, so
that a later change can be scored against both relations rather than only the
one the failing tests measure.

**The dominant effect is document grouping, not retrieval method.** Corpus B
beats corpus A by +0.64 on continuation (0.890 vs 0.253) — larger than any
method difference in the table. Packaging a subject's facts into one document
gives the text arm its first hop for free, and that is worth far more than
traversal. It is also the conservative condition, so the graph is losing from
the position it should find hardest to beat.

**The relevance/continuation gap is real and concentrated at small k.** flat-B
scores 0.960 relevance@1 against 0.180 continuation@1 — the two relations are
not interchangeable at the budget GCCA actually uses. By @5 the gap closes
(0.980 vs 0.890). flat-A shows the gap at every budget (0.835 vs 0.253).

### What this measurement does not establish

- **Absolute numbers are inflated.** Boundary queries are verbalised with the
  same templates the corpus uses, so every text arm shares lexical surface with
  its own index. The bias is uniform across arms — the graph arm queries with
  the identical string — but these are not deployment recall figures.
- **It scores retrieval, not generation.** No model runs. It cannot say whether
  better continuation recall produces better answers; that is Level 2.
- **One corpus, one domain.** MetaQA is a movie KB with nine relation types.
  Whether the expansion result generalises to prose corpora is untested.
- **It measures Tahi's expansion as currently wired**, with three failing tests against
  it. A repaired `_expand` could change this line entirely — which is the point
  of taking the baseline first.

### Consequences

1. The graph arm cannot be justified on this evidence. Either `_expand` is
   repaired and re-measured against **both** relations, or the graph substrate
   is dropped and TahiRetro reduces to the schedule bet — which is MAAILMA's
   bet, already further along.
2. Repairing `_expand` against `tests/test_graph_retrieval.py` alone would tune
   it on the relevance relation. Both numbers must move together, or the repair
   is the same mistake in a third form.
3. The free-hop result is worth carrying into any corpus design: how facts are
   grouped into documents dominates retrieval-method choices at this scale.

## Status of the earlier result

The 2026-08-04 run (`benchmarks/results/l3_native_run.json`, `l3_trained` token-F1
0.063 vs `rag_prompt` 0.128) is **valid for what it measured and does not bear on this
architecture.** It benchmarked one-shot injection on single-hop questions. It tripped
the Stage 4 Option B kill criterion in `docs/RETRO_POC.txt`, and GCCA was deferred the
same day.

Claim A of the falsification plan — *does retrieval that re-aims mid-generation beat
one-shot retrieval* — remains **untested**.

## Kill criteria, restated

Unchanged from `docs/retro-v2-falsification-plan.md`, and to be committed to before the
Tier 2 run, not after:

- If `iterative_rag` does not beat `rag_prompt` on the multi-hop set, continuous
  retrieval does not help this task. **Stop** — no GCCA result can matter.
- If `tahiretro_graph` does not beat `oneshot_inject`, the schedule buys nothing. Stop.
- If `tahiretro_graph` does not reach `iterative_rag` accuracy at materially lower
  cost, the custom architecture is not justified. Publish the null and stop.
