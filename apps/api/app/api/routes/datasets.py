"""`/api/v1/datasets` — dataset and dataset item management.

Routes stay thin: translate HTTP <-> schemas and delegate everything
else to `app.services.dataset_service`.
"""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.models.dataset import Dataset
from app.schemas.dataset import (
    DatasetCreate,
    DatasetItemCreate,
    DatasetItemRead,
    DatasetItemUpdate,
    DatasetRead,
    DatasetUpdate,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, PageParam, PageSizeParam
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _dataset_read(dataset: Dataset, item_count: int) -> DatasetRead:
    return DatasetRead(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        version=dataset.version,
        item_count=item_count,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(data: DatasetCreate, db: DbSession) -> DatasetRead:
    dataset = await dataset_service.create_dataset(db, data)
    return _dataset_read(dataset, 0)


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    db: DbSession, project_id: uuid.UUID | None = Query(default=None)
) -> list[DatasetRead]:
    rows = await dataset_service.list_datasets(db, project_id=project_id)
    return [_dataset_read(dataset, count) for dataset, count in rows]


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: uuid.UUID, db: DbSession) -> DatasetRead:
    dataset, count = await dataset_service.get_dataset_with_item_count(db, dataset_id)
    return _dataset_read(dataset, count)


@router.patch("/{dataset_id}", response_model=DatasetRead)
async def update_dataset(dataset_id: uuid.UUID, data: DatasetUpdate, db: DbSession) -> DatasetRead:
    await dataset_service.update_dataset(db, dataset_id, data)
    dataset, count = await dataset_service.get_dataset_with_item_count(db, dataset_id)
    return _dataset_read(dataset, count)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: uuid.UUID, db: DbSession) -> None:
    await dataset_service.delete_dataset(db, dataset_id)


# --- dataset items -----------------------------------------------------


@router.post(
    "/{dataset_id}/items", response_model=DatasetItemRead, status_code=status.HTTP_201_CREATED
)
async def create_dataset_item(
    dataset_id: uuid.UUID, data: DatasetItemCreate, db: DbSession
) -> DatasetItemRead:
    item = await dataset_service.create_dataset_item(db, dataset_id, data)
    return DatasetItemRead.model_validate(item)


@router.get("/{dataset_id}/items", response_model=Page[DatasetItemRead])
async def list_dataset_items(
    dataset_id: uuid.UUID,
    db: DbSession,
    page: PageParam = 1,
    page_size: PageSizeParam = DEFAULT_PAGE_SIZE,
) -> Page[DatasetItemRead]:
    items, total = await dataset_service.list_dataset_items(
        db, dataset_id, page=page, page_size=page_size
    )
    return Page(
        items=[DatasetItemRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/{dataset_id}/items/{item_id}", response_model=DatasetItemRead)
async def update_dataset_item(
    dataset_id: uuid.UUID, item_id: uuid.UUID, data: DatasetItemUpdate, db: DbSession
) -> DatasetItemRead:
    item = await dataset_service.update_dataset_item(db, dataset_id, item_id, data)
    return DatasetItemRead.model_validate(item)


@router.delete("/{dataset_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_item(dataset_id: uuid.UUID, item_id: uuid.UUID, db: DbSession) -> None:
    await dataset_service.delete_dataset_item(db, dataset_id, item_id)
