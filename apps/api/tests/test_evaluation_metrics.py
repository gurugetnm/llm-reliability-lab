"""Unit tests for `reliability_lab_evaluation.metrics`."""

from reliability_lab_evaluation import ResultRecord, calculate_aggregate_metrics


class TestAggregateMetrics:
    def test_empty_results(self) -> None:
        metrics = calculate_aggregate_metrics([])
        assert metrics.total == 0
        assert metrics.evaluated == 0
        assert metrics.mean_score is None
        assert metrics.pass_rate is None
        assert metrics.distribution is None

    def test_basic_aggregation(self) -> None:
        results = [
            ResultRecord("succeeded", 1.0, True),
            ResultRecord("succeeded", 0.0, False),
            ResultRecord("succeeded", 0.5, True),
        ]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.total == 3
        assert metrics.evaluated == 3
        assert metrics.passed == 2
        assert metrics.pass_rate == 2 / 3
        assert metrics.mean_score == 0.5
        assert metrics.median_score == 0.5
        assert metrics.min_score == 0.0
        assert metrics.max_score == 1.0

    def test_failed_results_counted_separately_from_low_scores(self) -> None:
        results = [
            ResultRecord("succeeded", 0.0, False),  # a real (low) score, not a failure
            ResultRecord("failed", None, None),  # the evaluator itself errored
        ]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.total == 2
        assert metrics.evaluated == 1
        assert metrics.failed == 1
        assert metrics.mean_score == 0.0

    def test_cancelled_results_excluded_from_scoring(self) -> None:
        results = [ResultRecord("cancelled", None, None), ResultRecord("succeeded", 1.0, True)]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.total == 2
        assert metrics.evaluated == 1
        assert metrics.failed == 0

    def test_metric_without_pass_fail_reports_no_pass_rate(self) -> None:
        # e.g. an evaluator that only ever returns a score, no passed flag.
        results = [ResultRecord("succeeded", 0.7, None), ResultRecord("succeeded", 0.9, None)]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.mean_score == 0.8
        assert metrics.passed is None
        assert metrics.pass_rate is None

    def test_distribution_buckets_scores_into_deciles(self) -> None:
        results = [
            ResultRecord("succeeded", 0.05, None),
            ResultRecord("succeeded", 0.15, None),
            ResultRecord("succeeded", 0.95, None),
            ResultRecord("succeeded", 1.0, None),
        ]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.distribution is not None
        assert len(metrics.distribution) == 10
        assert metrics.distribution[0].item_count == 1  # 0.05
        assert metrics.distribution[1].item_count == 1  # 0.15
        assert metrics.distribution[9].item_count == 2  # 0.95, 1.0
        assert sum(bucket.item_count for bucket in metrics.distribution) == 4

    def test_distribution_clamps_out_of_range_scores(self) -> None:
        # A cosine similarity can technically be slightly negative.
        results = [ResultRecord("succeeded", -0.01, None)]
        metrics = calculate_aggregate_metrics(results)
        assert metrics.distribution is not None
        assert metrics.distribution[0].item_count == 1
