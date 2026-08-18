"""`EvaluationRunner` — drives one `EvaluationRun` to completion.

    EvaluationRun
       -> EvaluationRunner
       -> EvaluatorRegistry   (reliability_lab_evaluation)
       -> Evaluator
       -> EvaluationResult

Deliberately shaped like `app.experiments.runner.ExperimentRunner`:
independent of FastAPI (a plain session factory, not a request-scoped
session), bounded concurrency via `asyncio.Semaphore`, per-item failure
isolation, cooperative cancellation, and SSE progress via an in-process
event bus. The evaluator itself never touches the database — this class
builds `EvaluationInput` from a `RunItem`/`DatasetItem` pair and is the
only thing that talks to SQLAlchemy.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from reliability_lab_evaluation import (
    EmbeddingProvider,
    EvaluationInput,
    Evaluator,
    EvaluatorExecutionError,
    EvaluatorRegistry,
)
from reliability_lab_llm import LLMProvider
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.session import AsyncSessionLocal
from app.evaluation.events import evaluation_event_bus
from app.models.enums import EvaluationResultStatus, EvaluationRunStatus
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.models.experiment import Experiment, ExperimentRun, RunItem

logger = logging.getLogger(__name__)

#: One item's evaluation may not run forever — a hung judge/embedding
#: call must not hold a concurrency slot (and the run) open indefinitely.
DEFAULT_ITEM_TIMEOUT_SECONDS = 60.0

SessionFactory = Callable[[], AsyncSession]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EvaluationRunner:
    def __init__(
        self,
        *,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        session_factory: SessionFactory = AsyncSessionLocal,
        item_timeout_seconds: float = DEFAULT_ITEM_TIMEOUT_SECONDS,
    ) -> None:
        self._llm_provider = llm_provider
        self._embedding_provider = embedding_provider
        self._session_factory = session_factory
        self._item_timeout_seconds = item_timeout_seconds

    async def execute_evaluation(self, evaluation_run_id: uuid.UUID) -> None:
        try:
            evaluator, experiment_name, items = await self._start(evaluation_run_id)
        except _EvaluationAlreadyHandled:
            return

        evaluation_run = await self._load(evaluation_run_id)
        semaphore = asyncio.Semaphore(evaluation_run.concurrency)
        await asyncio.gather(
            *(
                self._process_item(evaluation_run_id, evaluator, item, experiment_name, semaphore)
                for item in items
            )
        )

        await self._finish(evaluation_run_id)

    # --- run-level bookkeeping --------------------------------------------

    async def _start(self, evaluation_run_id: uuid.UUID) -> tuple[Evaluator, str, list[RunItem]]:
        async with self._session_factory() as db:
            evaluation_run = await db.get(EvaluationRun, evaluation_run_id)
            if evaluation_run is None:
                logger.warning("EvaluationRun %s vanished before it could start", evaluation_run_id)
                raise _EvaluationAlreadyHandled

            if evaluation_run.cancel_requested:
                evaluation_run.status = EvaluationRunStatus.CANCELLED
                evaluation_run.completed_at = _utcnow()
                await db.commit()
                await evaluation_event_bus.publish(
                    evaluation_run_id,
                    "evaluation_cancelled",
                    {"evaluation_run_id": str(evaluation_run_id)},
                )
                raise _EvaluationAlreadyHandled

            experiment_run = await db.get(ExperimentRun, evaluation_run.run_id)
            experiment = (
                await db.get(Experiment, experiment_run.experiment_id) if experiment_run else None
            )
            if experiment_run is None or experiment is None:
                evaluation_run.status = EvaluationRunStatus.FAILED
                evaluation_run.completed_at = _utcnow()
                await db.commit()
                await evaluation_event_bus.publish(
                    evaluation_run_id,
                    "evaluation_completed",
                    _snapshot(evaluation_run),
                )
                raise _EvaluationAlreadyHandled

            items = list(
                (
                    await db.execute(
                        select(RunItem)
                        .options(joinedload(RunItem.dataset_item))
                        .where(RunItem.run_id == evaluation_run.run_id)
                        .order_by(RunItem.created_at)
                    )
                )
                .scalars()
                .all()
            )

            evaluator = EvaluatorRegistry.create(
                evaluation_run.evaluator_type,
                evaluation_run.configuration,
                embedding_provider=self._embedding_provider,
                llm_provider=self._llm_provider,
            )

            evaluation_run.total_items = len(items)
            if not items:
                # Nothing to evaluate — Part 42's "empty dataset" case.
                # Complete immediately rather than starting a run that
                # will never produce a single item event.
                evaluation_run.status = EvaluationRunStatus.COMPLETED
                evaluation_run.started_at = _utcnow()
                evaluation_run.completed_at = _utcnow()
                await db.commit()
                await evaluation_event_bus.publish(
                    evaluation_run_id, "evaluation_completed", _snapshot(evaluation_run)
                )
                raise _EvaluationAlreadyHandled

            evaluation_run.status = EvaluationRunStatus.RUNNING
            evaluation_run.started_at = _utcnow()
            await db.commit()
            experiment_name = experiment.name

        await evaluation_event_bus.publish(
            evaluation_run_id,
            "evaluation_started",
            {"evaluation_run_id": str(evaluation_run_id), "total_items": len(items)},
        )
        return evaluator, experiment_name, items

    async def _load(self, evaluation_run_id: uuid.UUID) -> EvaluationRun:
        async with self._session_factory() as db:
            evaluation_run = await db.get(EvaluationRun, evaluation_run_id)
            assert evaluation_run is not None
            return evaluation_run

    async def _finish(self, evaluation_run_id: uuid.UUID) -> None:
        async with self._session_factory() as db:
            evaluation_run = await db.get(EvaluationRun, evaluation_run_id)
            assert evaluation_run is not None
            if evaluation_run.cancel_requested:
                evaluation_run.status = EvaluationRunStatus.CANCELLED
            elif evaluation_run.failed_items == 0:
                evaluation_run.status = EvaluationRunStatus.COMPLETED
            else:
                evaluation_run.status = EvaluationRunStatus.COMPLETED_WITH_ERRORS
            evaluation_run.completed_at = _utcnow()
            await db.commit()
            snapshot = _snapshot(evaluation_run)
            final_status = evaluation_run.status

        await evaluation_event_bus.publish(
            evaluation_run_id,
            "evaluation_cancelled"
            if final_status == EvaluationRunStatus.CANCELLED
            else "evaluation_completed",
            snapshot,
        )

    # --- per-item processing -----------------------------------------------

    async def _process_item(
        self,
        evaluation_run_id: uuid.UUID,
        evaluator: Evaluator,
        run_item: RunItem,
        experiment_name: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            if await self._is_cancelled(evaluation_run_id):
                await self._record_cancelled(evaluation_run_id, run_item)
                return
            await self._evaluate_one(evaluation_run_id, evaluator, run_item, experiment_name)

    async def _is_cancelled(self, evaluation_run_id: uuid.UUID) -> bool:
        async with self._session_factory() as db:
            result = await db.execute(
                select(EvaluationRun.cancel_requested).where(EvaluationRun.id == evaluation_run_id)
            )
            return bool(result.scalar_one_or_none())

    async def _record_cancelled(self, evaluation_run_id: uuid.UUID, run_item: RunItem) -> None:
        evaluation_run = await self._load(evaluation_run_id)
        result_id = await self._insert_result(
            evaluation_run_id,
            run_item.id,
            status=EvaluationResultStatus.CANCELLED,
            metric_name=evaluation_run.evaluator_type,
            evaluator=_evaluator_label(evaluation_run),
        )
        await self._bump_counters(evaluation_run_id, successful=False, failed=False)
        await evaluation_event_bus.publish(
            evaluation_run_id,
            "evaluation_item_failed",
            {
                "evaluation_run_id": str(evaluation_run_id),
                "evaluation_result_id": str(result_id),
                "status": "cancelled",
            },
        )
        await self._publish_progress(evaluation_run_id)

    async def _evaluate_one(
        self,
        evaluation_run_id: uuid.UUID,
        evaluator: Evaluator,
        run_item: RunItem,
        experiment_name: str,
    ) -> None:
        evaluation_run = await self._load(evaluation_run_id)
        item_input = _build_input(run_item, experiment_name)

        try:
            output = await asyncio.wait_for(
                evaluator.evaluate(item_input), timeout=self._item_timeout_seconds
            )
        except TimeoutError:
            result_id = await self._insert_result(
                evaluation_run_id,
                run_item.id,
                status=EvaluationResultStatus.FAILED,
                metric_name=evaluation_run.evaluator_type,
                evaluator=_evaluator_label(evaluation_run),
                error_message=(
                    f"Evaluation did not complete within {self._item_timeout_seconds:.0f}s"
                ),
            )
            await self._on_item_failed(evaluation_run_id, result_id)
            return
        except EvaluatorExecutionError as exc:
            result_id = await self._insert_result(
                evaluation_run_id,
                run_item.id,
                status=EvaluationResultStatus.FAILED,
                metric_name=evaluation_run.evaluator_type,
                evaluator=_evaluator_label(evaluation_run),
                error_message=str(exc),
                details=exc.details,
            )
            await self._on_item_failed(evaluation_run_id, result_id)
            return
        except Exception as exc:  # noqa: BLE001 — one item's failure must never abort the run
            logger.warning(
                "EvaluationRun %s item %s failed: %s", evaluation_run_id, run_item.id, exc
            )
            result_id = await self._insert_result(
                evaluation_run_id,
                run_item.id,
                status=EvaluationResultStatus.FAILED,
                metric_name=evaluation_run.evaluator_type,
                evaluator=_evaluator_label(evaluation_run),
                error_message=str(exc)[:2000],
            )
            await self._on_item_failed(evaluation_run_id, result_id)
            return

        result_id = await self._insert_result(
            evaluation_run_id,
            run_item.id,
            status=EvaluationResultStatus.SUCCEEDED,
            metric_name=evaluation_run.evaluator_type,
            evaluator=_evaluator_label(evaluation_run),
            score=output.score,
            passed=output.passed,
            reason=output.reason,
            details=output.details,
        )
        await self._bump_counters(evaluation_run_id, successful=True, failed=False)
        await evaluation_event_bus.publish(
            evaluation_run_id,
            "evaluation_item_completed",
            {
                "evaluation_run_id": str(evaluation_run_id),
                "evaluation_result_id": str(result_id),
                "status": "succeeded",
                "score": output.score,
                "passed": output.passed,
            },
        )
        await self._publish_progress(evaluation_run_id)

    async def _on_item_failed(self, evaluation_run_id: uuid.UUID, result_id: uuid.UUID) -> None:
        await self._bump_counters(evaluation_run_id, successful=False, failed=True)
        await evaluation_event_bus.publish(
            evaluation_run_id,
            "evaluation_item_failed",
            {
                "evaluation_run_id": str(evaluation_run_id),
                "evaluation_result_id": str(result_id),
                "status": "failed",
            },
        )
        await self._publish_progress(evaluation_run_id)

    async def _publish_progress(self, evaluation_run_id: uuid.UUID) -> None:
        async with self._session_factory() as db:
            evaluation_run = await db.get(EvaluationRun, evaluation_run_id)
            assert evaluation_run is not None
            snapshot = _snapshot(evaluation_run)
        await evaluation_event_bus.publish(evaluation_run_id, "evaluation_progress", snapshot)

    # --- EvaluationResult persistence ---------------------------------------

    async def _insert_result(
        self,
        evaluation_run_id: uuid.UUID,
        run_item_id: uuid.UUID,
        *,
        status: EvaluationResultStatus,
        metric_name: str,
        evaluator: str,
        score: float | None = None,
        passed: bool | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> uuid.UUID:
        async with self._session_factory() as db:
            result = EvaluationResult(
                evaluation_run_id=evaluation_run_id,
                run_item_id=run_item_id,
                status=status,
                metric_name=metric_name,
                score=score,
                passed=passed,
                reason=reason,
                details=details or {},
                evaluator=evaluator,
                error_message=error_message,
            )
            db.add(result)
            await db.commit()
            await db.refresh(result)
            return result.id

    async def _bump_counters(
        self, evaluation_run_id: uuid.UUID, *, successful: bool, failed: bool
    ) -> None:
        """A single atomic `UPDATE` (server-side arithmetic), same
        reasoning as `ExperimentRunner._bump_counters`: safe under
        concurrent items finishing at once."""
        async with self._session_factory() as db:
            await db.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id == evaluation_run_id)
                .values(
                    completed_items=EvaluationRun.completed_items + 1,
                    successful_items=EvaluationRun.successful_items + (1 if successful else 0),
                    failed_items=EvaluationRun.failed_items + (1 if failed else 0),
                )
            )
            await db.commit()


class _EvaluationAlreadyHandled(Exception):
    """Internal control-flow signal: `_start` already finalized the
    evaluation run (pre-cancelled, its ExperimentRun vanished, or its
    dataset produced zero RunItems) — nothing left to do."""


def _build_input(run_item: RunItem, experiment_name: str) -> EvaluationInput:
    dataset_item = run_item.dataset_item
    return EvaluationInput(
        input=dataset_item.input if dataset_item is not None else None,
        expected_output=dataset_item.expected_output if dataset_item is not None else None,
        actual_output=run_item.response,
        actual_structured_output=run_item.structured_output,
        metadata=(dataset_item.item_metadata or {}) if dataset_item is not None else {},
        model=run_item.model,
        experiment_name=experiment_name,
        run_id=str(run_item.run_id),
    )


def _evaluator_label(evaluation_run: EvaluationRun) -> str:
    return f"{evaluation_run.evaluator_type}:{evaluation_run.evaluator_version}"


def _snapshot(evaluation_run: EvaluationRun) -> dict[str, Any]:
    return {
        "evaluation_run_id": str(evaluation_run.id),
        "status": evaluation_run.status,
        "total_items": evaluation_run.total_items,
        "completed_items": evaluation_run.completed_items,
        "successful_items": evaluation_run.successful_items,
        "failed_items": evaluation_run.failed_items,
    }
