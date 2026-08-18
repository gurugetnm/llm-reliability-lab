"""Evaluation endpoints:

GET  /evaluators                  registered evaluator metadata
POST /evaluations                 start an evaluation run
GET  /evaluations                 list evaluation runs (optionally by run_id)
GET  /evaluations/{id}            evaluation run detail
GET  /evaluations/{id}/results    paginated evaluation results
GET  /evaluations/{id}/metrics    aggregate metrics
POST /evaluations/{id}/cancel     request cancellation
GET  /evaluations/{id}/events     live progress (SSE)
GET  /evaluations/compare         baseline vs. candidate + regression detection
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse
from reliability_lab_evaluation import AggregateMetrics, EvaluatorRegistry

from app.api.deps import DbSession
from app.core.sse import format_sse_event
from app.embeddings.dependencies import EmbeddingProviderDep
from app.evaluation.events import evaluation_event_bus
from app.evaluation.lifecycle import is_terminal
from app.llm.dependencies import LLMProviderDep
from app.models.evaluation import EvaluationRun
from app.schemas.evaluation import (
    DistributionBucketRead,
    EvaluationComparisonRead,
    EvaluationItemComparisonRead,
    EvaluationMetricsRead,
    EvaluationResultRead,
    EvaluationRunCreate,
    EvaluationRunRead,
    EvaluatorInfo,
    RegressionRead,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, PageParam, PageSizeParam
from app.services import evaluation_comparison_service, evaluation_service

router = APIRouter(tags=["evaluations"])


@router.get("/evaluators", response_model=list[EvaluatorInfo])
async def list_evaluators() -> list[EvaluatorInfo]:
    return [EvaluatorInfo.model_validate(m.model_dump()) for m in EvaluatorRegistry.list_metadata()]


@router.post("/evaluations", response_model=EvaluationRunRead, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    data: EvaluationRunCreate,
    db: DbSession,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
) -> EvaluationRunRead:
    evaluation_run = await evaluation_service.create_evaluation(
        db, data, llm_provider=llm_provider, embedding_provider=embedding_provider
    )
    return EvaluationRunRead.model_validate(evaluation_run)


@router.get("/evaluations", response_model=Page[EvaluationRunRead])
async def list_evaluations(
    db: DbSession,
    run_id: uuid.UUID | None = Query(default=None),
    page: PageParam = 1,
    page_size: PageSizeParam = DEFAULT_PAGE_SIZE,
) -> Page[EvaluationRunRead]:
    evaluations, total = await evaluation_service.list_evaluations(
        db, run_id=run_id, page=page, page_size=page_size
    )
    return Page(
        items=[EvaluationRunRead.model_validate(e) for e in evaluations],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/evaluations/compare", response_model=EvaluationComparisonRead)
async def compare_evaluations(
    db: DbSession,
    baseline_id: uuid.UUID = Query(...),
    candidate_id: uuid.UUID = Query(...),
    regression_threshold: float = Query(default=0.05, ge=0.0, le=1.0),
) -> EvaluationComparisonRead:
    comparison = await evaluation_comparison_service.compare_evaluations(
        db, baseline_id, candidate_id, regression_threshold=regression_threshold
    )
    return EvaluationComparisonRead(
        baseline=EvaluationRunRead.model_validate(comparison.baseline),
        candidate=EvaluationRunRead.model_validate(comparison.candidate),
        baseline_metrics=_metrics_read(comparison.baseline.id, comparison.baseline_metrics),
        candidate_metrics=_metrics_read(comparison.candidate.id, comparison.candidate_metrics),
        regression=(
            RegressionRead(
                baseline_score=comparison.regression.baseline_score,
                candidate_score=comparison.regression.candidate_score,
                difference=comparison.regression.difference,
                relative_difference=comparison.regression.relative_difference,
                threshold=comparison.regression.threshold,
                higher_is_better=comparison.regression.higher_is_better,
                regression_detected=comparison.regression.regression_detected,
            )
            if comparison.regression is not None
            else None
        ),
        items=[
            EvaluationItemComparisonRead(
                dataset_item_id=item.dataset_item_id,
                baseline_result_id=item.baseline_result_id,
                candidate_result_id=item.candidate_result_id,
                baseline_score=item.baseline_score,
                candidate_score=item.candidate_score,
                difference=item.difference,
            )
            for item in comparison.items
        ],
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRunRead)
async def get_evaluation(evaluation_id: uuid.UUID, db: DbSession) -> EvaluationRunRead:
    evaluation_run = await evaluation_service.get_evaluation_or_404(db, evaluation_id)
    return EvaluationRunRead.model_validate(evaluation_run)


@router.get("/evaluations/{evaluation_id}/results", response_model=Page[EvaluationResultRead])
async def list_evaluation_results(
    evaluation_id: uuid.UUID,
    db: DbSession,
    page: PageParam = 1,
    page_size: PageSizeParam = DEFAULT_PAGE_SIZE,
) -> Page[EvaluationResultRead]:
    results, total = await evaluation_service.list_evaluation_results(
        db, evaluation_id, page=page, page_size=page_size
    )
    return Page(
        items=[EvaluationResultRead.model_validate(r) for r in results],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/evaluations/{evaluation_id}/metrics", response_model=EvaluationMetricsRead)
async def get_evaluation_metrics(evaluation_id: uuid.UUID, db: DbSession) -> EvaluationMetricsRead:
    metrics = await evaluation_service.get_evaluation_metrics(db, evaluation_id)
    return _metrics_read(evaluation_id, metrics)


@router.post("/evaluations/{evaluation_id}/cancel", response_model=EvaluationRunRead)
async def cancel_evaluation(evaluation_id: uuid.UUID, db: DbSession) -> EvaluationRunRead:
    evaluation_run = await evaluation_service.cancel_evaluation(db, evaluation_id)
    return EvaluationRunRead.model_validate(evaluation_run)


@router.get("/evaluations/{evaluation_id}/events")
async def evaluation_events(evaluation_id: uuid.UUID, db: DbSession) -> StreamingResponse:
    evaluation_run = await evaluation_service.get_evaluation_or_404(db, evaluation_id)

    async def event_source() -> AsyncIterator[str]:
        # Already finished by the time a client subscribes — send one
        # terminal snapshot and close instead of hanging forever.
        if is_terminal(evaluation_run.status):
            event = (
                "evaluation_cancelled"
                if evaluation_run.status == "cancelled"
                else "evaluation_completed"
            )
            yield format_sse_event(event, _run_snapshot(evaluation_run))
            return

        queue = evaluation_event_bus.subscribe(evaluation_id)
        try:
            yield format_sse_event("evaluation_progress", _run_snapshot(evaluation_run))
            while True:
                item = await queue.get()
                yield format_sse_event(item.event, item.data)
                if item.event in ("evaluation_completed", "evaluation_cancelled"):
                    break
        finally:
            evaluation_event_bus.unsubscribe(evaluation_id, queue)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run_snapshot(evaluation_run: EvaluationRun) -> dict[str, object]:
    return {
        "evaluation_run_id": str(evaluation_run.id),
        "status": evaluation_run.status,
        "total_items": evaluation_run.total_items,
        "completed_items": evaluation_run.completed_items,
        "successful_items": evaluation_run.successful_items,
        "failed_items": evaluation_run.failed_items,
    }


def _metrics_read(evaluation_run_id: uuid.UUID, m: AggregateMetrics) -> EvaluationMetricsRead:
    return EvaluationMetricsRead(
        evaluation_run_id=evaluation_run_id,
        total=m.total,
        evaluated=m.evaluated,
        failed=m.failed,
        passed=m.passed,
        pass_rate=m.pass_rate,
        mean_score=m.mean_score,
        median_score=m.median_score,
        min_score=m.min_score,
        max_score=m.max_score,
        distribution=(
            [
                DistributionBucketRead(
                    range_start=b.range_start, range_end=b.range_end, item_count=b.item_count
                )
                for b in m.distribution
            ]
            if m.distribution is not None
            else None
        ),
    )
