"""Service-level tests for `app.services.experiment_service`."""

import uuid

import pytest
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset import Dataset
from app.models.project import Project
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate, GenerationConfig
from app.services import experiment_service
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_project_and_dataset(db_session: AsyncSession) -> tuple[Project, Dataset]:
    project = Project(name="Experiment service test project")
    db_session.add(project)
    await db_session.flush()
    dataset = Dataset(project_id=project.id, name="Q&A")
    db_session.add(dataset)
    await db_session.flush()
    return project, dataset


def _create_data(
    project_id: uuid.UUID, dataset_id: uuid.UUID, **overrides: object
) -> ExperimentCreate:
    defaults = dict(
        project_id=project_id,
        dataset_id=dataset_id,
        name="Baseline",
        user_prompt_template="Explain: {{input}}",
        model="qwen2.5:0.5b",
    )
    defaults.update(overrides)
    return ExperimentCreate(**defaults)  # type: ignore[arg-type]


async def test_create_experiment_requires_an_existing_project(db_session: AsyncSession) -> None:
    _, dataset = await _make_project_and_dataset(db_session)
    with pytest.raises(NotFoundError):
        await experiment_service.create_experiment(
            db_session, _create_data(uuid.uuid4(), dataset.id)
        )


async def test_create_experiment_requires_an_existing_dataset(db_session: AsyncSession) -> None:
    project, _ = await _make_project_and_dataset(db_session)
    with pytest.raises(NotFoundError):
        await experiment_service.create_experiment(
            db_session, _create_data(project.id, uuid.uuid4())
        )


async def test_create_experiment_rejects_a_dataset_from_a_different_project(
    db_session: AsyncSession,
) -> None:
    project, _ = await _make_project_and_dataset(db_session)
    other_project = Project(name="Other project")
    db_session.add(other_project)
    await db_session.flush()
    other_dataset = Dataset(project_id=other_project.id, name="Other dataset")
    db_session.add(other_dataset)
    await db_session.flush()

    with pytest.raises(ValidationError, match="different project"):
        await experiment_service.create_experiment(
            db_session, _create_data(project.id, other_dataset.id)
        )


async def test_create_experiment_rejects_an_invalid_prompt_template(
    db_session: AsyncSession,
) -> None:
    project, dataset = await _make_project_and_dataset(db_session)
    with pytest.raises(ValidationError, match="Unknown variable"):
        await experiment_service.create_experiment(
            db_session,
            _create_data(project.id, dataset.id, user_prompt_template="{{question}}"),
        )


async def test_create_experiment_persists_generation_config(db_session: AsyncSession) -> None:
    project, dataset = await _make_project_and_dataset(db_session)

    experiment = await experiment_service.create_experiment(
        db_session,
        _create_data(project.id, dataset.id, generation_config=GenerationConfig(temperature=0.3)),
    )

    assert experiment.generation_config["temperature"] == 0.3


async def test_get_experiment_or_404_includes_dataset_and_no_run_yet(
    db_session: AsyncSession,
) -> None:
    project, dataset = await _make_project_and_dataset(db_session)
    experiment = await experiment_service.create_experiment(
        db_session, _create_data(project.id, dataset.id)
    )

    row = await experiment_service.get_experiment_or_404(db_session, experiment.id)

    fetched, fetched_dataset, item_count, latest_run = row
    assert fetched.id == experiment.id
    assert fetched_dataset.id == dataset.id
    assert item_count == 0
    assert latest_run is None


async def test_update_experiment_revalidates_the_prompt_template(
    db_session: AsyncSession,
) -> None:
    project, dataset = await _make_project_and_dataset(db_session)
    experiment = await experiment_service.create_experiment(
        db_session, _create_data(project.id, dataset.id)
    )

    with pytest.raises(ValidationError):
        await experiment_service.update_experiment(
            db_session, experiment.id, ExperimentUpdate(user_prompt_template="{{bogus}}")
        )


async def test_update_experiment_changes_only_provided_fields(db_session: AsyncSession) -> None:
    project, dataset = await _make_project_and_dataset(db_session)
    experiment = await experiment_service.create_experiment(
        db_session, _create_data(project.id, dataset.id, description="original")
    )

    updated = await experiment_service.update_experiment(
        db_session, experiment.id, ExperimentUpdate(name="Renamed")
    )

    assert updated.name == "Renamed"
    assert updated.description == "original"


async def test_delete_experiment_with_no_active_runs_succeeds(db_session: AsyncSession) -> None:
    project, dataset = await _make_project_and_dataset(db_session)
    experiment = await experiment_service.create_experiment(
        db_session, _create_data(project.id, dataset.id)
    )

    await experiment_service.delete_experiment(db_session, experiment.id)

    with pytest.raises(NotFoundError):
        await experiment_service.get_experiment_or_404(db_session, experiment.id)
