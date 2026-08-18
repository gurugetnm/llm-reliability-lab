"""Run evaluation comparison and regression detection (Parts 32-34).

Pairs two `EvaluationRun`s' results by the dataset item they scored (the
same idea `apps/web`'s Phase 3 run-compare page uses for RunItems, moved
server-side here so regression detection has one source of truth), then
compares their aggregate metrics via `reliability_lab_evaluation.regression`.
"""

import uuid
from dataclasses import dataclass

from reliability_lab_evaluation import (
    AggregateMetrics,
    EvaluatorRegistry,
    RegressionResult,
    ResultRecord,
    calculate_aggregate_metrics,
    detect_regression,
)
from reliability_lab_evaluation.regression import DEFAULT_REGRESSION_THRESHOLD
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.repositories import evaluation_repository
from app.services import evaluation_service


@dataclass
class ItemComparison:
    dataset_item_id: uuid.UUID | None
    baseline_result_id: uuid.UUID | None
    candidate_result_id: uuid.UUID | None
    baseline_score: float | None
    candidate_score: float | None
    difference: float | None


@dataclass
class EvaluationComparison:
    baseline: EvaluationRun
    candidate: EvaluationRun
    baseline_metrics: AggregateMetrics
    candidate_metrics: AggregateMetrics
    regression: RegressionResult | None
    items: list[ItemComparison]


def _to_records(results: list[EvaluationResult]) -> list[ResultRecord]:
    return [ResultRecord(status=r.status.value, score=r.score, passed=r.passed) for r in results]


def _pair_by_dataset_item(
    baseline_results: list[EvaluationResult],
    candidate_results: list[EvaluationResult],
    dataset_item_by_run_item: dict[uuid.UUID, uuid.UUID | None],
) -> list[ItemComparison]:
    candidate_by_dataset_item = {
        dataset_item_by_run_item.get(r.run_item_id): r
        for r in candidate_results
        if dataset_item_by_run_item.get(r.run_item_id) is not None
    }

    comparisons: list[ItemComparison] = []
    matched_candidate_ids: set[uuid.UUID] = set()

    for baseline in baseline_results:
        dataset_item_id = dataset_item_by_run_item.get(baseline.run_item_id)
        match = candidate_by_dataset_item.get(dataset_item_id) if dataset_item_id else None
        difference = (
            match.score - baseline.score
            if match is not None and match.score is not None and baseline.score is not None
            else None
        )
        comparisons.append(
            ItemComparison(
                dataset_item_id=dataset_item_id,
                baseline_result_id=baseline.id,
                candidate_result_id=match.id if match else None,
                baseline_score=baseline.score,
                candidate_score=match.score if match else None,
                difference=difference,
            )
        )
        if match is not None:
            matched_candidate_ids.add(match.id)

    for candidate in candidate_results:
        if candidate.id in matched_candidate_ids:
            continue
        comparisons.append(
            ItemComparison(
                dataset_item_id=dataset_item_by_run_item.get(candidate.run_item_id),
                baseline_result_id=None,
                candidate_result_id=candidate.id,
                baseline_score=None,
                candidate_score=candidate.score,
                difference=None,
            )
        )

    return comparisons


async def compare_evaluations(
    db: AsyncSession,
    baseline_id: uuid.UUID,
    candidate_id: uuid.UUID,
    *,
    regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD,
) -> EvaluationComparison:
    baseline = await evaluation_service.get_evaluation_or_404(db, baseline_id)
    candidate = await evaluation_service.get_evaluation_or_404(db, candidate_id)

    if baseline.evaluator_type != candidate.evaluator_type:
        raise ValidationError(
            f"Cannot compare evaluations using different evaluators "
            f"('{baseline.evaluator_type}' vs. '{candidate.evaluator_type}') — "
            "re-run the same evaluator against both experiment runs first."
        )

    baseline_results = await evaluation_repository.list_all_evaluation_results(db, baseline_id)
    candidate_results = await evaluation_repository.list_all_evaluation_results(db, candidate_id)

    baseline_metrics = calculate_aggregate_metrics(_to_records(baseline_results))
    candidate_metrics = calculate_aggregate_metrics(_to_records(candidate_results))

    regression = None
    if baseline_metrics.mean_score is not None and candidate_metrics.mean_score is not None:
        higher_is_better = EvaluatorRegistry.get(baseline.evaluator_type).metadata.higher_is_better
        regression = detect_regression(
            baseline_metrics.mean_score,
            candidate_metrics.mean_score,
            threshold=regression_threshold,
            higher_is_better=higher_is_better,
        )

    run_item_ids = [r.run_item_id for r in (*baseline_results, *candidate_results)]
    dataset_item_by_run_item = await evaluation_repository.get_dataset_item_ids_for_run_items(
        db, run_item_ids
    )
    items = _pair_by_dataset_item(baseline_results, candidate_results, dataset_item_by_run_item)

    return EvaluationComparison(
        baseline=baseline,
        candidate=candidate,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        regression=regression,
        items=items,
    )
