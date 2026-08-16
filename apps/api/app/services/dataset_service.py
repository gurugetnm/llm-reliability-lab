"""Business logic for datasets and dataset items.

Routes translate HTTP <-> schemas and delegate everything else here:
existence/ownership checks and version bookkeeping live in this module
rather than in `app/repositories/dataset_repository.py` (which stays a
thin, rule-free data-access layer) or in the routes. Bulk-import parsing
lives here too — see the `# --- bulk import` section below.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset import Dataset, DatasetItem
from app.repositories import dataset_repository as repo
from app.schemas.dataset import DatasetCreate, DatasetItemCreate, DatasetItemUpdate, DatasetUpdate
from app.services import project_service


async def get_dataset_or_404(db: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    dataset = await repo.get_dataset(db, dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' was not found")
    return dataset


async def get_dataset_with_item_count(
    db: AsyncSession, dataset_id: uuid.UUID
) -> tuple[Dataset, int]:
    result = await repo.get_dataset_with_item_count(db, dataset_id)
    if result is None:
        raise NotFoundError(f"Dataset '{dataset_id}' was not found")
    return result


async def list_datasets(
    db: AsyncSession, *, project_id: uuid.UUID | None = None
) -> list[tuple[Dataset, int]]:
    return await repo.list_datasets(db, project_id=project_id)


async def create_dataset(db: AsyncSession, data: DatasetCreate) -> Dataset:
    # Fail fast with a clear 404 rather than letting the FK violation
    # surface as an opaque 500.
    if await project_service.get_project(db, data.project_id) is None:
        raise NotFoundError(f"Project '{data.project_id}' was not found")
    return await repo.create_dataset(
        db, project_id=data.project_id, name=data.name, description=data.description
    )


async def update_dataset(db: AsyncSession, dataset_id: uuid.UUID, data: DatasetUpdate) -> Dataset:
    dataset = await get_dataset_or_404(db, dataset_id)
    if data.name is not None:
        dataset.name = data.name
    if data.description is not None:
        dataset.description = data.description
    await db.flush()
    await db.refresh(dataset)
    return dataset


async def delete_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> None:
    dataset = await get_dataset_or_404(db, dataset_id)
    in_use = await repo.count_experiments_for_dataset(db, dataset_id)
    if in_use > 0:
        raise ValidationError(
            f"Dataset '{dataset_id}' is used by {in_use} experiment(s) and can't be deleted. "
            "Delete those experiments first."
        )
    await repo.delete_dataset(db, dataset)


# --- dataset items -----------------------------------------------------


async def get_dataset_item_or_404(
    db: AsyncSession, dataset_id: uuid.UUID, item_id: uuid.UUID
) -> DatasetItem:
    await get_dataset_or_404(db, dataset_id)
    item = await repo.get_dataset_item(db, dataset_id, item_id)
    if item is None:
        raise NotFoundError(f"Item '{item_id}' was not found in dataset '{dataset_id}'")
    return item


async def list_dataset_items(
    db: AsyncSession, dataset_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[DatasetItem], int]:
    await get_dataset_or_404(db, dataset_id)
    offset = (page - 1) * page_size
    return await repo.list_dataset_items_page(db, dataset_id, offset=offset, limit=page_size)


async def create_dataset_item(
    db: AsyncSession, dataset_id: uuid.UUID, data: DatasetItemCreate
) -> DatasetItem:
    await get_dataset_or_404(db, dataset_id)
    position = await repo.next_position(db, dataset_id)
    return await repo.create_dataset_item(
        db,
        dataset_id=dataset_id,
        input_=data.input,
        expected_output=data.expected_output,
        metadata=data.metadata,
        position=position,
    )


async def update_dataset_item(
    db: AsyncSession, dataset_id: uuid.UUID, item_id: uuid.UUID, data: DatasetItemUpdate
) -> DatasetItem:
    item = await get_dataset_item_or_404(db, dataset_id, item_id)
    fields = data.model_fields_set
    return await repo.update_dataset_item(
        db,
        item,
        input_=data.input,
        input_provided="input" in fields,
        expected_output=data.expected_output,
        expected_output_provided="expected_output" in fields,
        metadata=data.metadata,
        metadata_provided="metadata" in fields,
    )


async def delete_dataset_item(db: AsyncSession, dataset_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = await get_dataset_item_or_404(db, dataset_id, item_id)
    await repo.delete_dataset_item(db, item)
