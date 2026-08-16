"""Request/response schemas for `/api/v1/generate` and `/generate/stream`.

Deliberately not the same shape as Ollama's request/response format —
`app/services/generation_service.py` translates between this API schema
and the provider-agnostic `reliability_lab_llm` types, so a future
provider (or a change to Ollama's API) never has to change this schema.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import jsonschema
from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.validators import validate_model_name


class GenerateMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=50_000)


class GenerateRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    messages: list[GenerateMessage] = Field(min_length=1, max_length=50)

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=32_768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: list[str] | None = Field(default=None, max_length=10)
    seed: int | None = None

    response_schema: dict[str, Any] | None = Field(
        default=None,
        description="A JSON Schema object. When present, the model is asked to "
        "return JSON conforming to it, and the response is validated against it.",
    )

    @field_validator("model")
    @classmethod
    def _validate_model_name(cls, value: str) -> str:
        return validate_model_name(value)

    @field_validator("response_schema")
    @classmethod
    def _validate_json_schema(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        try:
            jsonschema.Draft202012Validator.check_schema(value)
        except jsonschema.SchemaError as exc:
            raise ValueError(f"Not a valid JSON Schema: {exc.message}") from exc
        return value

    @model_validator(mode="after")
    def _require_a_user_message(self) -> "GenerateRequest":
        if not any(m.role == "user" and m.content.strip() for m in self.messages):
            raise ValueError("At least one non-empty 'user' message is required")
        return self


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GenerationParameters(BaseModel):
    """Echoes back the parameters actually used, for the execution record."""

    temperature: float
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    seed: int | None = None


class ExecutionResult(BaseModel):
    """The result of one generation — the basis of the future trace record.

    Not persisted yet (that's Phase 3's experiment/run schema); this is
    what the Playground renders and what a caller would attach a score
    to in Phase 4.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    model: str
    provider: str
    response: str
    structured_output: dict[str, Any] | None = None
    finish_reason: str | None = None
    latency_ms: float
    usage: TokenUsage
    parameters: GenerationParameters
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
