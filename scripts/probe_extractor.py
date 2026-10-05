#!/usr/bin/env python
"""
Falsification probe: is claim extraction grammar, or is it smuggled knowledge?

The objection this answers: "if an LLM can fact-check the answer, why did an LLM
generate a wrong answer in the first place?" That objection is fatal to any
design where a model judges truth -- and it is exactly why the NLI evaluator
failed here, scoring +0.826 with AND without supporting evidence.

The claim-extraction design escapes it only if the extractor is doing grammar
rather than recall. So test that directly: give it sentences about compounds and
genes that CANNOT exist in any training corpus, with grammar identical to
sentences about real ones.

    real:  "Aspirin does not bind COX-1."
    fake:  "Zelphamide does not bind KRT9X."

Both must yield polarity DENIED. If accuracy on fake entities matches accuracy
on real ones, the extractor is parsing. If it collapses on fake entities, it was
leaning on world knowledge, the design is circular, and the objection stands.

Deliberately run with a SMALL model (Qwen2.5-1.5B by default). A model too
small to know pharmacology is the strongest available evidence that no
pharmacology is being used.

Format failures are reported separately from comprehension failures. A model
that understands the sentence but cannot emit JSON is a tooling problem, not a
refutation, and conflating the two would misattribute the result.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.validate.claim_extractor import (  # noqa: E402
    ClaimExtractionError,
    ClaimExtractor,
)

RELATIONS = ["binds", "treats", "causes", "participates_in"]

# Grammar conditions. `template` takes {s}=subject {o}=object {d}=distractor.
# `gold` is the expected polarity for the claim about {o}.
CONDITIONS = [
    ("affirm_simple",      "{s} binds {o}.",                          "affirmed"),
    ("deny_simple",        "{s} does not bind {o}.",                  "denied"),
    ("deny_contraction",   "{s} doesn't bind {o}.",                   "denied"),
    ("deny_never",         "{s} never binds {o}.",                    "denied"),
    ("deny_lexical",       "{s} lacks affinity for {o}.",             "denied"),
    ("deny_except",        "{s} binds everything except {o}.",        "denied"),
    ("double_negation",    "{s} does not fail to bind {o}.",          "affirmed"),
    ("scoped_negation",    "{s} binds {d}, not {o}.",                 "denied"),
    ("scoped_affirm",      "{s} binds {o}, not {d}.",                 "affirmed"),
]

REAL = {"s": "Aspirin", "o": "COX-1", "d": "COX-2"}
# Nonsense strings: no plausible pretraining occurrence, so no knowledge to lean on.
FAKE = {"s": "Zelphamide", "o": "KRT9X", "d": "BRN4Q"}


@dataclass
class Result:
    condition: str
    arm: str
    sentence: str
    gold: str
    got: str | None
    format_ok: bool
    raw: str = ""

    @property
    def correct(self) -> bool:
        return self.format_ok and self.got == self.gold


class LocalHFClient:
    """Minimal LLMClient-shaped wrapper over a local transformers model."""

    def __init__(self, model_name: str, device: str = "cuda",
                 max_new_tokens: int = 256):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype=torch.float32).to(device).eval()
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.model_name = model_name

    def complete(self, prompt: str, system: str | None = None):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        text = self.tok.apply_chat_template(msgs, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **ids, max_new_tokens=self.max_new_tokens,
                do_sample=False,                 # temperature 0: reproducible
                pad_token_id=self.tok.pad_token_id,
            )
        gen = out[0][ids["input_ids"].shape[1]:]

        class _R:
            text = self.tok.decode(gen, skip_special_tokens=True)
        return _R()


def score(extractor: ClaimExtractor, sentence: str, target_object: str,
          gold: str, condition: str, arm: str) -> Result:
    """Did the extractor get the polarity of the claim about `target_object`?"""
    try:
        claims = extractor.extract(sentence)
    except ClaimExtractionError as e:
        return Result(condition, arm, sentence, gold, None, False, str(e)[:160])
    except Exception as e:  # noqa: BLE001
        return Result(condition, arm, sentence, gold, None, False, str(e)[:160])

    tgt = target_object.lower().replace("-", "")
    for c in claims:
        if tgt in c.object.lower().replace("-", ""):
            return Result(condition, arm, sentence, gold, c.polarity, True)
    # Parsed fine but never mentioned the target: a comprehension miss.
    return Result(condition, arm, sentence, gold, None, True,
                  raw=json.dumps([c.to_dict() for c in claims])[:200])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", default="benchmarks/results/probe_extractor.json")
    args = ap.parse_args()

    print(f"Loading {args.model} ...", flush=True)
    client = LocalHFClient(args.model, device=args.device)
    extractor = ClaimExtractor(llm=client, relations=RELATIONS, strict=False)

    results: list[Result] = []
    for _rep in range(args.repeats):
        for cond, template, gold in CONDITIONS:
            for arm, ents in (("real", REAL), ("fake", FAKE)):
                sentence = template.format(**ents)
                r = score(extractor, sentence, ents["o"], gold, cond, arm)
                results.append(r)
                mark = "ok " if r.correct else "MISS"
                print(f"  [{mark}] {arm:4s} {cond:18s} gold={gold:9s} "
                      f"got={r.got}  | {sentence}", flush=True)

    def acc(arm: str) -> tuple[int, int]:
        rows = [r for r in results if r.arm == arm]
        return sum(1 for r in rows if r.correct), len(rows)

    r_ok, r_n = acc("real")
    f_ok, f_n = acc("fake")
    fmt_fail = sum(1 for r in results if not r.format_ok)

    print()
    print("=" * 68)
    print("EXTRACTOR PROBE")
    print("=" * 68)
    print(f"  model                 {args.model}")
    print(f"  real entities         {r_ok}/{r_n}  ({r_ok / max(r_n,1):.1%})")
    print(f"  fake entities         {f_ok}/{f_n}  ({f_ok / max(f_n,1):.1%})")
    print(f"  delta (real - fake)   {r_ok / max(r_n,1) - f_ok / max(f_n,1):+.1%}")
    print(f"  JSON format failures  {fmt_fail}/{len(results)}")
    print()
    print("  INTERPRETATION")
    if fmt_fail > len(results) * 0.3:
        print("    Too many format failures to conclude anything about")
        print("    comprehension. This is a tooling result, not a refutation:")
        print("    retry with a larger extractor or constrained decoding.")
    elif abs(r_ok / max(r_n, 1) - f_ok / max(f_n, 1)) <= 0.10:
        print("    Fake-entity accuracy tracks real-entity accuracy. The")
        print("    extractor is parsing GRAMMAR, not recalling knowledge, so")
        print("    the catch-22 does not apply: a model that cannot know the")
        print("    fact can still report what the sentence claims.")
    else:
        print("    Fake-entity accuracy is materially WORSE. The extractor is")
        print("    leaning on world knowledge, the design is circular, and the")
        print("    objection stands. Do not build on this.")
    print()

    per_cond: dict[str, dict] = {}
    for cond, _t, _g in CONDITIONS:
        rows = [r for r in results if r.condition == cond]
        per_cond[cond] = {
            arm: sum(1 for r in rows if r.arm == arm and r.correct)
            for arm in ("real", "fake")
        }
    print(f"  PER CONDITION (correct out of {args.repeats} each)")
    for cond, d in per_cond.items():
        print(f"    {cond:18s} real={d['real']}  fake={d['fake']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": args.model,
        "real_correct": r_ok, "real_n": r_n,
        "fake_correct": f_ok, "fake_n": f_n,
        "format_failures": fmt_fail,
        "per_condition": per_cond,
        "rows": [vars(r) for r in results],
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
