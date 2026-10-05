"""
Demonstrable Integration Test: NLI Entailment & Contradiction Evaluator (Fixing Defect D8).

Verifies that:
1. NLIEvaluator scores true claims with high entailment (truth_score > 0.8).
2. NLIEvaluator scores negated claims with high contradiction (truth_score < -0.8).
3. NLIEvaluator scores numeric swaps with contradiction, resolving D8 negation blindness.
"""

import unittest

from tahi.eval.nli_evaluator import NLIEvaluator


class TestNLIEvaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.evaluator = NLIEvaluator(model_name="cross-encoder/nli-deberta-v3-base")
        except Exception as e:
            raise unittest.SkipTest(f"NLI model download/init unavailable: {e}") from e

    def test_true_claim_is_entailed(self):
        evidence = "The compound was scheduled under the Controlled Substances Act in 2018."
        claim = "The compound was scheduled under the Controlled Substances Act."
        res = self.evaluator.score_pair(evidence, claim)
        self.assertGreater(res["truth_score"], 0.7)
        self.assertGreater(res["entailment"], 0.8)

    def test_negated_claim_is_contradicted(self):
        """Fixes Defect D8: Negated claims must score high contradiction / negative truth score."""
        evidence = "The compound was scheduled under the Controlled Substances Act in 2018."
        negated_claim = "The compound was not scheduled under the Controlled Substances Act."
        res = self.evaluator.score_pair(evidence, negated_claim)
        self.assertLess(res["truth_score"], -0.7)
        self.assertGreater(res["contradiction"], 0.8)

    def test_numeric_swap_is_contradicted(self):
        evidence = "The default maximum file size is 10 MiB per upload request."
        false_numeric_claim = "The maximum file size is 57 MiB"
        res = self.evaluator.score_pair(evidence, false_numeric_claim)
        self.assertLess(res["truth_score"], -0.5)
        self.assertGreater(res["contradiction"], 0.7)


if __name__ == "__main__":
    unittest.main()
