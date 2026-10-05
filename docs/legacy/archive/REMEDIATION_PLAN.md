# TAHI Remediation Plan — Restoring Measurement Discipline

**Date:** 2026-08-01
**Companion to:** `investor_results.md`
**Owner:** _unassigned_
**Status:** Draft for approval

---

## 0. Framing: what actually went wrong

The August benchmark suite did not fail because of bad code. It failed because of **three missing controls**, and every individual defect in `investor_results.md` is downstream of one of them:

| Root cause | What it produced |
|---|---|
| **Silent degradation.** `LLMClient._fallback_complete()` returns a plausible string when no provider is configured; `get_encoder()` silently swaps `STEncoder` → `HashedTokenEncoder` on any exception (including `local_files_only=True` cache misses). Neither raises, neither is recorded in output. | `4arm_benchmark_results.json` — an all-zeros stub run, written to disk indistinguishable from a real one, then reported as the flagship 20-item result. |
| **Hand-written reports.** `src/tahi/results_reporter.py` and `benchmarking.py` already provide `write_eval_artifacts()` and `render_markdown_summary_table()`. The four August reports bypassed them and were authored by hand from remembered numbers. | Reports whose numbers appear in no artifact; the LegalBench report silently dropping the two columns where TAHI tied. |
| **No pre-registration.** Metrics were defined after results were seen, so every ambiguous choice resolved favourably. | Substring "EM", wall-clock "TTFT", `[NOISE]`-label "distractors". |

**Therefore the plan below fixes the controls first and the experiments second.** Fixing metrics without fixing the controls just produces the next round of unfalsifiable reports.

A note on cost: Phases 0–2 are the whole job. Phases 3–5 are optional depending on what Phase 2 returns. Do not start Phase 3 before Phase 2 reports a number.

---

## Phase 0 — Quarantine (2 days, do this first)

**Goal:** stop distributing claims that cannot be reproduced. Nothing else can start until the record is clean, because every later result will be read against the current one.

| # | Action | File |
|---|---|---|
| 0.1 | Add a `> [!WARNING] RETRACTED — see REMEDIATION_PLAN.md` header to all four August reports. Do not delete them; retracted-and-visible is more credible than disappeared. | `docs/TAHI_EXECUTIVE_BENCHMARK_REPORT.md`, `docs/BENCHMARK_4ARM_REPORT.md`, `docs/TAHI_HOTPOTQA_BENCHMARK_REPORT.md`, `docs/TAHI_LEGALBENCH_REPORT.md` |
| 0.2 | Move the stub artifacts to `benchmarks/retracted/` with a `README.md` explaining what each one actually was. | `benchmarks/4arm_benchmark_results.{json,md}` |
| 0.3 | Correct the test-count claim: `166 passed` → actual `142 passed, 27 failed, 2 errors`, with the environmental-vs-logic breakdown. | `docs/EVAL_RESULTS.md` |
| 0.4 | Promote `docs/research/HONEST_STATUS_MARCH_2026.md` to `docs/STATUS.md` as the canonical status document, updated to August. | new |
| 0.5 | Fix the ~40 stale `/Users/richiek/...` absolute paths breaking every doc link and 15 tests. | `README.md`, `docs/ARCHITECTURE.md`, `tests/test_spider_snow*.py`, `tests/test_schema_compression.py` |

**Gate 0:** a reader arriving cold cannot mistake a retracted number for a live one.

---

## Phase 1 — Make the instrument trustworthy (1 week)

**Goal:** it must become *impossible* to produce a result artifact that silently lies. No experiments run during this phase.

### 1.1 Fail loud — kill every silent fallback in a measurement path

```python
# src/tahi/llm_client.py
def __init__(self, ..., strict: bool = False):
    self.strict = strict or os.getenv("TAHI_STRICT") == "1"

def _fallback_complete(self, prompt, system=None):
    if self.strict:
        raise RuntimeError(
            "No LLM provider configured and strict mode is on. "
            "Refusing to emit placeholder text into a measurement path."
        )
    ...
```

