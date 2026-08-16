"""Service-level tests for `app.services.dataset_service` — no HTTP
involved, so these exercise the business rules (ownership, PATCH
semantics, delete-in-use protection) directly and fast.
"""

import uuid

import pytest
from app.core.exceptions import NotFoundError, ValidationError
from app.models.experiment import Experiment
from app.models.project import Project
from app.schemas.dataset import DatasetCreate, DatasetItemCreate, DatasetItemUpdate, DatasetUpdate
from app.services import dataset_service
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_project(db_session: AsyncSession) -> Project:
    project = Project(name="Dataset service test project")
    db_session.add(project)
    await db_session.flush()
    return project


async def test_create_dataset_requires_an_existing_project(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await dataset_service.create_dataset(
            db_session, DatasetCreate(project_id=uuid.uuid4(), name="Orphan")
        )


async def test_create_and_get_dataset_round_trips(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)

    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Q&A", description="A test set")
    )

    assert dataset.version == 1
    fetched, count = await dataset_service.get_dataset_with_item_count(db_session, dataset.id)
    assert fetched.id == dataset.id
    assert count == 0


async def test_get_dataset_with_item_count_raises_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await dataset_service.get_dataset_with_item_count(db_session, uuid.uuid4())


async def test_update_dataset_only_changes_provided_fields(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Original", description="Keep me")
    )

    updated = await dataset_service.update_dataset(
        db_session, dataset.id, DatasetUpdate(name="Renamed")
    )

    assert updated.name == "Renamed"
    assert updated.description == "Keep me"


async def test_list_datasets_filters_by_project_and_reports_item_counts(
    db_session: AsyncSession,
) -> None:
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    dataset_a = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project_a.id, name="A")
    )
    await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project_b.id, name="B")
    )
    await dataset_service.create_dataset_item(
        db_session, dataset_a.id, DatasetItemCreate(input="hello")
    )

    rows = await dataset_service.list_datasets(db_session, project_id=project_a.id)

    assert len(rows) == 1
    dataset, count = rows[0]
    assert dataset.id == dataset_a.id
    assert count == 1


async def test_delete_dataset_in_use_by_an_experiment_is_rejected(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="In use")
    )
    db_session.add(
        Experiment(
            project_id=project.id,
            dataset_id=dataset.id,
            name="Baseline",
            user_prompt_template="{{input}}",
            model="qwen2.5:0.5b",
        )
    )
    await db_session.flush()

    with pytest.raises(ValidationError):
        await dataset_service.delete_dataset(db_session, dataset.id)


async def test_delete_dataset_not_in_use_succeeds(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Unused")
    )

    await dataset_service.delete_dataset(db_session, dataset.id)

    with pytest.raises(NotFoundError):
        await dataset_service.get_dataset_or_404(db_session, dataset.id)


# --- dataset items -----------------------------------------------------


async def test_dataset_items_are_positioned_sequentially(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Positions")
    )

    first = await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="one")
    )
    second = await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="two")
    )

    assert first.position == 0
    assert second.position == 1


async def test_create_dataset_item_requires_an_existing_dataset(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await dataset_service.create_dataset_item(
            db_session, uuid.uuid4(), DatasetItemCreate(input="x")
        )


async def test_list_dataset_items_paginates(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Page test")
    )
    for i in range(5):
        await dataset_service.create_dataset_item(
            db_session, dataset.id, DatasetItemCreate(input=f"item-{i}")
        )

    page_one, total = await dataset_service.list_dataset_items(
        db_session, dataset.id, page=1, page_size=2
    )
    page_two, _ = await dataset_service.list_dataset_items(
        db_session, dataset.id, page=2, page_size=2
    )

    assert total == 5
    assert [item.position for item in page_one] == [0, 1]
    assert [item.position for item in page_two] == [2, 3]


async def test_update_dataset_item_can_explicitly_clear_expected_output(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Clear test")
    )
    item = await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="q", expected_output="a")
    )

    updated = await dataset_service.update_dataset_item(
        db_session, dataset.id, item.id, DatasetItemUpdate(expected_output=None)
    )

    assert updated.expected_output is None


async def test_update_dataset_item_leaves_unset_fields_untouched(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Untouched test")
    )
    item = await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="q", expected_output="a")
    )

    updated = await dataset_service.update_dataset_item(
        db_session, dataset.id, item.id, DatasetItemUpdate()
    )

    assert updated.input == "q"
    assert updated.expected_output == "a"


async def test_get_dataset_item_rejects_mismatched_dataset(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset_a = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="A")
    )
    dataset_b = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="B")
    )
    item = await dataset_service.create_dataset_item(
        db_session, dataset_a.id, DatasetItemCreate(input="q")
    )

    with pytest.raises(NotFoundError):
        await dataset_service.get_dataset_item_or_404(db_session, dataset_b.id, item.id)


async def test_delete_dataset_item(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Delete item test")
    )
    item = await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="q")
    )

    await dataset_service.delete_dataset_item(db_session, dataset.id, item.id)

    with pytest.raises(NotFoundError):
        await dataset_service.get_dataset_item_or_404(db_session, dataset.id, item.id)
