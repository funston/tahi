"""
Correctness and groundedness metrics -- measuring hallucination directly.

Token F1 answers "did the wording overlap?". The claim under test is
"structured world state makes the model assert fewer false things", and F1 is
a poor instrument for that: a fluent, well-worded, entirely fabricated answer
can score respectably, and a terse correct answer can score badly.

These metrics target the claim instead:

  fact_coverage      of the gold atomic facts, how many did the answer state?
                     -> completeness. Rewards saying the true things.

  groundedness       of the answer's content words, how many appear in the
                     evidence the system actually retrieved?
                     -> the inverse of hallucination. An answer asserting
                        content absent from its own evidence is unsupported,
                        whether or not it happens to be true.

  unsupported_rate   1 - groundedness. The headline "bullshit rate".

  abstention         on questions with no answer in the corpus, did the system
                     decline instead of inventing one?

Design note: these are deterministic lexical measures, not LLM-judged. That is
deliberate. An LLM judge introduces a second model whose version must be pinned
or the numbers stop being reproducible across runs, and judge drift is
indistinguishable from system improvement. Lexical measures are weaker per-item
but stable, cheap, and auditable -- and for a paired A/B between two arms on the
same items, stability matters more than per-item precision.

`llm_judge_prompt()` is provided for an optional stronger pass, but the primary
metrics must not depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import normalize_answer

# Words that carry no factual content -- their presence in evidence proves
# nothing about whether a claim is supported.
_STOPWORDS = frozenset("""
a an the and or but if then than that this these those there here of in on at to
for from by with as is are was were be been being do does did have has had will
would shall should can could may might must not no nor so such only own same too
very s t just don now it its it's i you he she they we who whom which what when
where why how all any both each few more most other some own about into over
under again further once during before after above below up down out off
""".split())


@dataclass
class FaithfulnessScores:
    fact_coverage: float
    groundedness: float
    unsupported_rate: float
    n_gold_facts: int
    n_facts_covered: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "fact_coverage": self.fact_coverage,
            "groundedness": self.groundedness,
            "unsupported_rate": self.unsupported_rate,
            "n_gold_facts": self.n_gold_facts,
            "n_facts_covered": self.n_facts_covered,
        }


def _content_words(text: str) -> set[str]:
    """Normalized content tokens -- stopwords and pure numbers-as-noise removed."""
    return {
        w for w in normalize_answer(text).split()
        if w not in _STOPWORDS and len(w) > 2
    }


def fact_coverage(answer: str, gold_facts: list[str], threshold: float = 0.6) -> tuple[float, int]:
    """Fraction of gold atomic facts the answer actually states.

    A fact counts as covered when `threshold` of its content words appear in the
    answer. This is the completeness half of correctness: an answer that is
    perfectly grounded but only states one of four required facts is incomplete,
    and `completeness`-category questions exist precisely to catch that.

    Returns (coverage, n_covered).
    """
    if not gold_facts:
        return 0.0, 0
    answer_words = _content_words(answer)
    covered = 0
    for fact in gold_facts:
        fact_words = _content_words(fact)
        if not fact_words:
            continue
        overlap = len(fact_words & answer_words) / len(fact_words)
        if overlap >= threshold:
            covered += 1
    return covered / len(gold_facts), covered


def groundedness(answer: str, evidence: str) -> float:
    """Fraction of the answer's content words that appear in its own evidence.

    This is the hallucination measure, and it is deliberately scored against
    *retrieved* evidence rather than gold: the question is whether the system
    asserted something its own context did not support. A system that retrieves
    badly and then invents a plausible answer scores low here even when the
    invention happens to be correct -- which is the behaviour we want to
    penalise, because it is unreliable by construction.

    Returns 1.0 for an empty answer (nothing asserted, nothing unsupported).
    """
    answer_words = _content_words(answer)
    if not answer_words:
        return 1.0
    evidence_words = _content_words(evidence)
    if not evidence_words:
        return 0.0
    return len(answer_words & evidence_words) / len(answer_words)


def score_faithfulness(answer: str, evidence: str, gold_facts: list[str]) -> FaithfulnessScores:
    cov, n_cov = fact_coverage(answer, gold_facts)
    ground = groundedness(answer, evidence)
    return FaithfulnessScores(
        fact_coverage=cov,
        groundedness=ground,
        unsupported_rate=1.0 - ground,
        n_gold_facts=len(gold_facts),
        n_facts_covered=n_cov,
    )


def llm_judge_prompt(question: str, answer: str, gold_answer: str) -> str:
    """Optional stronger correctness pass. NOT used for primary metrics.

    If this is ever run, the judge model and version MUST be recorded in the run
    manifest -- otherwise a judge upgrade is indistinguishable from a system
    improvement, and the comparison silently stops being valid across runs.
    """
    return (
        "You are grading a factual answer. Reply with exactly one word: "
        "CORRECT, PARTIAL, or WRONG.\n\n"
        f"QUESTION: {question}\n"
        f"REFERENCE ANSWER: {gold_answer}\n"
        f"CANDIDATE ANSWER: {answer}\n\n"
        "CORRECT = states the same facts as the reference. "
        "PARTIAL = some correct facts, missing others, nothing false. "
        "WRONG = asserts something the reference contradicts, or fabricates.\n"
        "VERDICT:"
    )
