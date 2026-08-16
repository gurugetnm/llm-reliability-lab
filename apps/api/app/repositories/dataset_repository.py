"""Data access for `Dataset` / `DatasetItem`. No business rules here —
see `app/services/dataset_service.py` for validation, ownership checks,
and import parsing.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, DatasetItem
from app.models.experiment import Experiment


async def get_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> Dataset | None:
    return await db.get(Dataset, dataset_id)


async def get_dataset_with_item_count(
    db: AsyncSession, dataset_id: uuid.UUID
) -> tuple[Dataset, int] | None:
    query = (
        select(Dataset, func.count(DatasetItem.id))
        .outerjoin(DatasetItem, DatasetItem.dataset_id == Dataset.id)
        .where(Dataset.id == dataset_id)
        .group_by(Dataset.id)
    )
    result = await db.execute(query)
    row = result.first()
    return (row[0], row[1]) if row else None


async def list_datasets(
    db: AsyncSession, *, project_id: uuid.UUID | None = None
) -> list[tuple[Dataset, int]]:
    """Datasets with their item counts in a single query — avoids an N+1
    `count()` per dataset when listing."""
    query = (
        select(Dataset, func.count(DatasetItem.id))
        .outerjoin(DatasetItem, DatasetItem.dataset_id == Dataset.id)
        .group_by(Dataset.id)
        .order_by(Dataset.created_at.desc())
    )
    if project_id is not None:
        query = query.where(Dataset.project_id == project_id)
    result = await db.execute(query)
    return [(row[0], row[1]) for row in result.all()]


async def create_dataset(
    db: AsyncSession, *, project_id: uuid.UUID, name: str, description: str | None
) -> Dataset:
    dataset = Dataset(project_id=project_id, name=name, description=description)
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return dataset


async def delete_dataset(db: AsyncSession, dataset: Dataset) -> None:
    await db.delete(dataset)
    await db.flush()


async def count_experiments_for_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(Experiment.id)).where(Experiment.dataset_id == dataset_id)
    )
    return result.scalar_one()


# --- dataset items -----------------------------------------------------


async def get_dataset_item(
    db: AsyncSession, dataset_id: uuid.UUID, item_id: uuid.UUID
) -> DatasetItem | None:
    result = await db.execute(
        select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    )
    return result.scalar_one_or_none()


async def list_dataset_items_page(
    db: AsyncSession, dataset_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[DatasetItem], int]:
    total = (
        await db.execute(
            select(func.count(DatasetItem.id)).where(DatasetItem.dataset_id == dataset_id)
        )
    ).scalar_one()
    result = await db.execute(
        select(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id)
        .order_by(DatasetItem.position)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def next_position(db: AsyncSession, dataset_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(DatasetItem.position)).where(DatasetItem.dataset_id == dataset_id)
    )
    current_max = result.scalar_one_or_none()
    return 0 if current_max is None else current_max + 1


async def create_dataset_item(
    db: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    input_: object,
    expected_output: object | None,
    metadata: dict[str, object] | None,
    position: int,
) -> DatasetItem:
    item = DatasetItem(
        dataset_id=dataset_id,
        input=input_,
        expected_output=expected_output,
        item_metadata=metadata,
        position=position,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def bulk_create_dataset_items(
    db: AsyncSession, *, dataset_id: uuid.UUID, rows: list[dict[str, object]]
) -> list[DatasetItem]:
    """Inserts every row in `rows` starting right after the dataset's
    current highest `position` — used by bulk import, where all rows are
    known-valid by the time this is called (see `dataset_service`)."""
    start = await next_position(db, dataset_id)
    items = [
        DatasetItem(
            dataset_id=dataset_id,
            input=row["input"],
            expected_output=row.get("expected_output"),
            item_metadata=row.get("metadata"),
            position=start + offset,
        )
        for offset, row in enumerate(rows)
    ]
    db.add_all(items)
    await db.flush()
    return items


async def update_dataset_item(
    db: AsyncSession,
    item: DatasetItem,
    *,
    input_: object | None,
    input_provided: bool,
    expected_output: object | None,
    expected_output_provided: bool,
    metadata: dict[str, object] | None,
    metadata_provided: bool,
) -> DatasetItem:
    # `_provided` flags distinguish "field omitted from the PATCH" from
    # "field explicitly set to null" — both look like `None` otherwise,
    # and only the latter should actually clear the column.
    if input_provided and input_ is not None:
        item.input = input_
    if expected_output_provided:
        item.expected_output = expected_output
    if metadata_provided:
        item.item_metadata = metadata
    await db.flush()
    await db.refresh(item)
    return item


async def delete_dataset_item(db: AsyncSession, item: DatasetItem) -> None:
    await db.delete(item)
    await db.flush()
