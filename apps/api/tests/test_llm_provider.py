"""Tests for the LLMProvider interface and its Ollama implementation.

Uses `httpx.MockTransport` instead of a live Ollama instance, so these
run without any local model server and stay fast/deterministic.
"""

import json

import httpx
import pytest
from pydantic import BaseModel
from reliability_lab_llm import (
    GenerationOptions,
    LLMProvider,
    ModelNotFoundError,
    OllamaProvider,
    ProviderConnectionError,
    StructuredOutputError,
)
from reliability_lab_llm.types import Message


def test_llm_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_ollama_provider_implements_llm_provider() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "ollama"


async def test_generate_parses_ollama_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = json.loads(request.content)
        assert body["model"] == "llama3.1"
        assert body["prompt"] == "Say hi"
        return httpx.Response(
            200,
            json={
                "model": "llama3.1",
                "response": "hi there",
                "done": True,
                "prompt_eval_count": 5,
                "eval_count": 3,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate(
        "Say hi", model="llama3.1", options=GenerationOptions(temperature=0.1)
    )

    assert result.text == "hi there"
    assert result.provider == "ollama"
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 3
    assert result.total_tokens == 8
    assert result.finish_reason == "stop"
    assert result.latency_ms is not None


async def test_generate_uses_chat_endpoint_for_message_lists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        return httpx.Response(200, json={"message": {"content": "hi!"}, "done": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate([Message(role="user", content="hello")], model="llama3.1")

    assert result.text == "hi!"


class Answer(BaseModel):
    value: int


async def test_generate_structured_validates_against_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "format" in body  # JSON schema was sent to constrain output
        return httpx.Response(200, json={"response": json.dumps({"value": 42}), "done": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate_structured("What is 6*7?", model="llama3.1", schema=Answer)

    assert result.data == Answer(value=42)


async def test_generate_structured_preserves_token_usage_for_pydantic_schema() -> None:
    """Regression test: structured generation used to discard Ollama's
    token counts entirely because `generate_structured` only returned the
    parsed data. Usage must now be consistent with plain `generate()`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": json.dumps({"value": 42}),
                "done": True,
                "prompt_eval_count": 11,
                "eval_count": 4,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate_structured("What is 6*7?", model="llama3.1", schema=Answer)

    assert result.prompt_tokens == 11
    assert result.completion_tokens == 4
    assert result.total_tokens == 15
    assert result.finish_reason == "stop"
    assert result.latency_ms is not None
    assert result.model == "llama3.1"
    assert result.provider == "ollama"


async def test_generate_structured_leaves_missing_usage_as_none_never_invented() -> None:
    """When Ollama doesn't report eval counts, usage must be `None` —
    never a fabricated number."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": json.dumps({"value": 42}), "done": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate_structured("What is 6*7?", model="llama3.1", schema=Answer)

    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None


async def test_stream_yields_chunks_and_final_done_chunk() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            json.dumps({"response": "Hel", "done": False}),
            json.dumps({"response": "lo", "done": False}),
            json.dumps({"response": "", "done": True}),
        ]
        return httpx.Response(200, content="\n".join(lines))

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    chunks = [chunk async for chunk in provider.stream("Hi", model="llama3.1")]

    assert [c.delta for c in chunks] == ["Hel", "lo", ""]
    assert chunks[-1].done is True


async def test_get_model_info_maps_ollama_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/show"
        return httpx.Response(
            200,
            json={
                "details": {"parameter_size": "8.0B", "quantization_level": "Q4_0"},
                "model_info": {"llama.context_length": 8192},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    info = await provider.get_model_info("llama3.1")

    assert info.name == "llama3.1"
    assert info.provider == "ollama"
    assert info.parameter_size == "8.0B"
    assert info.quantization == "Q4_0"
    assert info.context_length == 8192


async def test_model_not_found_raises_typed_error() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(404)), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    with pytest.raises(ModelNotFoundError):
        await provider.get_model_info("does-not-exist")


async def test_connection_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    with pytest.raises(ProviderConnectionError):
        await provider.generate("hi", model="llama3.1")


async def test_get_models_maps_tags_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "llama3.1:8b",
                        "size": 4_920_753_328,
                        "modified_at": "2026-01-05T10:00:00Z",
                        "details": {
                            "parameter_size": "8.0B",
                            "quantization_level": "Q4_0",
                            "family": "llama",
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    models = await provider.get_models()

    assert len(models) == 1
    assert models[0].name == "llama3.1:8b"
    assert models[0].provider == "ollama"
    assert models[0].size_bytes == 4_920_753_328
    assert models[0].parameter_size == "8.0B"
    assert models[0].family == "llama"


async def test_get_models_empty_when_none_installed() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"models": []})),
        base_url="http://ollama.test",
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    assert await provider.get_models() == []


async def test_get_models_raises_connection_error_when_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    with pytest.raises(ProviderConnectionError):
        await provider.get_models()


async def test_generate_structured_accepts_a_raw_json_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["format"] == {"type": "object", "properties": {"value": {"type": "integer"}}}
        return httpx.Response(200, json={"response": json.dumps({"value": 42}), "done": True})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    result = await provider.generate_structured(
        "What is 6*7?",
        model="llama3.1",
        schema={"type": "object", "properties": {"value": {"type": "integer"}}},
    )

    assert result.data == {"value": 42}


async def test_generate_structured_raises_on_non_json_output() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"response": "not json at all", "done": True})
        ),
        base_url="http://ollama.test",
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    with pytest.raises(StructuredOutputError) as exc_info:
        await provider.generate_structured("hi", model="llama3.1", schema={"type": "object"})
    assert exc_info.value.raw_text == "not json at all"


async def test_generate_structured_raises_when_schema_does_not_match() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"response": json.dumps({"wrong": "shape"}), "done": True}
            )
        ),
        base_url="http://ollama.test",
    )
    provider = OllamaProvider(base_url="http://localhost:11434", client=client)

    schema = {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]}
    with pytest.raises(StructuredOutputError):
        await provider.generate_structured("hi", model="llama3.1", schema=schema)
