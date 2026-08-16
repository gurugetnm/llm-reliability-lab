"""Data access for `Experiment`. No business rules here — see
`app/services/experiment_service.py`.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.dataset import Dataset, DatasetItem
from app.models.enums import ExperimentRunStatus
from app.models.experiment import Experiment, ExperimentRun

ExperimentRow = tuple[Experiment, Dataset, int, ExperimentRun | None]

#: `Dataset.name` and its item count, one row per dataset — joined
#: against `Experiment` so a listing never issues one count query per row.
_ITEM_COUNTS = (
    select(DatasetItem.dataset_id, func.count(DatasetItem.id).label("item_count"))
    .group_by(DatasetItem.dataset_id)
    .subquery()
)

#: The single most recent run per experiment (Postgres `DISTINCT ON`),
#: outer-joined so an experiment with no runs yet still lists.
_LATEST_RUNS = (
    select(ExperimentRun)
    .distinct(ExperimentRun.experiment_id)
    .order_by(ExperimentRun.experiment_id, ExperimentRun.created_at.desc())
    .subquery()
)
_LatestRun = aliased(ExperimentRun, _LATEST_RUNS)


def _base_query() -> Any:
    return (
        select(Experiment, Dataset, func.coalesce(_ITEM_COUNTS.c.item_count, 0), _LatestRun)
        .join(Dataset, Dataset.id == Experiment.dataset_id)
        .outerjoin(_ITEM_COUNTS, _ITEM_COUNTS.c.dataset_id == Dataset.id)
        .outerjoin(_LatestRun, _LatestRun.experiment_id == Experiment.id)
    )


async def get_experiment(db: AsyncSession, experiment_id: uuid.UUID) -> Experiment | None:
    return await db.get(Experiment, experiment_id)


async def get_experiment_with_relations(
    db: AsyncSession, experiment_id: uuid.UUID
) -> ExperimentRow | None:
    query = _base_query().where(Experiment.id == experiment_id)
    result = await db.execute(query)
    row = result.first()
    return tuple(row) if row else None  # type: ignore[return-value]


async def list_experiments(
    db: AsyncSession, *, project_id: uuid.UUID | None = None
) -> list[ExperimentRow]:
    query = _base_query().order_by(Experiment.created_at.desc())
    if project_id is not None:
        query = query.where(Experiment.project_id == project_id)
    result = await db.execute(query)
    return [tuple(row) for row in result.all()]  # type: ignore[misc]


async def create_experiment(db: AsyncSession, **fields: Any) -> Experiment:
    experiment = Experiment(**fields)
    db.add(experiment)
    await db.flush()
    await db.refresh(experiment)
    return experiment


async def delete_experiment(db: AsyncSession, experiment: Experiment) -> None:
    await db.delete(experiment)
    await db.flush()


async def count_active_runs(db: AsyncSession, experiment_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(ExperimentRun.id)).where(
            ExperimentRun.experiment_id == experiment_id,
            ExperimentRun.status.in_([ExperimentRunStatus.PENDING, ExperimentRunStatus.RUNNING]),
        )
    )
    return result.scalar_one()
