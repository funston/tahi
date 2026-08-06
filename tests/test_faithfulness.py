"""
Tests for the faithfulness metrics -- including what they provably CANNOT do.

The negation tests below are the reason this file exists. `groundedness` is
lexical overlap between a claim and its supporting evidence, so it is blind to
polarity by construction: "the limit is 10 MiB" and "the limit is NOT 10 MiB"
share every content word. That blindness was discovered by running a 45-minute
fragment-verification experiment (AUC 0.449 on negated claims -- below chance)
when a unit test would have shown it in milliseconds.

Encoding a known limitation as a passing test is deliberate. A metric with an
unwritten weakness gets used as though it has none; a metric whose weakness is
named in a test cannot be quietly promoted to something it is not.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.eval.faithfulness import (  # noqa: E402
    fact_coverage, groundedness, score_faithfulness,
)


class GroundednessTests(unittest.TestCase):
    def test_fully_supported_claim_scores_high(self):
        evidence = "The upload limit is 10 MiB per file and 50 MiB per request."
        self.assertGreater(groundedness("The upload limit is 10 MiB", evidence), 0.9)

    def test_unsupported_claim_scores_low(self):
        evidence = "The team discussed catering options for the offsite."
        self.assertLess(groundedness("Revenue grew 40% in Q3", evidence), 0.3)

    def test_empty_answer_is_vacuously_grounded(self):
        """Nothing asserted means nothing unsupported."""
        self.assertEqual(groundedness("", "any evidence"), 1.0)

    def test_no_evidence_means_nothing_is_supported(self):
        self.assertEqual(groundedness("A specific factual claim", ""), 0.0)

    def test_stopwords_do_not_manufacture_support(self):
        """Overlap on function words must not read as evidential support."""
        evidence = "The and or but if then this that with from"
        self.assertLess(groundedness("The revenue was 40 million", evidence), 0.5)


class KnownLimitationTests(unittest.TestCase):
    """Documented blind spots. These PASS -- they pin what the metric can't do."""

    def test_groundedness_cannot_detect_negation(self):
        """A claim and its negation score identically.

        Measured consequence: AUC 0.449 on negated fragments, i.e. below chance,
        because the negated form is marginally longer and picks up an extra
        token match. Any use of this metric to assess truthfulness -- as opposed
        to topical support -- is invalid, and it must not be used in a setting
        where "was scheduled" versus "was not scheduled" is the question.

        Fix requires an entailment signal (NLI) or a structured contradiction
        query, not lexical overlap.
        """
        evidence = "The compound was scheduled under the Controlled Substances Act."
        claim = "The compound was scheduled under the Controlled Substances Act."
        negated = "The compound was not scheduled under the Controlled Substances Act."

        self.assertGreater(groundedness(claim, evidence), 0.9)
        self.assertGreater(
            groundedness(negated, evidence), 0.9,
            "If this ever drops, groundedness has gained polarity awareness and "
            "this test should become an assertion that negation scores LOW.",
        )

    def test_groundedness_barely_detects_numeric_substitution(self):
        """Swapping a number leaves almost all content words intact.

        "10 MiB" -> "57 MiB" changes one token out of several, so the score
        moves only slightly. Numeric precision needs value comparison, not
        overlap -- which is what a structured (subject, predicate, value) lookup
        against the graph would provide.
        """
        evidence = "The default maximum file size is 10 MiB per upload request."
        true_claim = "The maximum file size is 10 MiB"
        false_claim = "The maximum file size is 57 MiB"

        drop = groundedness(true_claim, evidence) - groundedness(false_claim, evidence)
        self.assertLess(
            drop, 0.35,
            "Numeric substitution is only weakly detectable by lexical overlap; "
            "if this becomes large the metric changed and the fragment "
            "verification results must be recomputed.",
        )


class FactCoverageTests(unittest.TestCase):
    def test_counts_only_facts_actually_stated(self):
        facts = [
            "The per-file limit is 10 MiB.",
            "The total request limit is 50 MiB.",
        ]
        answer = "The per-file limit is 10 MiB."
        cov, n = fact_coverage(answer, facts)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(cov, 0.5)

    def test_all_facts_covered(self):
        facts = ["Revenue was 40 million.", "Growth was 12 percent."]
        answer = "Revenue was 40 million and growth was 12 percent."
        cov, n = fact_coverage(answer, facts)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(cov, 1.0)

    def test_no_gold_facts_is_zero_not_a_crash(self):
        self.assertEqual(fact_coverage("anything", []), (0.0, 0))


class ScoreFaithfulnessTests(unittest.TestCase):
    def test_unsupported_rate_is_the_complement_of_groundedness(self):
        s = score_faithfulness("The limit is 10 MiB",
                               "The limit is 10 MiB per file.", ["The limit is 10 MiB."])
        self.assertAlmostEqual(s.unsupported_rate, 1.0 - s.groundedness)
        self.assertEqual(s.n_gold_facts, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
