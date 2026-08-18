"""Business logic for evaluations: validating the target ExperimentRun is
completed, validating evaluator configuration, starting an EvaluationRun
(then handing off to `EvaluationRunner` as a background task), listing
evaluations/results, cancellation, and aggregate metrics.

Routes stay thin — see `app/repositories/evaluation_repository.py` for
the rule-free query layer this builds on. Mirrors
`app/services/run_service.py`'s shape.
"""

import asyncio
import logging
import uuid

from reliability_lab_evaluation import (
    AggregateMetrics,
    EmbeddingProvider,
    EvaluationConfigError,
    EvaluatorRegistry,
    ResultRecord,
    calculate_aggregate_metrics,
)
from reliability_lab_llm import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import AsyncSessionLocal
from app.evaluation.concurrency import clamp_concurrency
from app.evaluation.lifecycle import can_transition
from app.evaluation.runner import EvaluationRunner
from app.experiments.lifecycle import is_terminal as is_experiment_run_terminal
from app.models.enums import EvaluationRunStatus
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.repositories import evaluation_repository, run_repository
from app.schemas.evaluation import EvaluationRunCreate

logger = logging.getLogger(__name__)

#: Holds strong references to in-flight background evaluation tasks so
#: they aren't garbage-collected mid-run — same
#: `asyncio.create_task`-must-be-referenced concern as
#: `run_service._background_tasks`.
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn_evaluation(
    evaluation_run_id: uuid.UUID,
    *,
    llm_provider: LLMProvider,
    embedding_provider: EmbeddingProvider,
) -> None:
    runner = EvaluationRunner(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        session_factory=AsyncSessionLocal,
    )
    task = asyncio.create_task(runner.execute_evaluation(evaluation_run_id))
    _background_tasks.add(task)

    def _on_done(finished: asyncio.Task[None]) -> None:
        _background_tasks.discard(finished)
        if finished.cancelled():
            return
        exc = finished.exception()
        if exc is not None:
            logger.exception("Evaluation run %s crashed", evaluation_run_id, exc_info=exc)

    task.add_done_callback(_on_done)


async def create_evaluation(
    db: AsyncSession,
    data: EvaluationRunCreate,
    *,
    llm_provider: LLMProvider,
    embedding_provider: EmbeddingProvider,
) -> EvaluationRun:
    experiment_run = await run_repository.get_run(db, data.run_id)
    if experiment_run is None:
        raise NotFoundError(f"Experiment run '{data.run_id}' was not found")
    if not is_experiment_run_terminal(experiment_run.status):
        raise ValidationError(
            f"Experiment run '{data.run_id}' is still {experiment_run.status} — "
            "it must finish before it can be evaluated."
        )

    try:
        evaluator_cls = EvaluatorRegistry.get(data.evaluator_type)
        validated_config = EvaluatorRegistry.validate_config(
            data.evaluator_type, data.configuration
        )
    except EvaluationConfigError as exc:
        raise ValidationError(str(exc)) from exc

    evaluation_run = await evaluation_repository.create_evaluation_run(
        db,
        run_id=data.run_id,
        name=data.name,
        evaluator_type=data.evaluator_type,
        evaluator_version=evaluator_cls.metadata.version,
        configuration=validated_config.model_dump(mode="json"),
        concurrency=clamp_concurrency(data.concurrency),
    )
    _spawn_evaluation(
        evaluation_run.id, llm_provider=llm_provider, embedding_provider=embedding_provider
    )
    return evaluation_run


async def get_evaluation_or_404(db: AsyncSession, evaluation_run_id: uuid.UUID) -> EvaluationRun:
    evaluation_run = await evaluation_repository.get_evaluation_run(db, evaluation_run_id)
    if evaluation_run is None:
        raise NotFoundError(f"Evaluation run '{evaluation_run_id}' was not found")
    return evaluation_run


async def list_evaluations(
    db: AsyncSession, *, run_id: uuid.UUID | None, page: int, page_size: int
) -> tuple[list[EvaluationRun], int]:
    offset = (page - 1) * page_size
    return await evaluation_repository.list_evaluation_runs_page(
        db, run_id=run_id, offset=offset, limit=page_size
    )


async def list_evaluation_results(
    db: AsyncSession, evaluation_run_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[EvaluationResult], int]:
    await get_evaluation_or_404(db, evaluation_run_id)
    offset = (page - 1) * page_size
    return await evaluation_repository.list_evaluation_results_page(
        db, evaluation_run_id, offset=offset, limit=page_size
    )


async def cancel_evaluation(db: AsyncSession, evaluation_run_id: uuid.UUID) -> EvaluationRun:
    evaluation_run = await get_evaluation_or_404(db, evaluation_run_id)
    if not can_transition(evaluation_run.status, EvaluationRunStatus.CANCELLED):
        raise ValidationError(
            f"Evaluation run '{evaluation_run_id}' is already {evaluation_run.status} "
            "and can no longer be cancelled"
        )
    evaluation_run.cancel_requested = True
    await db.flush()
    await db.refresh(evaluation_run)
    return evaluation_run


async def get_evaluation_metrics(
    db: AsyncSession, evaluation_run_id: uuid.UUID
) -> AggregateMetrics:
    await get_evaluation_or_404(db, evaluation_run_id)
    results = await evaluation_repository.list_all_evaluation_results(db, evaluation_run_id)
    records = [ResultRecord(status=r.status.value, score=r.score, passed=r.passed) for r in results]
    return calculate_aggregate_metrics(records)
