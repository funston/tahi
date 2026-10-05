# Evaluation conventions

One set of metric names for this project. They are taken from published
conventions, not invented here. Anything not on this list does not go in a table.

The rule: if a number needs a sentence of explanation before it can be read, it
is a diagnostic, not a result, and it belongs in the appendix of a run log.

---

## Answer quality — MetaQA's own metrics

MetaQA defines these; we use them unchanged so our numbers are comparable to the
published literature on the same dataset.

| name | definition |
|---|---|
| **Hits@1** | The model's first answer is in the gold answer set. Exact string equality after lowercasing and stripping punctuation and articles. |
| **Full** | The model's whole answer set equals the gold answer set exactly. |

MetaQA 3-hop answers average ~1.45 entities per question against ~492 candidates,
so both metrics are set-valued and the prediction is parsed into a set before
scoring.

**Hits@1 is the headline.** `Full` is reported alongside it because a model that
names one correct language out of three is right on Hits@1 and wrong on Full, and
the gap between them is worth seeing.

### Retired
- **token F1** — SQuAD's word-overlap score. Gives partial credit for "Al Green"
  against "Al Pacino". Wrong instrument for entity answers. Not reported again.
- **containment matching** — "does a gold answer appear anywhere in the output".
  Scored "drama and crime" as correct for gold "Crime". Flattered every condition
  and the no-help baseline most. Replaced by Hits@1.

---

## Retrieval quality — BEIR conventions

| name | definition |
|---|---|
| **recall@k** | The wanted item is among the k returned. |
| **nDCG@10** | Rank-weighted relevance over the top 10. Used when comparing against published retrieval numbers. |

`k` is always stated. Two things can be "the wanted item" and they must be named
in the table header, never assumed:

- **recall@k (fact present)** — some returned passage contains the needed fact.
- **recall@k (exact record)** — the specific record about the entity asked about.

### Retired
- **"answer recall" / "target recall" / "continuation recall"** as bare names.
  They are all recall@k; the difference is which item counts, and that belongs in
  the header.

---

## Statistics

| name | when |
|---|---|
| **Wilson 95% interval** | Reported on every proportion. Correct near 0 and 1, where the textbook interval produces bounds outside [0,1]. |
| **McNemar's test** | Comparing two conditions scored on the same questions. Exact binomial when disagreements < 25, chi-square with continuity correction otherwise. |
| **Holm–Bonferroni** | Applied whenever more than one comparison is made against the same baseline. |

Every condition in a run answers the same questions, so the observations are
paired. Comparing two independent proportions throws that pairing away; it is the
wrong test and a weaker one. Report the **gained / lost** counts alongside the
p-value — how many questions flipped wrong-to-right and right-to-wrong — because
a net change of zero can hide a hundred flips in each direction.

---

## Diagnostics — never a headline number

| name | what it is | why it exists |
|---|---|---|
| **answer log-probability** | How much probability the model put on the correct answer, whether or not it said it. | Hits@1 is all-or-nothing. A model about to say the right answer and a model with no idea both score 0. This separates them. Used to tell "the signal is absent" from "the signal is too weak", which is a real distinction when debugging a channel that carries information into the model. |

Diagnostics appear in run logs. They do not appear in a summary table without the
result they are diagnosing next to them.

---

## Naming of experimental conditions

Plain description, no coined terms.

| use | not |
|---|---|
| no facts supplied | closed-book |
| correct facts supplied | gold / oracle |
| wrong facts supplied | random control |
| correct facts mixed with wrong ones | gold+noise / distractors |
