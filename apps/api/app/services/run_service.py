"""Business logic for experiment runs: starting a run (validating the
dataset isn't empty, then handing off to `ExperimentRunner` as a
background task), listing runs/run items, and cancellation.

Routes stay thin — see `app/repositories/run_repository.py` for the
rule-free query layer this builds on.
"""

import asyncio
import logging
import uuid

from reliability_lab_llm import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.experiments.concurrency import clamp_concurrency
from app.experiments.lifecycle import can_transition
from app.experiments.runner import ExperimentRunner
from app.models.enums import ExperimentRunStatus
from app.models.experiment import ExperimentRun, RunItem
from app.repositories import run_repository
from app.services import experiment_service

logger = logging.getLogger(__name__)

#: Holds strong references to in-flight background run tasks so they
#: aren't garbage-collected mid-run (a well-known `asyncio.create_task`
#: gotcha) — see https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task.
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn_run(provider: LLMProvider, run_id: uuid.UUID) -> None:
    task = asyncio.create_task(ExperimentRunner(provider).execute_run(run_id))
    _background_tasks.add(task)

    def _on_done(finished: asyncio.Task[None]) -> None:
        _background_tasks.discard(finished)
        if finished.cancelled():
            return
        exc = finished.exception()
        if exc is not None:
            logger.exception("Experiment run %s crashed", run_id, exc_info=exc)

    task.add_done_callback(_on_done)


async def start_run(
    db: AsyncSession, experiment_id: uuid.UUID, *, provider: LLMProvider, concurrency: int | None
) -> ExperimentRun:
    experiment, _, item_count, _ = await experiment_service.get_experiment_or_404(db, experiment_id)
    if item_count == 0:
        raise ValidationError(
            f"Dataset '{experiment.dataset_id}' has no items — add items before running "
            "this experiment."
        )

    run = await run_repository.create_run(
        db,
        experiment_id=experiment.id,
        model=experiment.model,
        generation_config=experiment.generation_config,
        total_items=item_count,
        concurrency=clamp_concurrency(concurrency),
    )
    _spawn_run(provider, run.id)
    return run


async def get_run_or_404(db: AsyncSession, run_id: uuid.UUID) -> ExperimentRun:
    run = await run_repository.get_run(db, run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' was not found")
    return run


async def list_runs(
    db: AsyncSession, experiment_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[ExperimentRun], int]:
    # 404s if the experiment doesn't exist, so `/experiments/{bad-id}/runs`
    # doesn't silently return an empty page.
    await experiment_service.get_experiment_or_404(db, experiment_id)
    offset = (page - 1) * page_size
    return await run_repository.list_runs_page(db, experiment_id, offset=offset, limit=page_size)


async def list_run_items(
    db: AsyncSession, run_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[RunItem], int]:
    await get_run_or_404(db, run_id)
    offset = (page - 1) * page_size
    return await run_repository.list_run_items_page(db, run_id, offset=offset, limit=page_size)


async def cancel_run(db: AsyncSession, run_id: uuid.UUID) -> ExperimentRun:
    run = await get_run_or_404(db, run_id)
    if not can_transition(run.status, ExperimentRunStatus.CANCELLED):
        raise ValidationError(
            f"Run '{run_id}' is already {run.status} and can no longer be cancelled"
        )
    run.cancel_requested = True
    await db.flush()
    await db.refresh(run)
    return run
