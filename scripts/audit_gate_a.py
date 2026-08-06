#!/usr/bin/env python
"""
Mechanical audit of a Gate A run. Written BEFORE the run produced numbers.

Purpose: make the verdict independent of whoever writes the summary. Every
conclusion this project has retracted was a plausible narrative laid over real
artifacts -- `p<0.05` reported where the artifact recorded `p: None`, an
exact-match column that existed in no file, an AUC computed on n=2 presented as
general, and a causal story about alpha that was never tested. A prose audit
written by the same author as the conclusion cannot catch that class of error.

This script answers three questions in order, and refuses to skip any:

  (a) WHAT THE TEST DID       -- provenance read out of the artifact and the
                                 checkpoint, never retyped from a log.
  (b) WHAT IT WAS SUPPOSED TO -- the pre-registered conditions in
      DO                        docs/OCTO_ENDGAME_PLAN.md section 2.
  (c) DO (a) AND (b) AGREE,   -- conformance, validity, independent
      AND DO THE CONCLUSIONS     re-derivation of every headline number from
      FOLLOW?                    per-item data, then the decision bands applied
                                 arithmetically.

Exit codes:
  0  audit completed and the run is VALID (verdict printed; may be PASS,
     INCONCLUSIVE, or FAIL -- all three are real results)
  2  the run is VOID: a pre-registered validity gate failed. The correct
     response is to fix and rerun, NOT to interpret the numbers.
  3  the audit could not be completed (missing artifact, unreadable checkpoint).

Usage:
    python scripts/audit_gate_a.py \
        --artifact benchmarks/results/gate_a_oracle.json \
        --checkpoint checkpoints/gcca_oracle/gcca_epoch14.pt \
        --split-manifest data/gcca_oracle/split_manifest.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# The pre-registration, transcribed from docs/OCTO_ENDGAME_PLAN.md section 2.
# These are the committed values. If a run does not match them, that is a
# finding about the run, not a reason to edit this block.
# ---------------------------------------------------------------------------

PREREG = {
    "memory_source": "oracle",
    "gnn": "off",
    "distractor_frac": 0.0,
    "encoder": "all-MiniLM-L6-v2",
    "max_new_tokens": 35,
    "seed": 0,
    "test_frac": 0.3,
    "base_failure_metric": "token_f1",
    "base_failure_max": 0.5,
}

PASS_ALPHA = 0.10
FAIL_ALPHA = 0.05
LENGTH_TOLERANCE = 0.10        # arms may differ by at most 10% in output tokens
RE_DERIVE_TOLERANCE = 1e-6     # summary vs recomputed-from-per-item

# What Gate A structurally cannot answer. Printed with every verdict so a
# conclusion cannot quietly outgrow its evidence.
SCOPE_LIMITS = [
    "Oracle memory is the question's OWN gold documents. This measures whether "
    "the GCCA bridge can use ideal memory -- NOT whether retrieval works, and "
    "NOT whether a graph beats vector RAG.",
    "The RGAT is OFF. Nothing here is evidence about the graph encoder, which "
    "remains untrained and unvalidated against any published baseline.",
    "The base model is Qwen2.5-1.5B. A shut gate at 1.5B does not prove a shut "
    "gate at larger scale, though the plan argues scale is not the mechanism.",
    "This is EnterpriseRAG-Bench only. It is one corpus with one question "
    "distribution and a base token-F1 of 0.075.",
    "A PASS on alpha alone is not a capability claim. The accuracy CI must also "
    "exclude zero, per the pre-registered band.",
]


class Audit:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.void_reasons: list[str] = []
        self.warnings: list[str] = []
        self.conformance_failures: list[str] = []

    def say(self, text: str = "") -> None:
        self.lines.append(text)

    def check(self, ok: bool, label: str, detail: str = "",
              *, void_on_fail: bool = False, conformance: bool = False) -> bool:
        mark = "PASS" if ok else "FAIL"
        self.say(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
        if not ok:
            if void_on_fail:
                self.void_reasons.append(f"{label}: {detail}" if detail else label)
            elif conformance:
                self.conformance_failures.append(
                    f"{label}: {detail}" if detail else label)
            else:
                self.warnings.append(f"{label}: {detail}" if detail else label)
        return ok


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--split-manifest", default=None)
    ap.add_argument("--out", default=None,
                    help="Write the audit report here as well as stdout.")
    args = ap.parse_args()

    A = Audit()

    art_path = Path(args.artifact)
    if not art_path.exists():
        print(f"AUDIT INCOMPLETE: artifact not found: {art_path}", file=sys.stderr)
        return 3
    art = json.loads(art_path.read_text(encoding="utf-8"))

    manifest = art.get("manifest", {})
    arms = {a["name"]: a for a in art.get("arms", [])}
    per_item = art.get("per_item", [])
    comparisons = art.get("comparisons", [])
    notes = manifest.get("notes", "")

    A.say("=" * 78)
    A.say("GATE A AUDIT")
    A.say("=" * 78)
    A.say(f"artifact: {art_path}")
    A.say()

    # -----------------------------------------------------------------------
    # (a) WHAT THE TEST DID -- read out, never retyped
    # -----------------------------------------------------------------------
    A.say("-" * 78)
    A.say("(a) WHAT THE TEST DID  [read directly from the artifact]")
    A.say("-" * 78)
    for k in ("git_sha", "git_dirty", "timestamp_utc", "model", "encoder",
              "encoder_is_fallback", "strict_mode", "seed", "n_items",
              "wall_clock_s", "dataset", "dataset_sha256"):
        if k in manifest:
            A.say(f"  {k:22s} {manifest[k]}")
    A.say(f"  {'arms':22s} {sorted(arms)}")
    A.say(f"  {'per_item rows':22s} {len(per_item)}")
    A.say(f"  {'notes':22s} {notes}")
    A.say()

    # Parse the memory provenance the benchmark stamped into notes.
    def note_field(key: str) -> str | None:
        for chunk in notes.replace(". ", ", ").split(","):
            chunk = chunk.strip()
            if chunk.startswith(f"{key}="):
                return chunk.split("=", 1)[1].strip()
        return None

    run_memory_source = note_field("source")
    run_store_sha = note_field("store_sha")
    run_gnn = note_field("gnn")
    run_alpha = note_field("max|tanh(alpha)|")

    A.say(f"  memory source (run)    {run_memory_source}")
    A.say(f"  memory store sha (run) {run_store_sha}")
    A.say(f"  gnn (run)              {run_gnn}")
    A.say(f"  alpha reported in run  {run_alpha}")
    A.say()

    # -----------------------------------------------------------------------
    # alpha, read from the checkpoint itself rather than from any log
    # -----------------------------------------------------------------------
    alpha_max = None
    ck_store_sha = None
    if args.checkpoint:
        try:
            import torch
            ck = torch.load(args.checkpoint, map_location="cpu")
            sd = ck.get("gcca_state_dict", {})
            alphas = [float(torch.tanh(v)) for k, v in sd.items() if "alpha" in k]
            if alphas:
                alpha_max = max(abs(a) for a in alphas)
            ck_store_sha = ck.get("memory_store_sha256")
            A.say("-" * 78)
            A.say("ALPHA  [recomputed from the checkpoint tensor, not from logs]")
            A.say("-" * 78)
            A.say(f"  checkpoint          {args.checkpoint}")
            A.say(f"  epoch               {ck.get('epoch')}")
            A.say(f"  n gates             {len(alphas)}")
            A.say(f"  tanh(alpha)         {[round(a, 5) for a in alphas]}")
            A.say(f"  max |tanh(alpha)|   {alpha_max:.5f}")
            A.say(f"  trained on store    {ck_store_sha}")
            A.say()
        except Exception as e:  # noqa: BLE001 -- audit must not crash on a bad file
            A.say(f"  COULD NOT READ CHECKPOINT: {e}")
            A.warnings.append(f"checkpoint unreadable: {e}")
            A.say()

    # -----------------------------------------------------------------------
    # (b) vs (a) -- CONFORMANCE to the pre-registration
    # -----------------------------------------------------------------------
    A.say("-" * 78)
    A.say("(b vs a) CONFORMANCE  [run config vs pre-registered conditions]")
    A.say("-" * 78)

    A.check(run_memory_source == PREREG["memory_source"],
            "memory source is oracle",
            f"pre-registered {PREREG['memory_source']!r}, run {run_memory_source!r}",
            conformance=True)
    A.check(run_gnn == PREREG["gnn"], "graph encoder is off",
            f"pre-registered {PREREG['gnn']!r}, run {run_gnn!r}", conformance=True)
    A.check(str(manifest.get("seed")) == str(PREREG["seed"]), "seed is 0",
            f"run seed {manifest.get('seed')}", conformance=True)

    split = {}
    if args.split_manifest and Path(args.split_manifest).exists():
        split = json.loads(Path(args.split_manifest).read_text(encoding="utf-8"))
        A.check(split.get("memory_source") == PREREG["memory_source"],
                "split manifest says oracle",
                f"{split.get('memory_source')!r}", conformance=True)
        A.check(abs(float(split.get("distractor_frac", -1))
                    - PREREG["distractor_frac"]) < 1e-9,
                "distractor fraction is 0.0",
                f"{split.get('distractor_frac')}", conformance=True)
        A.check(split.get("encoder") == PREREG["encoder"], "encoder matches",
                f"{split.get('encoder')!r}", conformance=True)
        A.check(bool(split.get("require_base_failure")),
                "base-failure filter was applied", conformance=True)
    else:
        A.say("  [SKIP] split manifest not supplied -- split conditions unverified")
        A.warnings.append("split manifest not supplied")
    A.say()

    # -----------------------------------------------------------------------
    # VALIDITY GATES -- any failure makes the run VOID, not negative
    # -----------------------------------------------------------------------
    A.say("-" * 78)
    A.say("VALIDITY GATES  [failure => VOID, discard and rerun; do NOT interpret]")
    A.say("-" * 78)

    A.check(bool(art.get("identity_control_passed")),
            "identity control passed",
            f"mismatches={art.get('identity_mismatches')}", void_on_fail=True)

    A.check(not manifest.get("encoder_is_fallback", False),
            "encoder is not a fallback", void_on_fail=True)
    A.check(bool(manifest.get("strict_mode", False)),
            "strict mode on", void_on_fail=True)

    if ck_store_sha and run_store_sha:
        A.check(ck_store_sha.startswith(run_store_sha.rstrip(".")),
                "checkpoint and run used the SAME memory store",
                f"checkpoint {ck_store_sha[:16]} vs run {run_store_sha}",
                void_on_fail=True)
    else:
        A.say("  [SKIP] store sha unavailable on one side -- symmetry unverified")
        A.warnings.append("store sha cross-check skipped")

    # Length matching: the confound that faked +0.1398 once already.
    tok = {n: a.get("output_tokens") for n, a in arms.items()
           if a.get("output_tokens") is not None}
    if len(tok) >= 2:
        lo, hi = min(tok.values()), max(tok.values())
        spread = (hi - lo) / hi if hi else 0.0
        gen_arms = {n: v for n, v in tok.items() if n != "rag_prompt"}
        glo, ghi = min(gen_arms.values()), max(gen_arms.values())
        gspread = (ghi - glo) / ghi if ghi else 0.0
        A.check(gspread <= LENGTH_TOLERANCE,
                "output length matched across generative arms",
                f"{gen_arms}, spread {gspread:.1%} (rag_prompt excluded: {tok.get('rag_prompt')})",
                void_on_fail=True)
        A.say(f"         all arms: {tok}, full spread {spread:.1%}")

    # Train/test leakage.
    if split:
        train_ids = set(split.get("train_question_ids", []))
        evaluated = {r["question_id"] for r in per_item}
        leaked = evaluated & train_ids
        A.check(not leaked, "no trained items in the evaluated set",
                f"{len(leaked)} leaked ids", void_on_fail=True)
        test_ids = set(split.get("test_question_ids", []))
        A.check(evaluated <= test_ids,
                "evaluated ids are a subset of the held-out split",
                f"{len(evaluated - test_ids)} outside", void_on_fail=True)
    A.say()

    # -----------------------------------------------------------------------
    # INDEPENDENT RE-DERIVATION -- recompute headline numbers from per-item
    # -----------------------------------------------------------------------
    A.say("-" * 78)
    A.say("RE-DERIVATION  [summary block vs recomputed from per_item rows]")
    A.say("-" * 78)
    metrics = ("exact_match", "token_f1", "fact_coverage", "output_tokens")
    by_arm: dict[str, list[dict]] = {}
    for r in per_item:
        by_arm.setdefault(r["arm"], []).append(r)

    for name in sorted(by_arm):
        rows = by_arm[name]
        A.say(f"  arm {name}  (n={len(rows)})")
        reported_n = arms.get(name, {}).get("n")
        if reported_n is not None:
            A.check(int(reported_n) == len(rows), f"    n matches for {name}",
                    f"summary {reported_n} vs per_item {len(rows)}")
        for m in metrics:
            if m not in rows[0]:
                continue
            recomputed = _mean([r.get(m) for r in rows])
            reported = arms.get(name, {}).get(m)
            if reported is None:
                A.say(f"    {m:16s} recomputed {recomputed:.4f}  (not in summary)")
                continue
            agree = math.isclose(float(reported), recomputed,
                                 rel_tol=1e-3, abs_tol=RE_DERIVE_TOLERANCE)
            A.check(agree, f"    {m} matches summary",
                    f"summary {float(reported):.4f} vs recomputed {recomputed:.4f}")
    A.say()

    # -----------------------------------------------------------------------
    # SIGNIFICANCE CLAIMS -- only what the artifact actually supports
    # -----------------------------------------------------------------------
    A.say("-" * 78)
    A.say("COMPARISONS  [as recorded; p-values NOT inferred from CIs]")
    A.say("-" * 78)
    key_cmp = None
    for c in comparisons:
        a_lab = c.get("arm_a", "?")
        b_lab = c.get("arm_b", "?")
        delta = c.get("delta")
        lo = c.get("ci_low", c.get("ci_lower"))
        hi = c.get("ci_high", c.get("ci_upper"))
        sig = c.get("significant")
        p = c.get("p_value")
        A.say(f"  {b_lab} vs {a_lab}")
        A.say(f"      delta {delta:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]  "
              f"significant={sig}  p={p if p is not None else 'NOT COMPUTED'}")
        if p is None and sig:
            A.say("      NOTE: significance here is a bootstrap CI excluding zero. "
                  "It is NOT a p-value. Do not report 'p<0.05'.")
        if a_lab == "base[token_f1]" and b_lab == "l3_trained[token_f1]":
            key_cmp = c
    A.say()

    # -----------------------------------------------------------------------
    # (c) VERDICT -- bands applied arithmetically
    # -----------------------------------------------------------------------
    A.say("=" * 78)
    A.say("(c) VERDICT")
    A.say("=" * 78)

    if A.void_reasons:
        A.say("  RUN IS **VOID**. A pre-registered validity gate failed:")
        for r in A.void_reasons:
            A.say(f"    - {r}")
        A.say()
        A.say("  The numbers in this artifact must NOT be interpreted as a result.")
        A.say("  Correct response: fix the cause and rerun. This is not a negative.")
        _emit(A, args.out)
        return 2

    if A.conformance_failures:
        A.say("  CONFORMANCE FAILURES -- the run did not implement the "
              "pre-registered design:")
        for r in A.conformance_failures:
            A.say(f"    - {r}")
        A.say("  Any verdict below describes the run that was ACTUALLY performed, "
              "which is not the one that was pre-registered.")
        A.say()

    if alpha_max is None:
        A.say("  VERDICT UNAVAILABLE: alpha could not be read from a checkpoint.")
        A.say("  Gate A's primary readout is max|tanh(alpha)|; without it there is "
              "no verdict, regardless of what the accuracy numbers show.")
        _emit(A, args.out)
        return 3

    acc_ok = None
    if key_cmp:
        lo = key_cmp.get("ci_low", key_cmp.get("ci_lower"))
        hi = key_cmp.get("ci_high", key_cmp.get("ci_upper"))
        acc_ok = bool(lo is not None and hi is not None and lo > 0)

    A.say(f"  primary readout   max|tanh(alpha)| = {alpha_max:.5f}")
    A.say(f"  bands             PASS > {PASS_ALPHA}   FAIL < {FAIL_ALPHA}")
    A.say(f"  reference         0.0199 (epoch 2) / 0.0426 (epoch 14), voided run")
    if key_cmp:
        A.say(f"  secondary         l3_trained vs base token_f1: "
              f"{key_cmp.get('delta'):+.4f} "
              f"CI [{key_cmp.get('ci_low', key_cmp.get('ci_lower')):+.4f}, "
              f"{key_cmp.get('ci_high', key_cmp.get('ci_upper')):+.4f}] "
              f"-> CI excludes zero on the positive side: {acc_ok}")
    else:
        A.say("  secondary         l3_trained vs base token_f1 comparison ABSENT")
    A.say()

    if alpha_max < FAIL_ALPHA:
        verdict = "FAIL"
        meaning = ("GCCA did not open the gate even on zero-noise oracle memory. "
                   "OCTO Level 3 is dead, and RETRO-v2's Claim A is damaged with "
                   "it. This is a real, publishable negative result.")
    elif alpha_max > PASS_ALPHA and acc_ok:
        verdict = "PASS"
        meaning = ("The gate opened AND paid. The bridge works; memory quality is "
                   "the bottleneck. Fixing retrieval becomes the priority.")
    else:
        verdict = "INCONCLUSIVE"
        meaning = ("The gate moved but did not pay, or moved only into the "
                   "ambiguous band. Do NOT retune and rerun without a new "
                   "pre-registration.")

    A.say(f"  >>> GATE A VERDICT: {verdict}")
    A.say()
    for line in _wrap(meaning, 74):
        A.say(f"      {line}")
    A.say()

    A.say("  WHAT THIS RUN CANNOT SHOW:")
    for lim in SCOPE_LIMITS:
        for i, line in enumerate(_wrap(lim, 70)):
            A.say(f"    {'- ' if i == 0 else '  '}{line}")
    A.say()

    if A.warnings:
        A.say("  NON-BLOCKING WARNINGS:")
        for w in A.warnings:
            A.say(f"    - {w}")
        A.say()

    _emit(A, args.out)
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def _emit(A: Audit, out: str | None) -> None:
    text = "\n".join(A.lines)
    print(text)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")
        print(f"\n[audit written to {out}]")


if __name__ == "__main__":
    sys.exit(main())
