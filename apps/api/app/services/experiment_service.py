"""Business logic for experiments: project/dataset ownership checks,
prompt template validation, and safe-delete rules. Routes stay thin —
see `app/repositories/experiment_repository.py` for the rule-free query
layer this builds on.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.experiments.prompt_template import PromptTemplateError, validate_template
from app.models.experiment import Experiment
from app.repositories import dataset_repository, experiment_repository
from app.repositories.experiment_repository import ExperimentRow
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services import project_service


async def _validate_prompt_template(template: str) -> None:
    try:
        validate_template(template)
    except PromptTemplateError as exc:
        raise ValidationError(str(exc)) from exc


async def _validate_dataset_belongs_to_project(
    db: AsyncSession, dataset_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    dataset = await dataset_repository.get_dataset(db, dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' was not found")
    if dataset.project_id != project_id:
        raise ValidationError(
            f"Dataset '{dataset_id}' belongs to a different project than this experiment"
        )


async def create_experiment(db: AsyncSession, data: ExperimentCreate) -> Experiment:
    if await project_service.get_project(db, data.project_id) is None:
        raise NotFoundError(f"Project '{data.project_id}' was not found")
    await _validate_dataset_belongs_to_project(db, data.dataset_id, data.project_id)
    await _validate_prompt_template(data.user_prompt_template)

    return await experiment_repository.create_experiment(
        db,
        project_id=data.project_id,
        dataset_id=data.dataset_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        user_prompt_template=data.user_prompt_template,
        model=data.model,
        generation_config=data.generation_config.model_dump(),
        structured_output_config=(
            data.structured_output_config.model_dump(by_alias=True)
            if data.structured_output_config
            else None
        ),
    )


async def get_experiment_or_404(db: AsyncSession, experiment_id: uuid.UUID) -> ExperimentRow:
    row = await experiment_repository.get_experiment_with_relations(db, experiment_id)
    if row is None:
        raise NotFoundError(f"Experiment '{experiment_id}' was not found")
    return row


async def list_experiments(
    db: AsyncSession, *, project_id: uuid.UUID | None = None
) -> list[ExperimentRow]:
    return await experiment_repository.list_experiments(db, project_id=project_id)


async def update_experiment(
    db: AsyncSession, experiment_id: uuid.UUID, data: ExperimentUpdate
) -> Experiment:
    experiment, _, _, _ = await get_experiment_or_404(db, experiment_id)

    fields = data.model_fields_set
    if "name" in fields and data.name is not None:
        experiment.name = data.name
    if "description" in fields:
        experiment.description = data.description
    if "system_prompt" in fields:
        experiment.system_prompt = data.system_prompt
    if "user_prompt_template" in fields and data.user_prompt_template is not None:
        await _validate_prompt_template(data.user_prompt_template)
        experiment.user_prompt_template = data.user_prompt_template
    if "model" in fields and data.model is not None:
        experiment.model = data.model
    if "generation_config" in fields and data.generation_config is not None:
        experiment.generation_config = data.generation_config.model_dump()
    if "structured_output_config" in fields:
        experiment.structured_output_config = (
            data.structured_output_config.model_dump(by_alias=True)
            if data.structured_output_config
            else None
        )

    await db.flush()
    await db.refresh(experiment)
    return experiment


async def delete_experiment(db: AsyncSession, experiment_id: uuid.UUID) -> None:
    experiment, _, _, _ = await get_experiment_or_404(db, experiment_id)
    active = await experiment_repository.count_active_runs(db, experiment_id)
    if active > 0:
        raise ValidationError(
            f"Experiment '{experiment_id}' has {active} active run(s). "
            "Cancel or wait for them to finish before deleting."
        )
    await experiment_repository.delete_experiment(db, experiment)