Same treatment for `get_encoder()`: in strict mode, an `STEncoder` failure raises rather than degrading to `HashedTokenEncoder`. **Every benchmark entrypoint sets `strict=True` unconditionally.** The offline fallbacks stay — they are genuinely useful for demos and CI — but they become unreachable from anything that writes a result file.

### 1.2 Run manifests — every artifact self-describes

Extend `benchmark_report_to_dict()` so no result can be written without:

```json
{
  "manifest": {
    "git_sha": "21f89b3", "git_dirty": false,
    "timestamp_utc": "...", "seed": 0,
    "provider": "vllm", "model": "Qwen/Qwen2.5-72B-Instruct-AWQ",
    "encoder": "sentence-transformers/all-MiniLM-L6-v2",
    "encoder_is_fallback": false,
    "dataset": "hotpotqa-distractor-dev", "dataset_sha256": "...",
    "n_items": 500, "n_llm_calls": 2000, "strict_mode": true,
    "wall_clock_s": 4210.3, "est_cost_usd": 0.00
  }
}
```

`encoder_is_fallback` and `strict_mode` exist specifically so the `4arm_benchmark_results.json` failure mode is visible on the face of the file.

### 1.3 Reports are generated, never written

- Delete the four hand-written August reports; replace with `scripts/render_report.py <results.json> -o <report.md>`.
- Every number in a report must render from the JSON. Prose is allowed only in explicitly-marked interpretation sections.
- **The renderer emits every column in the schema.** Dropping a column requires deleting it from the schema for all arms — which makes selective reporting a visible, reviewable diff instead of an invisible omission. This single rule structurally prevents the LegalBench incident.
- CI check: fail if any `docs/*BENCHMARK*.md` has no corresponding `benchmarks/*.json` with a matching manifest hash.

### 1.4 Correct metrics, with unit tests that pin the pathologies

| Metric | Fix | Regression test |
|---|---|---|
| EM | Official SQuAD normalization: lowercase, strip articles/punctuation/whitespace, **full sequence equality**. No containment. | `assert em("Based on context, Paris", "Paris") == 0.0` and `f1(...) > 0.5` |
| F1 | Multiset token overlap (`collections.Counter`), not `set` intersection — the current version ignores duplicates. | pinned known-value cases |
| TTFT | Real streaming: `stream=True`, stop the clock on the first chunk with non-empty `delta.content`. Report **prefill TTFT and decode TPS as separate fields**, plus `output_token_count`. | assert TTFT < total latency on a live call |
| Constraint violation | Replace keyword regex with per-domain validators. For SQL, `src/tahi/validators/sql.py` already does real work — use it. Keyword matching is a placeholder, not a metric. | domain-specific |
| Distractor rejection | Rename to `accuracy_under_noise` — it never measured rejection. True rejection needs an abstention signal ("I don't know") scored separately. | — |
| — | `import re` (currently missing → `NameError` on any constraint-bearing dataset) | smoke test |

**Gate 1:** delete your API key, run the full benchmark suite, and confirm it **crashes** instead of producing a file. That is the acceptance test.

---

## Phase 2 — One valid experiment (2–3 weeks)

**Goal:** answer the actual question — *does TAHI's world model beat honest dense RAG when both retrieve from the same corpus?* This has never been tested.

### 2.1 Pre-register before writing harness code

Commit `benchmarks/PREREGISTRATION_hotpotqa.md` containing hypothesis, primary metric (**answer F1**, one metric, chosen in advance), N, statistical test, and — critically — **the kill criterion, written before any data is seen**:

> If TAHI's F1 improvement over `StandaloneRAG` has a 95% bootstrap CI that includes zero at N=500, the graph-retrieval thesis is not supported on multi-hop Wikipedia QA, and we report that and move to a domain where structure matters more.

