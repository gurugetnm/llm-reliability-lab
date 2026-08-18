"""Regression detection — a simple engineering comparison between a
baseline and candidate score, not a statistical significance test
(Part 33 is explicit about that distinction).
"""

from __future__ import annotations

from typing import NamedTuple

#: Absolute-score-difference default. Deliberately a plain, documented
#: default rather than something "smart" — the whole point of Part 33 is
#: a transparent, configurable comparison a developer can reason about.
DEFAULT_REGRESSION_THRESHOLD = 0.05


class RegressionResult(NamedTuple):
    baseline_score: float
    candidate_score: float
    difference: float
    """candidate - baseline. Negative means the candidate scored lower."""
    relative_difference: float | None
    """difference / abs(baseline_score), or None if baseline_score is 0."""
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
    regression_detected = signed_difference < -threshold

    return RegressionResult(
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        difference=difference,
        relative_difference=relative_difference,
        threshold=threshold,
        higher_is_better=higher_is_better,
        regression_detected=regression_detected,
    )
