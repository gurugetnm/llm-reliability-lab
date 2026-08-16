"""Request/response schemas for `/api/v1/experiments`."""

import uuid
from datetime import datetime
from typing import Any

import jsonschema
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ExperimentRunStatus
from app.schemas.validators import validate_model_name


class GenerationConfig(BaseModel):
    """Mirrors `reliability_lab_llm.GenerationOptions` — kept as a
    separate schema (rather than importing that one directly) because
    this is API-facing/persisted config, not a provider call's options."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=32_768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: list[str] | None = Field(default=None, max_length=10)
    seed: int | None = None


class StructuredOutputConfig(BaseModel):
    schema_: dict[str, Any] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("schema_")
    @classmethod
    def _validate_json_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            jsonschema.Draft202012Validator.check_schema(value)
        except jsonschema.SchemaError as exc:
            raise ValueError(f"Not a valid JSON Schema: {exc.message}") from exc
        return value


class ExperimentCreate(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    system_prompt: str | None = Field(default=None, max_length=20_000)
    user_prompt_template: str = Field(min_length=1, max_length=20_000)
    model: str = Field(min_length=1, max_length=200)
    generation_config: GenerationConfig = Field(default_factory=GenerationConfig)
    structured_output_config: StructuredOutputConfig | None = None

    @field_validator("model")
    @classmethod
    def _validate_model_name(cls, value: str) -> str:
        return validate_model_name(value)


class ExperimentUpdate(BaseModel):
    """PATCH semantics — everything optional. `project_id`/`dataset_id`
    are deliberately not updatable: swapping the dataset out from under
    an experiment would make its run history no longer reproducible."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    system_prompt: str | None = Field(default=None, max_length=20_000)
    user_prompt_template: str | None = Field(default=None, min_length=1, max_length=20_000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    generation_config: GenerationConfig | None = None
    structured_output_config: StructuredOutputConfig | None = None

    @field_validator("model")
    @classmethod
    def _validate_model_name(cls, value: str | None) -> str | None:
        return validate_model_name(value) if value is not None else None


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    item_count: int


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ExperimentRunStatus
    total_items: int
    completed_items: int
    successful_items: int
    failed_items: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ExperimentRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    dataset: DatasetSummary
    system_prompt: str | None
    user_prompt_template: str
    model: str
    generation_config: GenerationConfig
    structured_output_config: StructuredOutputConfig | None
    latest_run: RunSummary | None
    created_at: datetime
    updated_at: datetime