Merge this before the harness exists. Its whole value is that it is unfalsifiable-after-the-fact.

### 2.2 Rebuild the harness so the arms are actually different

This is the core of the plan. Current arms differ by prompt-string formatting; they must differ by **which system retrieves the evidence**.

| Arm | Current (invalid) | Required |
|---|---|---|
| 1 — Base | query only | unchanged ✅ |
| 2 — RAG | gold facts pasted in | `StandaloneRAG` (`src/tahi/baseline_rag.py`) retrieves top-k from the **full 10-paragraph distractor corpus** |
| 3 — TAHI L1 | `CognitiveState` hand-built from gold titles | `TahiRuntime.infer()` over a `WorldModel` built from the **same full corpus** — real `Planner`, `RuleEngine`, `Simulator`, `Fusion`, real `ControlPacket` |
| 4 — TAHI L3 | GCCA output discarded; text prompt sent | see Phase 3 — **excluded from Phase 2** |

**Hard rule: no arm receives `supporting_facts`.** Gold facts are used only to score. `implementations/hotpotqa/hotpotqa_eval.py` currently builds its world model *from the gold supporting facts* (its own docstring says so) — that must be rebuilt from the full distractor context. Add an assertion that raises if any gold-only field reaches a prompt-construction path.

Retrieval quality is measured separately from answer quality: **supporting-fact recall@k for Arms 2 and 3**. If TAHI's recall matches RAG's, the graph adds nothing and the answer F1 delta is noise — that diagnostic is what tells you *why* a result happened.

### 2.3 Scale and statistics

- **N = 500** HotpotQA distractor-dev, seeded sample, dataset hash in manifest.
- Paired **McNemar** on per-item correctness; **10k-sample bootstrap CI** on the F1 delta.
- Power check first: at N=500, the minimum detectable F1 delta is roughly ±0.03. **The August deltas (0.014) were never detectable at any N these runs used** — this is why "more samples" alone was never the fix.
- Report the CI. A delta without a CI is not a result.

**Gate 2 — the real decision point.** Three honest outcomes, all publishable:
- **CI excludes zero, favourable** → thesis has first real support. Proceed to Phase 3.
- **CI includes zero** → the pre-registered kill criterion fires. Publish the negative result, skip Phase 3 entirely, go to Phase 5.
- **CI excludes zero, unfavourable** → graph expansion is adding noise (consistent with the MuSiQue −33% in `docs/EVAL_RESULTS.md`). Publish, then investigate expansion limits.

---

## Phase 3 — The Level 3 kill test (2 weeks) — *only if Gate 2 passes*

The deck sells Level 3. The code cannot currently produce it. Resolve this honestly.

### 3.1 Prove the null first

