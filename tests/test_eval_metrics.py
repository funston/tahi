"""
Regression tests pinning the metric pathologies that invalidated earlier runs.

Each test named `test_regression_*` encodes a specific way a previous harness
reported a number that was not a measurement. They exist so the same defect
cannot silently return.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.eval.metrics import (  # noqa: E402
    exact_match,
    normalize_answer,
    supporting_fact_recall,
    token_f1,
)
from tahi.eval.stats import (  # noqa: E402
    bootstrap_paired_delta,
    mcnemar_p_value,
    minimum_detectable_effect,
    required_n,
)


class MetricRegressionTests(unittest.TestCase):
    def test_regression_em_is_not_substring_containment(self):
        """EM must not fire when the reference merely appears inside the prediction.

        The prior harness used `ref in pred or pred in ref`, which scored EM=1.0
        for every arm on HotpotQA -- including the zero-retrieval baseline --
        while token F1 was 0.028. EM 1.0 with F1 0.028 is impossible.
        """
        pred = "Based on the provided context, the answer is Paris."
        ref = "Paris"
        self.assertEqual(exact_match(pred, ref), 0.0)
        self.assertGreater(token_f1(pred, ref), 0.0)

        # And the reverse direction, which was the more damaging half.
        self.assertEqual(exact_match("Paris", "Paris, the capital of France"), 0.0)

    def test_regression_em_and_f1_cannot_disagree_at_the_extremes(self):
        """EM=1.0 implies F1=1.0. Any pair violating this is a broken metric."""
        for pred, ref in [
            ("Paris", "Paris"),
            ("the Paris", "Paris"),          # article stripped
            ("Paris.", "Paris"),             # punctuation stripped
            ("  PARIS  ", "paris"),          # case + whitespace
        ]:
            if exact_match(pred, ref) == 1.0:
                self.assertEqual(token_f1(pred, ref), 1.0, f"{pred!r} vs {ref!r}")

    def test_regression_f1_uses_multiset_not_set(self):
        """Repeating a correct token must not earn credit repeatedly.

        Set-intersection F1 scores a degenerate repetition far too highly.
        """
        pred = "Paris Paris Paris Paris Paris"
        ref = "Paris is the capital of France"
        f1 = token_f1(pred, ref)
        self.assertLess(f1, 0.4, "multiset F1 should penalize repetition")

    def test_normalization_matches_squad(self):
        self.assertEqual(normalize_answer("The Quick, Brown Fox!"), "quick brown fox")
        self.assertEqual(normalize_answer("  an   Apple  "), "apple")

    def test_empty_prediction_scores_zero(self):
        self.assertEqual(exact_match("", "Paris"), 0.0)
        self.assertEqual(token_f1("", "Paris"), 0.0)

    def test_supporting_fact_recall(self):
        self.assertEqual(supporting_fact_recall(["a", "b", "c"], ["a", "b"]), 1.0)
        self.assertEqual(supporting_fact_recall(["a"], ["a", "b"]), 0.5)
        self.assertEqual(supporting_fact_recall([], ["a"]), 0.0)


class StatsRegressionTests(unittest.TestCase):
    def test_regression_tiny_delta_is_not_significant(self):
        """The headline deltas from the retracted runs must fail significance.

        TAHI L1 vs Standard RAG was reported as F1 0.194 vs 0.107 on n=20 and
        presented as a win. Per-item QA F1 is highly variable (many 0.0s, a few
        near 1.0), and at n=20 that spread swamps a 0.087 mean difference.
        """
        import random

        rng = random.Random(0)
        # What defeats a paired test is variance in the *difference*, not in the
        # scores. Graph expansion is exactly that shape: it recovers the answer
        # on some queries and injects distractors on others (the MuSiQue run in
        # this repo went -33%). Most items unchanged, a few swing hard each way.
        arm_a, arm_b = [], []
        for _ in range(20):
            base = 0.0 if rng.random() < 0.6 else rng.uniform(0.2, 0.9)
            roll = rng.random()
            if roll < 0.15:
                delta = rng.uniform(0.5, 0.9)      # graph found the bridge entity
            elif roll < 0.28:
                delta = -rng.uniform(0.4, 0.8)     # graph pulled in a distractor
            else:
                delta = 0.0                        # no effect either way
            arm_a.append(base)
            arm_b.append(max(0.0, min(1.0, base + delta)))

        result = bootstrap_paired_delta(
            arm_a, arm_b, arm_a="RAG", arm_b="TAHI", n_resamples=2000
        )
        self.assertFalse(
            result.ci_excludes_zero,
            f"n=20 must not yield significance at realistic variance: {result.verdict()}",
        )
        self.assertIn("NOT SIGNIFICANT", result.verdict())

    def test_clear_effect_is_detected(self):
        a = [0.0] * 100
        b = [1.0] * 100
        result = bootstrap_paired_delta(a, b, n_resamples=2000)
        self.assertTrue(result.ci_excludes_zero)
        self.assertAlmostEqual(result.delta, 1.0, places=6)

    def test_mcnemar_only_counts_discordant_pairs(self):
        # Identical arms: nothing to distinguish them.
        self.assertEqual(mcnemar_p_value([1.0, 0.0, 1.0], [1.0, 0.0, 1.0]), 1.0)
        # Strongly discordant: b wins every disagreement.
        p = mcnemar_p_value([0.0] * 12, [1.0] * 12)
        self.assertLess(p, 0.05)

    def test_regression_power_check_flags_underpowered_n(self):
        """At n=20 a 0.014 F1 delta was never detectable. Make that checkable."""
        mde_at_20 = minimum_detectable_effect(20)
        self.assertGreater(mde_at_20, 0.014 * 5, "n=20 cannot resolve a 0.014 delta")
        self.assertGreater(required_n(0.014), 5000)

    def test_mismatched_arm_lengths_raise(self):
        with self.assertRaises(ValueError):
            bootstrap_paired_delta([1.0, 0.0], [1.0])


if __name__ == "__main__":
    unittest.main()
