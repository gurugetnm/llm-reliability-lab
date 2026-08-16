"""`/api/v1/experiments` — experiment configuration management.

Run-related endpoints (`/experiments/{id}/runs`, `/runs/{id}`, ...) live
in `app/api/routes/runs.py` — this file is scoped to the experiment
*configuration* resource itself.
"""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.repositories.experiment_repository import ExperimentRow
from app.schemas.experiment import (
    DatasetSummary,
    ExperimentCreate,
    ExperimentRead,
    ExperimentUpdate,
    RunSummary,
)
from app.services import experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _experiment_read(row: ExperimentRow) -> ExperimentRead:
    experiment, dataset, item_count, latest_run = row
    return ExperimentRead(
        id=experiment.id,
        project_id=experiment.project_id,
        name=experiment.name,
        description=experiment.description,
        dataset=DatasetSummary(id=dataset.id, name=dataset.name, item_count=item_count),
        system_prompt=experiment.system_prompt,
        user_prompt_template=experiment.user_prompt_template,
        model=experiment.model,
        generation_config=experiment.generation_config,
        structured_output_config=(
            {"schema": experiment.structured_output_config["schema"]}
            if experiment.structured_output_config
            else None
        ),
        latest_run=RunSummary.model_validate(latest_run) if latest_run else None,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


@router.post("", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
async def create_experiment(data: ExperimentCreate, db: DbSession) -> ExperimentRead:
    experiment = await experiment_service.create_experiment(db, data)
    row = await experiment_service.get_experiment_or_404(db, experiment.id)
    return _experiment_read(row)


@router.get("", response_model=list[ExperimentRead])
async def list_experiments(
    db: DbSession, project_id: uuid.UUID | None = Query(default=None)
) -> list[ExperimentRead]:
    rows = await experiment_service.list_experiments(db, project_id=project_id)
    return [_experiment_read(row) for row in rows]


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(experiment_id: uuid.UUID, db: DbSession) -> ExperimentRead:
    row = await experiment_service.get_experiment_or_404(db, experiment_id)
    return _experiment_read(row)


@router.patch("/{experiment_id}", response_model=ExperimentRead)
async def update_experiment(
    experiment_id: uuid.UUID, data: ExperimentUpdate, db: DbSession
) -> ExperimentRead:
    await experiment_service.update_experiment(db, experiment_id, data)
    row = await experiment_service.get_experiment_or_404(db, experiment_id)
    return _experiment_read(row)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(experiment_id: uuid.UUID, db: DbSession) -> None:
    await experiment_service.delete_experiment(db, experiment_id)
