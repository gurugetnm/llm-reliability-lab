"""Regression detection — a simple engineering comparison between a
baseline and candidate score, not a statistical significance test
(Part 33 is explicit about that distinction).
"""

from __future__ import annotations

import math
from typing import NamedTuple

#: Absolute-score-difference default. Deliberately a plain, documented
#: default rather than something "smart" — the whole point of Part 33 is
#: a transparent, configurable comparison a developer can reason about.
DEFAULT_REGRESSION_THRESHOLD = 0.05

#: Floating-point tolerance for the threshold comparison — without it,
#: e.g. `0.90 - 0.85` (which is `0.05000000000000004` in IEEE 754) would
#: register as a regression against a `threshold=0.05` even though the
#: two scores are, for any practical purpose, exactly at the threshold.
_EPSILON = 1e-9


class RegressionResult(NamedTuple):
    baseline_score: float
    candidate_score: float
    #: candidate - baseline. Negative means the candidate scored lower.
    difference: float
    #: difference / abs(baseline_score), or None if baseline_score is 0.
    relative_difference: float | None
    threshold: float
    higher_is_better: bool
    regression_detected: bool


def detect_regression(
    baseline_score: float,
    candidate_score: float,
    *,
    threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    higher_is_better: bool = True,
) -> RegressionResult:
    """Flags a regression when the candidate is worse than the baseline
    by more than `threshold` (in score units, not a percentage)."""
    difference = candidate_score - baseline_score
    relative_difference = (difference / abs(baseline_score)) if baseline_score != 0 else None

    signed_difference = difference if higher_is_better else -difference
    regression_detected = signed_difference < -threshold and not math.isclose(
        signed_difference, -threshold, abs_tol=_EPSILON
    )

    return RegressionResult(
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        difference=difference,
        relative_difference=relative_difference,
        threshold=threshold,
        higher_is_better=higher_is_better,
        regression_detected=regression_detected,
    )
