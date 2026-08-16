"""Request/response schemas for `/api/v1/datasets` — never expose the
SQLAlchemy models directly through the API (see `app/models/dataset.py`).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class DatasetUpdate(BaseModel):
    """All fields optional — PATCH semantics; only what's provided changes."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    version: int
    item_count: int
    created_at: datetime
    updated_at: datetime


# --- dataset items -----------------------------------------------------

#: A dataset item's `input`/`expected_output` are intentionally not
#: constrained beyond "valid JSON" — a string question, a structured RAG
#: context object, or anything else Phase 4's evaluators need.
JsonValue = Any


class DatasetItemCreate(BaseModel):
    input: JsonValue
    expected_output: JsonValue | None = None
    metadata: dict[str, Any] | None = None


class DatasetItemUpdate(BaseModel):
    input: JsonValue | None = None
    expected_output: JsonValue | None = None
    metadata: dict[str, Any] | None = None


class DatasetItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    input: JsonValue
    expected_output: JsonValue | None
    metadata: dict[str, Any] | None = Field(validation_alias="item_metadata")
    position: int
    created_at: datetime
    updated_at: datetime


# --- bulk import ---------------------------------------------------------


class DatasetImportRequest(BaseModel):
    format: Literal["json", "jsonl"]
    content: str = Field(min_length=1, max_length=10_000_000)


class DatasetImportRowError(BaseModel):
    line: int
    message: str


class DatasetImportResponse(BaseModel):
    dataset: DatasetRead
    imported_count: int
