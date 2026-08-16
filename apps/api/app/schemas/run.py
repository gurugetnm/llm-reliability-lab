"""Request/response schemas for `/api/v1/experiments/{id}/runs` and
`/api/v1/runs/{id}`.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.experiments.concurrency import DEFAULT_CONCURRENCY, MAX_CONCURRENCY
from app.models.enums import ExperimentRunStatus, RunItemErrorType, RunItemStatus


class StartRunRequest(BaseModel):
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=MAX_CONCURRENCY)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    status: ExperimentRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    total_items: int
    completed_items: int
    successful_items: int
    failed_items: int
    cancel_requested: bool
    model: str
    generation_config: dict[str, Any]
    concurrency: int
    created_at: datetime


class RunItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    dataset_item_id: uuid.UUID | None
    status: RunItemStatus
    model: str
    system_prompt: str | None
    user_prompt: str
    response: str | None
    structured_output: dict[str, Any] | None
    error_type: RunItemErrorType | None
    error_message: str | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    generation_config: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None
