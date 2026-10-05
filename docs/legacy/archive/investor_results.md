# Investment Memo — TAHI (World-Model Coprocessor)

**Date:** 2026-08-01
**Reviewer:** Technical due diligence (VC perspective)
**Scope:** All docs in `docs/`, `README.md`, `AGY_*.md`, benchmark artifacts in `benchmarks/`, core code in `src/tahi/` and `implementations/`, plus `remediation_and_real_benchmark_plan.md`

**Recommendation: PASS at this stage.** Not because the thesis is wrong, but because **none of the evidence presented actually tests the thesis**, and the published reports make claims the repo's own artifacts contradict.

---

## 1. The thesis is legitimate

Structured, auditable, updateable grounding as a layer between enterprise domain knowledge and frozen LLMs is a real category. Constraint enforcement + provenance + cheap knowledge updates is a genuine gap that vector RAG doesn't fill. Positioning against RETRO/ANN as "correctness over recall coverage" (`AGY_ARCH_REVIEW.md`) is intellectually honest and well-argued. `docs/research/HONEST_STATUS_MARCH_2026.md` is the single best document in this repo — it shows the team *can* self-assess ruthlessly.

The problem is that the March honesty was replaced, not built on.

---

## 2. What the benchmark harness actually does

`benchmarks/run_4arm_benchmark.py` is the sole source for all four August reports. It has defects that invalidate every headline number.

**a) "Exact Match" is substring containment, both directions.**

```python
em = 1.0 if (pred == ref or ref in pred or pred in ref) else 0.0   # line 76
```

This is why `hotpotqa_4arm_results.json` reports **EM = 1.000 for all four arms — including the zero-retrieval base LLM — alongside F1 = 0.028.** EM 1.0 with F1 0.028 is mathematically impossible under any real EM definition. The metric is measuring nothing.

**b) "Distractor Rejection" uses that same broken EM, and the compared prompts are identical except for capitalization.**

Arm 1's distractor prompt (line 144) vs Arm 2's (line 191) differ *only* in `CONTEXT:/QUESTION:/ANSWER:` vs `Context:/Question:/Answer:`. Both receive the same text. The headline **"100% distractor rejection vs 0% for Base LLM"** is a case-sensitivity artifact. Also, the "distractors" are the gold context plus one literal sentence reading `[NOISE] Additional unverified trivia context.` That is not the RGB protocol.

**c) "TTFT" is not TTFT.** It's total wall-clock for a non-streaming completion (the code comment says so). TPS sits at 3.6–4.5 across all arms, so elapsed time is purely a function of output length. The **"48% TTFT reduction"** means TAHI arms produced *shorter answers* — ~44 words vs ~21. Adding prompt tokens cannot reduce prefill; the report's causal explanation ("reduces prefill token search overhead") is backwards.

**d) Arm 4 "Native GCCA" does not exist as an experiment.** The code instantiates GCCA, runs it on `torch.randn` dummy hidden states, **discards the result** (`_ = gcca(h_dummy, mem)`), then sends a text prompt over HTTP to vLLM. The GCCA computation has zero causal effect on any generated token. Arm 4 is Arm 3 with a different prompt template. `peak_vram_gb: 0.00` in every row confirms it.

Worse: `alpha` is zero-initialized and never trained, so `tanh(0) = 0` and `h + 0·attn = h`. **Untrained, GCCA is a provable identity function.** And the injected "world state" is `FusedSignal(vector=tuple([0.1]*768))` — a constant vector, identical for every query, carrying zero information.

**e) No arm performs retrieval.** `retrieved_context` is handed to Arms 2/3/4 pre-populated with the **gold supporting facts**. "Standard RAG (SentenceTransformers + FAISS)" as described in the reports does no vector search anywhere in the code. Arm 3 "TAHI" never touches `WorldModel`, `Planner`, `RuleEngine`, `Simulator`, or `FusionModule` — it hand-builds a `CognitiveState` from the gold document titles. **The benchmark does not exercise the product.** Its measured "TAHI advantage" is telling the model the gold Wikipedia titles.

**f) The code as committed cannot run.** `check_constraint_violation` calls `re.search`; `re` is never imported. Any dataset with non-empty `forbidden_terms` raises `NameError`.

