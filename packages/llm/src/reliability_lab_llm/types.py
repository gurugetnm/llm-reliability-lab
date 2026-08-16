"""Shared data types for the LLM provider abstraction.

These types are provider-agnostic by design: an `OllamaProvider` and a
future `OpenAIProvider` both speak this vocabulary, so callers never need
to know which provider they're talking to.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    """A single turn in a conversation, used for chat-style generation."""

    role: Role
    content: str


class GenerationOptions(BaseModel):
    """Sampling and length controls, shared across providers.

    Providers that don't support a given option should ignore it rather
    than error, so the same options object can be reused across providers.
    """

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stop: list[str] | None = None
    seed: int | None = None


class GenerationResult(BaseModel):
    """The outcome of a single (non-streaming) generation call."""

    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    latency_ms: float | None = None
    raw: dict[str, Any] | None = Field(
        default=None,
        description="The provider's raw response, kept for debugging and future tracing.",
    )


class StreamChunk(BaseModel):
    """A single chunk emitted while streaming a generation.

    Token counts are only known once generation finishes, so they're
    only populated on the final chunk (`done=True`) — providers that
    report usage mid-stream are free to populate them earlier too.
    """

    delta: str
    done: bool = False
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ModelInfo(BaseModel):
    """Metadata about a specific model, as reported by its provider."""

    name: str
    provider: str
    parameter_size: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    raw: dict[str, Any] | None = None


class ModelSummary(BaseModel):
    """One entry in a provider's list of currently available models.

    Deliberately lighter than `ModelInfo` — it's built from whatever a
    provider's "list models" call returns cheaply (e.g. Ollama's
    `/api/tags`), without a per-model deep lookup. Fields a provider
    can't report are `None` rather than guessed.
    """

    name: str
    provider: str
    size_bytes: int | None = None
    modified_at: datetime | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None
    capabilities: list[str] | None = Field(
        default=None,
        description="Detected capabilities (e.g. 'tools', 'vision'), when cheaply available.",
    )
