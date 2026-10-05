"""
Statistical significance for paired benchmark arms.

A delta without a confidence interval is not a result. Every comparison between
two arms in this repo must go through one of these functions before it is
reported, because the arms are *paired* -- both systems answer the same items,
so unpaired tests throw away the pairing and lose power.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass


@dataclass
class PairedComparison:
    """Result of comparing two arms on the same items."""

    arm_a: str
    arm_b: str
    n: int
    mean_a: float
    mean_b: float
    delta: float                 # mean_b - mean_a
    ci_low: float
    ci_high: float
    ci_excludes_zero: bool
    p_value: float | None        # McNemar, binary outcomes only
    test: str

    def verdict(self) -> str:
        if not self.ci_excludes_zero:
            return (
                f"NOT SIGNIFICANT: {self.arm_b} vs {self.arm_a} delta={self.delta:+.4f}, "
                f"95% CI [{self.ci_low:+.4f}, {self.ci_high:+.4f}] includes zero (n={self.n})."
            )
        direction = "BETTER" if self.delta > 0 else "WORSE"
        return (
            f"{direction}: {self.arm_b} vs {self.arm_a} delta={self.delta:+.4f}, "
            f"95% CI [{self.ci_low:+.4f}, {self.ci_high:+.4f}] (n={self.n})."
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "verdict": self.verdict()}


def bootstrap_paired_delta(
    scores_a: list[float],
    scores_b: list[float],
    *,
    arm_a: str = "A",
    arm_b: str = "B",
    n_resamples: int = 10_000,
    seed: int = 0,
    alpha: float = 0.05,
) -> PairedComparison:
    """Paired bootstrap CI on the mean difference (b - a).

    Resamples *item indices*, keeping both arms' scores for an item together.
    This preserves the pairing and is valid for continuous metrics like F1.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(f"Paired arms must have equal length: {len(scores_a)} != {len(scores_b)}")
    n = len(scores_a)
    if n == 0:
        raise ValueError("Cannot compute statistics on zero items.")

    diffs = [b - a for a, b in zip(scores_a, scores_b, strict=False)]
    observed = sum(diffs) / n

    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()

    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[min(int((1 - alpha / 2) * n_resamples), n_resamples - 1)]

    binary = all(s in (0.0, 1.0) for s in scores_a + scores_b)
    p = mcnemar_p_value(scores_a, scores_b) if binary else None

    return PairedComparison(
        arm_a=arm_a,
        arm_b=arm_b,
        n=n,
        mean_a=sum(scores_a) / n,
        mean_b=sum(scores_b) / n,
        delta=observed,
        ci_low=lo,
        ci_high=hi,
        ci_excludes_zero=(lo > 0.0 or hi < 0.0),
        p_value=p,
        test=f"paired bootstrap ({n_resamples} resamples, seed={seed})"
        + (" + McNemar exact" if p is not None else ""),
    )


def mcnemar_p_value(scores_a: list[float], scores_b: list[float]) -> float:
    """Exact two-sided McNemar test for paired binary outcomes.

    Only the discordant pairs carry information: items where one arm was right
    and the other wrong. Items both arms got right (or both wrong) tell you
    nothing about which is better.
    """
    b = sum(1 for x, y in zip(scores_a, scores_b, strict=False) if x == 1.0 and y == 0.0)
    c = sum(1 for x, y in zip(scores_a, scores_b, strict=False) if x == 0.0 and y == 1.0)
    n = b + c
    if n == 0:
        return 1.0  # no discordant pairs: arms are indistinguishable

    # Exact binomial two-sided p under H0: P(discordant favours either) = 0.5
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def minimum_detectable_effect(n: int, std_dev: float = 0.4, power: float = 0.8) -> float:
    """Roughly, the smallest paired delta detectable at n items.

    Use this BEFORE running to check the experiment can answer the question.
    The default std_dev=0.4 approximates per-item F1 spread on QA benchmarks.

    Worked example: at n=20 with std=0.4 the MDE is ~0.25 F1. An observed delta
    of 0.014 at that n is indistinguishable from noise no matter how it is
    presented -- which is why "just run more samples" is not always the fix; you
    need to know how many more.
    """
    if n < 2:
        return float("inf")
    z_alpha, z_beta = 1.96, 0.84 if power == 0.8 else 1.28
    return (z_alpha + z_beta) * std_dev / math.sqrt(n)


def required_n(effect: float, std_dev: float = 0.4, power: float = 0.8) -> int:
    """Items needed to detect `effect` at 95% confidence and given power."""
    if effect <= 0:
        raise ValueError("effect must be positive")
    z_alpha, z_beta = 1.96, 0.84 if power == 0.8 else 1.28
    return math.ceil(((z_alpha + z_beta) * std_dev / effect) ** 2)
