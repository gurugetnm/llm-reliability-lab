from httpx import AsyncClient


async def test_health_reports_service_info(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]
    assert body["environment"]
    assert body["database"]["status"] == "ok"
    assert body["llm_provider"]["provider"] == "ollama"
    assert "base_url" in body["llm_provider"]
    assert "default_model" in body["llm_provider"]
