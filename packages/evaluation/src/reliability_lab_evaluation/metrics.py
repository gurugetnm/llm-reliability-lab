"""Aggregate metric calculation over a set of `EvaluationResult`s.

Pure functions over plain `ResultRecord`s (not ORM rows) so they're
testable without a database and reusable outside `apps/api` — the same
reason `regression.py` and the evaluators themselves take plain values.
"""

from __future__ import annotations

import statistics
from typing import Literal, NamedTuple

ResultStatus = Literal["succeeded", "failed", "cancelled"]


class ResultRecord(NamedTuple):
    """The minimal shape `calculate_aggregate_metrics` needs from one
    `EvaluationResult` row."""

    status: ResultStatus
    score: float | None
    passed: bool | None


class DistributionBucket(NamedTuple):
    range_start: float
    range_end: float
    #: `count` (a `tuple` builtin method name) is avoided so mypy doesn't
    #: see it as an incompatible override of `tuple.count`.
    item_count: int


class AggregateMetrics(NamedTuple):
    total: int
    #: Results that completed with a non-null score.
    evaluated: int
    #: Results whose evaluator raised (a real failure, not a low score).
    failed: int
    #: Count of passed=true, or None if this metric never produces pass/fail.
    passed: int | None
    pass_rate: float | None
    mean_score: float | None
    median_score: float | None
    min_score: float | None
    max_score: float | None
    distribution: tuple[DistributionBucket, ...] | None


#: Number of equal-width buckets used for `distribution` — every built-in
#: evaluator normalizes its score to [0, 1], so ten buckets gives a
#: readable decile histogram (Part 27).
DISTRIBUTION_BUCKETS = 10


def calculate_aggregate_metrics(results: list[ResultRecord]) -> AggregateMetrics:
    total = len(results)
    failed = sum(1 for r in results if r.status == "failed")
    succeeded = [r for r in results if r.status == "succeeded"]

    scores = [r.score for r in succeeded if r.score is not None]
    pass_flags = [r.passed for r in succeeded if r.passed is not None]

    passed_count = sum(1 for p in pass_flags if p) if pass_flags else None
    pass_rate = (
        (passed_count / len(pass_flags)) if pass_flags and passed_count is not None else None
    )

    mean_score = statistics.fmean(scores) if scores else None
    median_score = statistics.median(scores) if scores else None
    min_score = min(scores) if scores else None
    max_score = max(scores) if scores else None
    distribution = _score_distribution(scores) if scores else None

    return AggregateMetrics(
        total=total,
        evaluated=len(scores),
        failed=failed,
        passed=passed_count,
        pass_rate=pass_rate,
        mean_score=mean_score,
        median_score=median_score,
        min_score=min_score,
        max_score=max_score,
        distribution=distribution,
    )


def _score_distribution(scores: list[float]) -> tuple[DistributionBucket, ...]:
    width = 1.0 / DISTRIBUTION_BUCKETS
    counts = [0] * DISTRIBUTION_BUCKETS
    for score in scores:
        # Clamp: a similarity score can technically fall outside [0, 1]
        # (e.g. slightly negative cosine similarity) — bucket it at the
        # nearest edge rather than raising or silently dropping it.
        clamped = min(max(score, 0.0), 1.0)
        index = min(int(clamped / width), DISTRIBUTION_BUCKETS - 1)
        counts[index] += 1
    return tuple(
        DistributionBucket(
            range_start=round(i * width, 2),
            range_end=round((i + 1) * width, 2),
            item_count=counts[i],
        )
        for i in range(DISTRIBUTION_BUCKETS)
    )
