# Pre-registration — does supplied graph knowledge lift the model?

Written before the run. Criteria fixed here, before results are seen.

## The question

Retrieval quality is not the question this answers. Assume retrieval is solved —
hand the model exactly the facts that a perfect graph lookup would have returned,
and ask whether its answers improve.

If they do not, no injection mechanism can help, because the knowledge itself is
not what the model is missing. If they do, the size of that lift is the ceiling
any retrieval and any injection channel is working toward, and partnering out the
linking problem becomes a reasonable move.

## Items

MetaQA 3-hop test questions. For each, a 3-hop path from the seed entity to a
gold answer is walked in `kb.txt`, so the supporting facts are structurally
guaranteed rather than generated. The three facts on that path, verbalised, are
the "gold facts".

Gold answers are MetaQA's own answer set for the question.

## Conditions — same questions, same model, same decoding

| condition | prompt contains |
|---|---|
| `closed` | the question only |
| `random` | the question + 3 facts about unrelated entities |
| `gold` | the question + the 3 facts on the path to the answer |
| `gold+noise` | the question + the 3 gold facts mixed with 7 unrelated ones |

`random` separates "the model uses the facts" from "any extra text changes the
output". `gold+noise` is the realistic case: correct facts present but not alone,
which is what any real retrieval returns.

## Metrics

- **exact match** — the generated answer contains any gold answer, after
  lowercase/punctuation normalisation.
- **token F1** — against the best-matching gold answer.
- **gold answer log-probability** — the model's log-probability of the gold answer
  string, teacher-forced. Reported because exact match reads 0.000 whether a
  signal is absent or merely too weak to cross the decoding threshold, and those
  are different findings. MAAILMA hit exactly that: four conditions, four 0.000s,
  no separation.

## Criteria, fixed now

1. **Validity gate.** If `closed` exact match is already above 0.5, the model
   knows these answers without help and the items cannot measure supplied
   knowledge. Report and switch to a corpus the model has not memorised.
2. **The floor test.** `gold` must beat `closed` on exact match by more than 2 SE.
   If it does not, supplied knowledge does not help this model on this task, and
   the injection programme has no ceiling to work toward. That is a stop result
   and is reported as one.
3. **The control.** `gold` must beat `random` by more than 2 SE. If `random` lifts
   as much as `gold`, the model is reacting to the presence of text rather than to
   its content — MAAILMA measured precisely this (+0.136 from random chunks,
   identical to exact retrieval), so it is a live possibility, not a formality.
4. **The realistic case.** `gold+noise` is reported against both `gold` and
   `closed`. It is not a pass/fail gate; it measures how much of the lift survives
   imperfect retrieval.
5. SE = sqrt(p(1-p)/n), printed per cell.

## What each outcome means

- `gold` ≫ `closed`, `gold` > `random` → supplied knowledge helps; the lift is the
  target for the injection channel, and buying linking from a partner is rational.
- `gold` ≈ `closed` → the model cannot use these facts. Stop.
- `gold` ≈ `random` > `closed` → the lift is an artefact of prompt length or
  format, not of content. Stop, and re-examine every prior result that did not
  carry this control.
