"""Tests for `/api/v1/generate` and `/api/v1/generate/stream`.

Uses `FakeLLMProvider` (see `tests/fakes.py`) rather than a real/mocked
Ollama — these tests are about the route/schema layer: request
validation, translating provider results into `ExecutionResult`, and
mapping provider errors to the right HTTP responses.
"""

import re
from collections.abc import Callable

from httpx import AsyncClient
from reliability_lab_llm import (
    GenerationResult,
    LLMProvider,
    ModelNotFoundError,
    ProviderConnectionError,
    StreamChunk,
    StructuredOutputError,
)

from tests.fakes import FakeLLMProvider

VALID_REQUEST = {
    "model": "llama3.1",
    "messages": [
        {"role": "system", "content": "You are terse."},
        {"role": "user", "content": "Say hi"},
    ],
    "temperature": 0.2,
}


def _parse_sse(raw: str) -> list[tuple[str, str]]:
    events = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        event_match = re.search(r"^event: (.+)$", block, re.MULTILINE)
        data_match = re.search(r"^data: (.+)$", block, re.MULTILINE)
        if event_match and data_match:
            events.append((event_match.group(1), data_match.group(1)))
    return events


# --- validation ---------------------------------------------------------


async def test_generate_rejects_request_without_a_user_message(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/generate",
        json={"model": "llama3.1", "messages": [{"role": "system", "content": "hi"}]},
    )
    assert response.status_code == 422


async def test_generate_rejects_invalid_model_name(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/generate",
        json={**VALID_REQUEST, "model": "../../etc/passwd"},
    )
    assert response.status_code == 422


async def test_generate_rejects_out_of_range_temperature(client: AsyncClient) -> None:
    response = await client.post("/api/v1/generate", json={**VALID_REQUEST, "temperature": 5})
    assert response.status_code == 422


async def test_generate_rejects_invalid_json_schema(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/generate",
        json={**VALID_REQUEST, "response_schema": {"type": "not-a-real-type"}},
    )
    assert response.status_code == 422


# --- non-streaming generation --------------------------------------------


async def test_generate_returns_execution_result(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(
            generate_result=GenerationResult(
                text="Hi there!",
                model="llama3.1",
                provider="ollama",
                prompt_tokens=10,
                completion_tokens=3,
                total_tokens=13,
                finish_reason="stop",
                latency_ms=42.0,
            )
        )
    )

    response = await client.post("/api/v1/generate", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "Hi there!"
    assert body["usage"]["total_tokens"] == 13
    assert body["parameters"]["temperature"] == 0.2
    assert body["finish_reason"] == "stop"


async def test_generate_returns_404_for_missing_model(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(generate_error=ModelNotFoundError(model="llama3.1", provider="ollama"))
    )

    response = await client.post("/api/v1/generate", json=VALID_REQUEST)

    assert response.status_code == 404


async def test_generate_returns_503_when_ollama_unreachable(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(generate_error=ProviderConnectionError("connection refused")))

    response = await client.post("/api/v1/generate", json=VALID_REQUEST)

    assert response.status_code == 503


# --- structured output ---------------------------------------------------


async def test_generate_structured_returns_validated_data(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(structured_result={"summary": "ok", "sentiment": "positive"}))

    response = await client.post(
        "/api/v1/generate",
        json={
            **VALID_REQUEST,
            "response_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "sentiment": {"type": "string"}},
                "required": ["summary", "sentiment"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["structured_output"] == {"summary": "ok", "sentiment": "positive"}


async def test_generate_structured_preserves_token_usage(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    """Regression test for the Phase 2 bug where structured generation's
    `ExecutionResult` always reported empty usage, even when Ollama
    reported real token counts. Usage must be consistent across normal,
    streaming, and structured generation."""
    set_provider(
        FakeLLMProvider(
            structured_result={"summary": "ok", "sentiment": "positive"},
            structured_usage=(10, 5, 15),
        )
    )

    response = await client.post(
        "/api/v1/generate",
        json={
            **VALID_REQUEST,
            "response_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "sentiment": {"type": "string"}},
                "required": ["summary", "sentiment"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert body["latency_ms"] > 0


async def test_generate_structured_invalid_output_returns_422_with_raw_response(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(
            structured_error=StructuredOutputError(
                "Output did not match the provided schema", raw_text="not valid json"
            )
        )
    )

    response = await client.post(
        "/api/v1/generate",
        json={**VALID_REQUEST, "response_schema": {"type": "object"}},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["raw_response"] == "not valid json"


# --- streaming -------------------------------------------------------------


async def test_generate_stream_emits_chunks_then_done(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(
            stream_chunks=[
                StreamChunk(delta="Hel", done=False),
                StreamChunk(delta="lo", done=False),
                StreamChunk(
                    delta="", done=True, prompt_tokens=5, completion_tokens=2, total_tokens=7
                ),
            ]
        )
    )

    async with client.stream("POST", "/api/v1/generate/stream", json=VALID_REQUEST) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = await response.aread()

    events = _parse_sse(raw.decode())
    kinds = [event for event, _ in events]
    assert kinds == ["chunk", "chunk", "chunk", "done"]
    assert '"delta": "Hel"' in events[0][1]

    import json

    done_payload = json.loads(events[-1][1])
    assert done_payload["response"] == "Hello"
    assert done_payload["usage"]["total_tokens"] == 7


async def test_generate_stream_emits_error_event_for_missing_model(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(stream_error=ModelNotFoundError(model="llama3.1", provider="ollama"))
    )

    async with client.stream("POST", "/api/v1/generate/stream", json=VALID_REQUEST) as response:
        raw = await response.aread()

    events = _parse_sse(raw.decode())
    assert events[0][0] == "error"
    assert "llama3.1" in events[0][1]


async def test_generate_stream_rejects_structured_mode(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/generate/stream",
        json={**VALID_REQUEST, "response_schema": {"type": "object"}},
    )
    assert response.status_code == 422
