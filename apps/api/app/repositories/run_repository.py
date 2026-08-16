"""Data access for `ExperimentRun` / `RunItem`. No business rules here —
see `app/services/run_service.py`.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import ExperimentRun, RunItem


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> ExperimentRun | None:
    return await db.get(ExperimentRun, run_id)


async def create_run(db: AsyncSession, **fields: Any) -> ExperimentRun:
    run = ExperimentRun(**fields)
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def list_runs_page(
    db: AsyncSession, experiment_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[ExperimentRun], int]:
    total = (
        await db.execute(
            select(func.count(ExperimentRun.id)).where(ExperimentRun.experiment_id == experiment_id)
        )
    ).scalar_one()
    result = await db.execute(
        select(ExperimentRun)
        .where(ExperimentRun.experiment_id == experiment_id)
        .order_by(ExperimentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def list_run_items_page(
    db: AsyncSession, run_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[RunItem], int]:
    total = (
        await db.execute(select(func.count(RunItem.id)).where(RunItem.run_id == run_id))
    ).scalar_one()
    result = await db.execute(
        select(RunItem)
        .where(RunItem.run_id == run_id)
        .order_by(RunItem.created_at)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total
