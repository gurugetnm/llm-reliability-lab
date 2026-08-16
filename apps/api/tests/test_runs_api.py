"""Route-level tests for the run endpoints
(`/experiments/{id}/runs`, `/runs/{id}`, ...).

Background execution is stubbed out (see `test_run_service.py`'s
docstring for why) — these tests are about request/response shape and
status codes.
"""

import uuid
from collections.abc import Callable

import pytest
from app.services import run_service
from httpx import AsyncClient
from reliability_lab_llm import LLMProvider

from tests.fakes import FakeLLMProvider


@pytest.fixture(autouse=True)
def _no_real_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "_spawn_run", lambda provider, run_id: None)


async def _setup_experiment(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], *, item_count: int = 3
) -> str:
    set_provider(FakeLLMProvider())
    project = await client.post("/api/v1/projects", json={"name": "Runs API test"})
    dataset = await client.post(
        "/api/v1/datasets", json={"project_id": project.json()["id"], "name": "Set"}
    )
    dataset_id = dataset.json()["id"]
    for i in range(item_count):
        await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": f"q{i}"})
    experiment = await client.post(
        "/api/v1/experiments",
        json={
            "project_id": project.json()["id"],
            "dataset_id": dataset_id,
            "name": "Baseline",
            "user_prompt_template": "{{input}}",
            "model": "qwen2.5:0.5b",
        },
    )
    return experiment.json()["id"]


async def test_start_run(client: AsyncClient, set_provider: Callable[[LLMProvider], None]) -> None:
    experiment_id = await _setup_experiment(client, set_provider, item_count=4)

    response = await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_items"] == 4
    assert body["concurrency"] == 3  # default


async def test_start_run_with_explicit_concurrency(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider)

    response = await client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 5}
    )

    assert response.status_code == 201
    assert response.json()["concurrency"] == 5


async def test_start_run_rejects_concurrency_above_the_maximum(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider)

    response = await client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 999}
    )

    assert response.status_code == 422


async def test_start_run_on_an_empty_dataset_is_rejected(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider, item_count=0)

    response = await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})

    assert response.status_code == 422


async def test_start_run_for_missing_experiment_returns_404(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider())
    response = await client.post(f"/api/v1/experiments/{uuid.uuid4()}/runs", json={})
    assert response.status_code == 404


async def test_list_runs_for_an_experiment(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider)
    await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})

    response = await client.get(f"/api/v1/experiments/{experiment_id}/runs")

    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_get_run_detail(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider)
    created = await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    run_id = created.json()["id"]

    response = await client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_run_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/runs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_run_items_is_paginated(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    experiment_id = await _setup_experiment(client, set_provider)
    created = await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    run_id = created.json()["id"]

    response = await client.get(f"/api/v1/runs/{run_id}/items")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0  # no background execution happened in this test
    assert body["page"] == 1


async def test_cancel_run(client: AsyncClient, set_provider: Callable[[LLMProvider], None]) -> None:
    experiment_id = await _setup_experiment(client, set_provider)
    created = await client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    run_id = created.json()["id"]

    response = await client.post(f"/api/v1/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True


async def test_cancel_run_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/runs/{uuid.uuid4()}/cancel")
    assert response.status_code == 404
