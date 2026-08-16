"""Ollama implementation of :class:`LLMProvider`.

Talks to the Ollama HTTP API (`/api/generate`, `/api/chat`, `/api/show`).
Chat-style prompts (a list of `Message`) use `/api/chat`; plain string
prompts use `/api/generate` — both are normalized to the same
`LLMProvider` interface.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
import jsonschema
from pydantic import BaseModel, ValidationError

from reliability_lab_llm.base import LLMProvider
from reliability_lab_llm.exceptions import (
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    StructuredOutputError,
)
from reliability_lab_llm.types import (
    GenerationOptions,
    GenerationResult,
    Message,
    ModelInfo,
    ModelSummary,
    StreamChunk,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _to_ollama_options(options: GenerationOptions | None) -> dict[str, Any]:
    if options is None:
        return {}
    payload: dict[str, Any] = {"temperature": options.temperature}
    if options.top_p is not None:
        payload["top_p"] = options.top_p
    if options.max_tokens is not None:
        payload["num_predict"] = options.max_tokens
    if options.stop is not None:
        payload["stop"] = options.stop
    if options.seed is not None:
        payload["seed"] = options.seed
    return payload


def _extract_text(data: dict[str, Any]) -> str:
    if "message" in data:
        return data["message"].get("content", "") or ""
    return data.get("response", "") or ""


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local (or remote) Ollama instance."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        *,
        default_model: str | None = None,
        timeout: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _build_request(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None,
        stream: bool,
        schema: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {"model": model, "stream": stream}
        ollama_options = _to_ollama_options(options)
        if ollama_options:
            payload["options"] = ollama_options
        if schema is not None:
            payload["format"] = schema

        if isinstance(prompt, list):
            payload["messages"] = [message.model_dump() for message in prompt]
            return "/api/chat", payload

        payload["prompt"] = prompt
        return "/api/generate", payload

    async def generate(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        path, payload = self._build_request(prompt, model=model, options=options, stream=False)

        started_at = time.perf_counter()
        data = await self._post(path, payload, model=model)
        latency_ms = (time.perf_counter() - started_at) * 1000

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        total_tokens = (
            (prompt_tokens or 0) + (completion_tokens or 0)
            if prompt_tokens is not None or completion_tokens is not None
            else None
        )

        return GenerationResult(
            text=_extract_text(data),
            model=model,
            provider=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason="stop" if data.get("done") else None,
            latency_ms=latency_ms,
            raw=data,
        )

    async def generate_structured(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        schema: type[SchemaT] | dict[str, Any],
        options: GenerationOptions | None = None,
    ) -> SchemaT | dict[str, Any]:
        json_schema = schema if isinstance(schema, dict) else schema.model_json_schema()
        path, payload = self._build_request(
            prompt, model=model, options=options, stream=False, schema=json_schema
        )
        data = await self._post(path, payload, model=model)
        text = _extract_text(data)

        if isinstance(schema, dict):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise StructuredOutputError(
                    f"Model did not return valid JSON: {exc}", raw_text=text
                ) from exc
            try:
                jsonschema.validate(parsed, schema)
            except jsonschema.ValidationError as exc:
                raise StructuredOutputError(
                    f"Output did not match the provided schema: {exc.message}", raw_text=text
                ) from exc
            return parsed

        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"Output did not match schema '{schema.__name__}': {exc}", raw_text=text
            ) from exc

    async def stream(
        self,
        prompt: str | list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        path, payload = self._build_request(prompt, model=model, options=options, stream=True)

        try:
            async with self._client.stream("POST", path, json=payload) as response:
                await self._raise_for_status(response, model=model)
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    done = bool(data.get("done"))
                    prompt_tokens = data.get("prompt_eval_count")
                    completion_tokens = data.get("eval_count")
                    yield StreamChunk(
                        delta=_extract_text(data),
                        done=done,
                        finish_reason="stop" if done else None,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=(
                            (prompt_tokens or 0) + (completion_tokens or 0)
                            if prompt_tokens is not None or completion_tokens is not None
                            else None
                        ),
                    )
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc

    async def get_model_info(self, model: str) -> ModelInfo:
        data = await self._post("/api/show", {"model": model}, model=model)
        details = data.get("details", {})
        model_info = data.get("model_info", {})
        context_length = next(
            (v for k, v in model_info.items() if k.endswith("context_length")),
            None,
        )

        return ModelInfo(
            name=model,
            provider=self.name,
            parameter_size=details.get("parameter_size"),
            quantization=details.get("quantization_level"),
            context_length=context_length,
            raw=data,
        )

    async def get_models(self) -> list[ModelSummary]:
        data = await self._get("/api/tags")
        summaries = []
        for entry in data.get("models", []):
            details = entry.get("details", {})
            summaries.append(
                ModelSummary(
                    name=entry.get("name") or entry.get("model"),
                    provider=self.name,
                    size_bytes=entry.get("size"),
                    modified_at=entry.get("modified_at"),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    family=details.get("family"),
                    # Ollama's /api/tags doesn't report capabilities — a
                    # per-model /api/show call would, but that's an N+1
                    # request pattern this list endpoint deliberately avoids.
                    capabilities=None,
                )
            )
        return summaries

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            response = await self._client.get(path)
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        await self._raise_for_status(response)
        return response.json()

    async def _post(
        self, path: str, payload: dict[str, Any], *, model: str | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        await self._raise_for_status(response, model=model)
        return response.json()

    async def _raise_for_status(
        self, response: httpx.Response, *, model: str | None = None
    ) -> None:
        if response.status_code == 404 and model is not None:
            raise ModelNotFoundError(model=model, provider=self.name)
        if response.status_code >= 400:
            await response.aread()
            raise ProviderError(
                f"Ollama request to {response.request.url.path} failed "
                f"({response.status_code}): {response.text}"
            )