**g) LegalBench is two hardcoded questions** written in the harness file, with `retrieved_context = f"Statutory excerpt: {q.answer}"` — the gold answer verbatim. Reported as "Real LegalBench Statutory & Contract Reasoning Dataset."

---

## 3. Selective reporting — the part I can't get past

This is the finding that moves this from "sloppy" to "disqualifying at current stage."

`benchmarks/legalbench_4arm_results.json` records **constraint violation 50.0% and distractor rejection 0.0% for all four arms — TAHI included.** The published `docs/TAHI_LEGALBENCH_REPORT.md` **drops both columns entirely** and leads with F1 and TTFT. The two metrics where TAHI showed no advantage were removed from the report; the report then discusses the constraint checker at length as a "Code Audit & Fix" success.

And `benchmarks/4arm_benchmark_results.json` — the machine-generated artifact for the flagship 20-item run — is **all zeros with TPS 11000.0 and TTFT 0.0018 ms**, the signature of the offline fallback stub. `docs/TAHI_EXECUTIVE_BENCHMARK_REPORT.md` and `docs/BENCHMARK_4ARM_REPORT.md` cite F1 0.064/0.107/0.194/0.149 and TTFT 10948/5650 ms. **No artifact in the repo reproduces those numbers.**

`docs/EVAL_RESULTS.md` claims `166 passed`. Actual: **142 passed, 27 failed, 2 errors.** (In fairness, the failures sampled are environmental — missing ffmpeg libs, CUDA, and hardcoded `/Users/richiek/...` paths — not logic bugs. Those same stale absolute paths break every documentation link in `README.md` and `docs/ARCHITECTURE.md`.)

---

## 4. The SQL evidence, which is older and more honest

Across all 20 archived BIRD runs: **`naive_baseline`, `rag_baseline`, and `tahi_grounding` produce byte-identical accuracy in every single run.** TAHI's core grounding has never once moved a BIRD number.

The one positive result — `benchmarks/bird/execution_50_claude_PROOF.json`, 20% → 26% — comes solely from `tahi_with_evidence`, which per `implementations/bird/bird.py:804` prepends **BIRD's own human-annotated `evidence` hint field** to the prompt. That field is part of the benchmark's task input, not a system contribution; every serious BIRD submission uses it. So the "30% relative lift" is 13 vs 10 correct out of 50 (not significant under McNemar) attributable to a dataset field, not to TAHI.

Also: 20% on BIRD dev, when public SOTA is 65–75% and plain GPT-4 baselines clear 40%, means the harness itself is unreliable in both directions.

The founders knew this in March: *"we don't have a cost-effective deployment path, and claiming 'production-ready' with 0% results on local models was bullshit."* Nothing in the August work refutes that; the August work restates the opposite conclusion with weaker evidence.

Finally, `scripts/train_schema_sql_coprocessor.py` — the only training script — is standard **LoRA SFT**, which contradicts the architecture's central "no fine-tuning, domain logic in graphs not weights" claim. There is no GCCA training pipeline and no adapter checkpoints anywhere in the repo.

---

## 5. Does the remediation plan solve these concerns?

**It fixes roughly a third of them.** It's a genuinely good document — the audit that produced it found real things, and Components 2 (streaming TTFT) and 3 (SQuAD normalization) are correct fixes to (c) and (a). Component 1 correctly identifies that vLLM-over-HTTP cannot expose hidden states.

**But it leaves the structural failures untouched:**

| # | Concern | Plan status |
|---|---|---|
| 1 | **No arm retrieves anything; gold context is handed to Arms 2/3/4** | ❌ Not addressed. Component 4 adds hard negatives to the *distractor* prompts only; the main `retrieved_context` stays gold. Until every arm retrieves from a shared real corpus, there is no experiment. |
| 2 | **Arm 3 bypasses the entire TAHI runtime** | ❌ Not addressed. The benchmark still won't test the product. |
| 3 | **α=0 ⇒ GCCA is an identity function** | ❌ Not acknowledged. Component 1 will make Arm 4 bit-identical to Arm 1 — a useful falsification, but the plan presents it as the fix. No GCCA training data, run, or budget exists. |
| 4 | **Injected memory is a constant `[0.1]*768`** | ❌ Not mentioned. Even with trained adapters, zero query-specific signal. |
| 5 | **Missing `import re`** | ❌ Not mentioned; harness still crashes on constraint datasets. |
| 6 | **Statistical significance** | ⚠️ Asks "N=100 for p<0.05?" — but N=100 cannot resolve F1 deltas of 0.014. Needs paired McNemar / bootstrap CIs and a power calculation, not a sample-size guess. |
| 7 | **Dropped columns / unreproducible published numbers** | ❌ No retraction or reconciliation step. The four August reports stay live. |
| 8 | **Cost per correct answer** | ❌ Absent — and it's the actual commercial question, flagged by the team's own March doc. |
| 9 | **Constraint-violation metric validity** | ❌ Still keyword regex, tautologically won by whoever receives the context. |

