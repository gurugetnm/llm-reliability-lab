from collections.abc import Callable

from httpx import AsyncClient
from reliability_lab_llm import LLMProvider, ModelSummary, ProviderConnectionError

from tests.fakes import FakeLLMProvider


async def test_list_models_returns_provider_models(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        FakeLLMProvider(
            models=[
                ModelSummary(
                    name="llama3.1",
                    provider="ollama",
                    size_bytes=4_920_000_000,
                    parameter_size="8.0B",
                    quantization="Q4_0",
                )
            ]
        )
    )

    response = await client.get("/api/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "llama3.1"
    assert body[0]["provider"] == "ollama"
    assert body[0]["parameter_size"] == "8.0B"


async def test_list_models_empty(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(models=[]))

    response = await client.get("/api/v1/models")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_models_returns_503_when_ollama_unavailable(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(models_error=ProviderConnectionError("connection refused")))

    response = await client.get("/api/v1/models")

    assert response.status_code == 503
    assert "connection refused" in response.json()["detail"]


async def test_models_health_reports_available(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(models=[ModelSummary(name="llama3.1", provider="ollama")]))

    response = await client.get("/api/v1/models/health")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["model_count"] == 1
    assert body["latency_ms"] is not None


async def test_models_health_reports_unavailable_without_raising(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider(models_error=ProviderConnectionError("connection refused")))

    response = await client.get("/api/v1/models/health")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "connection refused" in body["error"]
