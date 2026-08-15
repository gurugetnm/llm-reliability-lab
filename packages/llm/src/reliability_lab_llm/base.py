"""The `LLMProvider` interface every provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from reliability_lab_llm.types import (
    GenerationOptions,
    GenerationResult,
    Message,
    ModelInfo,
    StreamChunk,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProvider(ABC):
    """Provider-agnostic interface for talking to an LLM backend.

    Application code should depend on this interface, never on a concrete
    provider (`OllamaProvider`, a future `OpenAIProvider`, ...). Each method
    accepts either a plain prompt or a list of chat `Message`s so both
    completion- and chat-style backends fit the same interface.
    """

    #: Short, stable identifier used in results/traces, e.g. "ollama".
    name: str

    @abstractmethod
    async def generate(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        """Generate a single completion for `prompt`."""
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        schema: type[SchemaT],
        options: GenerationOptions | None = None,
    ) -> SchemaT:
        """Generate a completion constrained to (and parsed as) `schema`."""
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion for `prompt` as it is generated."""
        raise NotImplementedError

    @abstractmethod
    async def get_model_info(self, model: str) -> ModelInfo:
        """Return metadata about `model` as reported by this provider."""
        raise NotImplementedError
