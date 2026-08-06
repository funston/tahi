"""
Answer-quality metrics for OCTO evaluation.

These follow the official SQuAD / HotpotQA definitions. They are deliberately
strict: `exact_match` means the full normalized token sequence is equal, not
that one string contains the other. Containment-based "EM" can report 1.0 for a
prediction that is mostly wrong, which makes it useless as a headline metric.

All functions here are pure and side-effect free so they can be unit-pinned.
"""

from __future__ import annotations

import re
import string
from collections import Counter

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_answer(text: str) -> str:
    """SQuAD normalization: lowercase, strip punctuation, articles, extra whitespace."""
    text = text.lower()
    text = text.translate(_PUNCT_TABLE)
    text = _ARTICLES.sub(" ", text)
    return " ".join(text.split())


def get_tokens(text: str) -> list[str]:
    return normalize_answer(text).split()


def exact_match(prediction: str, reference: str) -> float:
    """1.0 only if the full normalized sequences are identical.

    Deliberately NOT containment. `exact_match("Based on the context, Paris",
    "Paris")` is 0.0 -- the model did not produce the answer exactly, and the
    token F1 below is the metric that gives it partial credit.
    """
    return float(normalize_answer(prediction) == normalize_answer(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Multiset token F1 (SQuAD definition).

    Uses Counter, not set: a prediction that repeats a correct token five times
    should not receive credit five times. Set-intersection F1 silently inflates
    scores on repetitive generations.
    """
    pred_tokens = get_tokens(prediction)
    ref_tokens = get_tokens(reference)

    # Degenerate case: if either side is empty, they only agree if both are.
    if not pred_tokens or not ref_tokens:
        return float(pred_tokens == ref_tokens)

    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def score_answer(prediction: str, reference: str) -> dict[str, float]:
    """Return both metrics for one prediction/reference pair."""
    return {
        "exact_match": exact_match(prediction, reference),
        "token_f1": token_f1(prediction, reference),
    }


def supporting_fact_recall(retrieved_ids: list[str], gold_ids: list[str]) -> float:
    """Fraction of gold supporting facts present in what the system retrieved.

    This is the diagnostic that explains *why* an answer-quality delta happened.
    If two arms have equal recall, any answer-F1 difference between them is not
    coming from retrieval quality.
    """
    if not gold_ids:
        return 0.0
    got = set(retrieved_ids)
    return sum(1 for g in gold_ids if g in got) / len(gold_ids)
