"""Test doubles for `LLMProvider`.

Route-level tests use `FakeLLMProvider` instead of exercising Ollama's
actual wire format — that translation is already covered directly
against `OllamaProvider` in `test_llm_provider.py`. Here we only care
that routes call the provider correctly and translate its results/
errors into the right HTTP responses.
"""

from collections.abc import AsyncIterator
from typing import Any

from reliability_lab_llm import (
    GenerationOptions,
    GenerationResult,
    LLMProvider,
    Message,
    ModelInfo,
    ModelSummary,
    StreamChunk,
)
from reliability_lab_llm.types import StructuredGenerationResult


class FakeLLMProvider(LLMProvider):
    name = "fake"

    def __init__(
        self,
        *,
        generate_result: GenerationResult | None = None,
        generate_error: Exception | None = None,
        structured_result: Any = None,
        structured_error: Exception | None = None,
        structured_usage: tuple[int | None, int | None, int | None] = (None, None, None),
        structured_latency_ms: float | None = 12.5,
        stream_chunks: list[StreamChunk] | None = None,
        stream_error: Exception | None = None,
        models: list[ModelSummary] | None = None,
        models_error: Exception | None = None,
    ) -> None:
        self._generate_result = generate_result
        self._generate_error = generate_error
        self._structured_result = structured_result
        self._structured_error = structured_error
        self._structured_usage = structured_usage
        self._structured_latency_ms = structured_latency_ms
        self._stream_chunks = stream_chunks or []
        self._stream_error = stream_error
        self._models = models or []
        self._models_error = models_error

    async def generate(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        if self._generate_error:
            raise self._generate_error
        assert self._generate_result is not None
        return self._generate_result

    async def generate_structured(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        schema: Any,
        options: GenerationOptions | None = None,
    ) -> StructuredGenerationResult[Any]:
        if self._structured_error:
            raise self._structured_error
        prompt_tokens, completion_tokens, total_tokens = self._structured_usage
        return StructuredGenerationResult(
            data=self._structured_result,
            model=model,
            provider=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason="stop",
            latency_ms=self._structured_latency_ms,
        )

    async def stream(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if self._stream_error:
            raise self._stream_error
        for chunk in self._stream_chunks:
            yield chunk

    async def get_model_info(self, model: str) -> ModelInfo:
        raise NotImplementedError

    async def get_models(self) -> list[ModelSummary]:
        if self._models_error:
            raise self._models_error
        return self._models
