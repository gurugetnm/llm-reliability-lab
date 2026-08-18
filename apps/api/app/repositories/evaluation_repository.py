"""Data access for `EvaluationRun` / `EvaluationResult`. No business
rules here — see `app/services/evaluation_service.py`.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.evaluation import EvaluationResult, EvaluationRun
from app.models.experiment import RunItem


async def get_evaluation_run(
    db: AsyncSession, evaluation_run_id: uuid.UUID
) -> EvaluationRun | None:
    return await db.get(EvaluationRun, evaluation_run_id)


async def create_evaluation_run(db: AsyncSession, **fields: Any) -> EvaluationRun:
    evaluation_run = EvaluationRun(**fields)
    db.add(evaluation_run)
    await db.flush()
    await db.refresh(evaluation_run)
    return evaluation_run


async def list_evaluation_runs_page(
    db: AsyncSession, *, run_id: uuid.UUID | None, offset: int, limit: int
) -> tuple[list[EvaluationRun], int]:
    filters = [EvaluationRun.run_id == run_id] if run_id is not None else []

    total = (await db.execute(select(func.count(EvaluationRun.id)).where(*filters))).scalar_one()
    result = await db.execute(
        select(EvaluationRun)
        .where(*filters)
        .order_by(EvaluationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def list_evaluation_results_page(
    db: AsyncSession, evaluation_run_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[EvaluationResult], int]:
    total = (
        await db.execute(
            select(func.count(EvaluationResult.id)).where(
                EvaluationResult.evaluation_run_id == evaluation_run_id
            )
        )
    ).scalar_one()
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.evaluation_run_id == evaluation_run_id)
        .order_by(EvaluationResult.created_at)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def list_evaluation_results_page_with_context(
    db: AsyncSession, evaluation_run_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[tuple[EvaluationResult, RunItem]], int]:
    """Same page of results as `list_evaluation_results_page`, but each
    paired with its `RunItem` (and that item's `DatasetItem`, eagerly
    joined) — one indexed query, not N+1 — so the API can show the
    input/expected/actual output a score is actually about (Part 31)
    without the evaluator itself ever touching the database."""
    total = (
        await db.execute(
            select(func.count(EvaluationResult.id)).where(
                EvaluationResult.evaluation_run_id == evaluation_run_id
            )
        )
    ).scalar_one()
    result = await db.execute(
        select(EvaluationResult, RunItem)
        .join(RunItem, RunItem.id == EvaluationResult.run_item_id)
        .options(joinedload(RunItem.dataset_item))
        .where(EvaluationResult.evaluation_run_id == evaluation_run_id)
        .order_by(EvaluationResult.created_at)
        .offset(offset)
        .limit(limit)
    )
    return [(row.EvaluationResult, row.RunItem) for row in result.all()], total


async def list_all_evaluation_results(
    db: AsyncSession, evaluation_run_id: uuid.UUID
) -> list[EvaluationResult]:
    """Unpaginated — used by aggregate metric calculation and run
    comparison, both of which need every result, not one page of them."""
    result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == evaluation_run_id)
    )
    return list(result.scalars().all())


async def get_dataset_item_ids_for_run_items(
    db: AsyncSession, run_item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """Maps `RunItem.id -> RunItem.dataset_item_id` for a batch of run
    items — one indexed query rather than N+1, used to pair two
    EvaluationRuns' results by the dataset item they scored (Part 32)."""
    if not run_item_ids:
        return {}
    result = await db.execute(
        select(RunItem.id, RunItem.dataset_item_id).where(RunItem.id.in_(run_item_ids))
    )
    return {row.id: row.dataset_item_id for row in result.all()}
