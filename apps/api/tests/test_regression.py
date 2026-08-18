"""Unit tests for `reliability_lab_evaluation.regression`."""

import pytest
from reliability_lab_evaluation import detect_regression


class TestDetectRegression:
    def test_no_change_is_not_a_regression(self) -> None:
        result = detect_regression(0.9, 0.9)
        assert result.regression_detected is False
        assert result.difference == 0.0

    def test_improvement_is_not_a_regression(self) -> None:
        result = detect_regression(0.8, 0.9)
        assert result.regression_detected is False
        assert result.difference == pytest.approx(0.1)

    def test_drop_beyond_threshold_is_a_regression(self) -> None:
        result = detect_regression(0.91, 0.84, threshold=0.05)
        assert result.regression_detected is True
        assert result.difference == pytest.approx(-0.07)

    def test_drop_within_threshold_is_not_a_regression(self) -> None:
        result = detect_regression(0.91, 0.88, threshold=0.05)
        assert result.regression_detected is False

    def test_exactly_at_threshold_is_not_a_regression(self) -> None:
        result = detect_regression(0.90, 0.85, threshold=0.05)
        assert result.regression_detected is False

    def test_relative_difference_computed(self) -> None:
        result = detect_regression(0.5, 0.25)
        assert result.relative_difference == -0.5

    def test_relative_difference_none_when_baseline_zero(self) -> None:
        result = detect_regression(0.0, 0.5)
        assert result.relative_difference is None

    def test_lower_is_better_flips_direction(self) -> None:
        # e.g. a latency metric: candidate got slower -> regression.
        result = detect_regression(100.0, 150.0, threshold=10.0, higher_is_better=False)
        assert result.regression_detected is True

        result = detect_regression(100.0, 90.0, threshold=10.0, higher_is_better=False)
        assert result.regression_detected is False