Net: the plan makes the instrument more accurate while leaving the experiment invalid. You'd get precise measurements of the wrong thing.

---

## 6. What would change my mind

Not more reports — one honest negative result would move me more than all four August reports combined.

1. **Retract or annotate the four August reports.** Non-negotiable. Diligence will find §3 in an afternoon, and it recontextualizes everything else.
2. **One real experiment:** HotpotQA distractor setting, full 10-paragraph context, *every* arm retrieving from the same corpus, SQuAD-normalized EM/F1, N≥500, paired McNemar with CIs. Publish the number whatever it is.
3. **Kill-test Level 3 honestly.** Run Arm 4 in-process, confirm it equals base at α=0, then either train GCCA on a real dataset and show a delta, or state publicly that Level 2/3 is unfunded roadmap. Currently the deck sells Level 3 and the code cannot produce it.
4. **Cost per correct answer** vs. plain RAG and vs. a fine-tuned specialist — the metric the March doc identified as the gating question.
5. **Find one domain where the graph genuinely wins.** The DEA result (+4.8%, n=21, with distractors and multi-hop questions, against an honest `StandaloneRAG` baseline) is the most credible signal in this entire repo. It's small, but it was measured fairly. Scale *that*.

---

## Bottom line

Pass now, stay in touch. The architecture is coherent, `WorldModelStore` and the repo boundary are real engineering, and the March self-assessment shows the intellectual honesty this needs. But the August benchmark suite is not weak evidence — it is **evidence that the measurement discipline has broken down**, with at least one instance of metrics being dropped from a published report precisely where they were unfavorable.

For a company whose entire value proposition is *auditability and provenance*, that is the worst possible failure mode. I'd need to see the retraction and one honestly-run experiment before re-engaging — and I'd want to see it whether the result is positive or negative.

---

## Appendix — Evidence index

| Claim | File / location |
|---|---|
| Substring EM | `benchmarks/run_4arm_benchmark.py:76` |
| Missing `import re` | `benchmarks/run_4arm_benchmark.py:19-38` vs `:100,103` |
| Distractor prompts differ only by case | `run_4arm_benchmark.py:144` vs `:191` |
| Wall-clock labelled TTFT | `run_4arm_benchmark.py:135, 180, 249, 334` |
| GCCA output discarded | `run_4arm_benchmark.py:319-323` |
| Constant fused vector | `run_4arm_benchmark.py:233, 309` |
| α zero-init ⇒ identity | `src/tahi/native/gcca_layer.py:50, 85-86` |
| Gold context handed to all arms | `run_4arm_benchmark.py:403-407, 387` |
| LegalBench = 2 hardcoded items | `run_4arm_benchmark.py:364-394` |
| Dropped unfavourable columns | `benchmarks/legalbench_4arm_results.json` vs `docs/TAHI_LEGALBENCH_REPORT.md` |
| Flagship run is all zeros / stub | `benchmarks/4arm_benchmark_results.json`, `.md` |
| EM 1.0 with F1 0.028 | `benchmarks/hotpotqa_4arm_results.json` |
| TAHI grounding == naive baseline, 20/20 runs | `benchmarks/bird/execution_*.json` |
| "30% lift" = BIRD's own evidence field | `implementations/bird/bird.py:804-805` |
| Only training script is LoRA SFT | `scripts/train_schema_sql_coprocessor.py:27,97,131` |
| Team's own honest assessment | `docs/research/HONEST_STATUS_MARCH_2026.md` |
| Most credible positive signal | `docs/EVAL_RESULTS.md` (DEA, +4.8%, n=21) |