Run `TahiNativeAdapter` in-process (`AutoModelForCausalLM`, ~7B on the GB10's unified memory — 72B in-process is not realistic here) with real forward hooks and untrained `α = 0`.

**Predicted result: output bit-identical to the base model,** because `tanh(0) = 0` ⇒ `h + 0·attn = h`. Assert it in a test:

```python
def test_untrained_gcca_is_identity():
    assert torch.equal(adapter(ids).logits, base_model(ids).logits)
```

This is not a formality. It converts an unfalsifiable architectural claim into a passing test, and it makes the honest statement possible: *"Level 3 is wired end-to-end and provably neutral until trained."*

### 3.2 Fix the memory tensor — the defect nobody has noticed

Even with trained adapters, the current design injects **zero information**. `FusedSignal(vector=tuple([0.1]*768))` is a constant, identical for every query. Before any training is worth running:
- the memory tensor must be the real fused world-state vector, varying per query;
- `d_retriever` must reconcile with the base model's `hidden_size` (8192 for Qwen-72B vs. the hardcoded 768) — currently only coherent by accident;
- K must be > 1 (retrieved node set), not a single pooled vector.

Test: two different queries must produce cosine-distinguishable memory tensors. Trivial to write; currently fails.

### 3.3 Train, or declare

Build a real GCCA training pipeline (frozen base, train only `W_K, W_V, α`, ~4–6h). **Note that `scripts/train_schema_sql_coprocessor.py` is LoRA SFT and trains no GCCA — it is not a starting point, and it contradicts the "no fine-tuning" architectural claim.** Success = `α` moves meaningfully off zero *and* held-out F1 beats Level 1.

**Gate 3:** if this is not funded or not achieved, **change the pitch materially** — Level 2/3 moves from "differentiation roadmap" to "unfunded research direction." Selling residual-stream injection while shipping prompt-string concatenation is the specific claim most likely to end a diligence process badly.

---

## Phase 4 — Cost per correct answer (1 week, runs parallel to 2)

The commercial question, flagged in the team's own March doc and still unanswered. Instrument `LLMClient` to record token counts and cost per call, then report for every arm:

```
cost_per_correct = (Σ tokens × $/token + amortized world-model build) / n_correct
```

Compare against plain RAG, and against a fine-tuned specialist as the honest alternative. If TAHI improves accuracy 15% at 3× cost, that is a real finding a buyer needs — and it may be *fine*. Not measuring it is what is not fine.

---

## Phase 5 — Find the domain where structure actually wins (4 weeks)

**The DEA result is the most credible signal in this entire repo** (`docs/EVAL_RESULTS.md`): +4.8% over an honest independent `StandaloneRAG`, on a corpus with real distractors and multi-hop questions, guarded by a 30-case scorer test suite, after an audit that *removed* asymmetric keyword boosting. That is what disciplined measurement looks like — the team has done this before.

It is also exactly the shape the thesis predicts: graph traversal wins when vector similarity is ambiguous (analogue → class → action edges). HotpotQA and BIRD are the wrong hills — BIRD has shown `tahi_grounding == naive_baseline` in **20 of 20** archived runs.

Scale the DEA corpus (Federal Register scheduling actions since 2010), get N to 200+, apply the Phase 1–2 rigor, and see whether +4.8% at n=21 survives contact with statistics. **This is the highest-expected-value work in the plan** — and it should arguably run in parallel with Phase 2 rather than after it.

---

## Timeline & sequencing

```
Week:  1  2  3  4  5  6  7  8  9 10
P0    ██
P1       ████████
P2             ████████████        → GATE 2 (go/no-go)
P4             ████                  (parallel)
P5             ████████████████      (parallel — highest EV)
P3                         ██████    (only if Gate 2 passes)
```

Phases 0–1 are unconditional: ~3 weeks, one engineer. Everything after Gate 2 is contingent on a real number.

---

## The five standing rules

These outlast the plan. Put them in `CONTRIBUTING.md` and enforce in CI.

1. **No silent degradation in a measurement path.** Fallbacks raise under `strict`. A benchmark that cannot run must crash, not improvise.
2. **Reports are rendered from artifacts, never authored.** Every published number traces to a JSON with a manifest.
3. **The schema is the report.** Every arm reports every column. Dropping a metric is a schema change and a reviewable diff.
4. **Pre-register metric, N, and kill criterion before the harness exists.**
5. **Publish negatives.** The March status doc is the most trust-building artifact here; a negative Phase 2 result would be the second.

---

## What this plan is honestly for

It will not necessarily save the thesis. Gate 2 may kill it on multi-hop QA, and Gate 3 may reveal that Level 3 is years from real. **That is the intended function.** A structured, auditable, provenance-preserving reasoning layer is a real category and the architecture is a coherent bet on it — but the current evidence base cannot tell you whether TAHI is that product, because no experiment yet run has been capable of returning "no."

The first genuinely falsifiable result — in either direction — is worth more than every report in `docs/` today. For a company selling auditability, demonstrating that it measures itself the way it promises to measure its customers' models is not overhead. It is the product demo.
