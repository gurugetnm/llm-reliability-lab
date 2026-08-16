"""Route-level tests for `/api/v1/experiments`."""

import uuid

from app.models.enums import ExperimentRunStatus
from app.models.experiment import ExperimentRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _setup(client: AsyncClient) -> tuple[str, str]:
    project = await client.post("/api/v1/projects", json={"name": "Experiment API test"})
    project_id = project.json()["id"]
    dataset = await client.post("/api/v1/datasets", json={"project_id": project_id, "name": "Q&A"})
    return project_id, dataset.json()["id"]


def _payload(project_id: str, dataset_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "name": "Baseline",
        "user_prompt_template": "Explain: {{input}}",
        "model": "qwen2.5:0.5b",
    }
    payload.update(overrides)
    return payload


async def test_create_experiment(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)

    response = await client.post(
        "/api/v1/experiments", json=_payload(project_id, dataset_id, system_prompt="Be terse.")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Baseline"
    assert body["dataset"]["id"] == dataset_id
    assert body["dataset"]["item_count"] == 0
    assert body["latest_run"] is None
    assert body["generation_config"]["temperature"] == 0.7


async def test_create_experiment_rejects_invalid_template(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)

    response = await client.post(
        "/api/v1/experiments",
        json=_payload(project_id, dataset_id, user_prompt_template="{{nope}}"),
    )

    assert response.status_code == 422


async def test_create_experiment_rejects_bad_model_name(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)

    response = await client.post(
        "/api/v1/experiments",
        json=_payload(project_id, dataset_id, model="../../etc/passwd"),
    )

    assert response.status_code == 422


async def test_create_experiment_with_structured_output_config(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)

    response = await client.post(
        "/api/v1/experiments",
        json=_payload(
            project_id,
            dataset_id,
            structured_output_config={
                "schema": {"type": "object", "properties": {"answer": {"type": "string"}}}
            },
        ),
    )

    assert response.status_code == 201
    assert response.json()["structured_output_config"]["schema"]["type"] == "object"


async def test_get_experiment_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/experiments/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_experiments_filters_by_project(client: AsyncClient) -> None:
    project_a, dataset_a = await _setup(client)
    project_b, dataset_b = await _setup(client)
    await client.post("/api/v1/experiments", json=_payload(project_a, dataset_a, name="A"))
    await client.post("/api/v1/experiments", json=_payload(project_b, dataset_b, name="B"))

    response = await client.get("/api/v1/experiments", params={"project_id": project_a})

    assert response.status_code == 200
    names = [e["name"] for e in response.json()]
    assert names == ["A"]


async def test_update_experiment(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)
    created = await client.post("/api/v1/experiments", json=_payload(project_id, dataset_id))
    experiment_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/experiments/{experiment_id}", json={"name": "Updated name"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated name"


async def test_delete_experiment(client: AsyncClient) -> None:
    project_id, dataset_id = await _setup(client)
    created = await client.post("/api/v1/experiments", json=_payload(project_id, dataset_id))
    experiment_id = created.json()["id"]

    response = await client.delete(f"/api/v1/experiments/{experiment_id}")
    assert response.status_code == 204

    follow_up = await client.get(f"/api/v1/experiments/{experiment_id}")
    assert follow_up.status_code == 404


async def test_delete_experiment_with_an_active_run_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project_id, dataset_id = await _setup(client)
    created = await client.post("/api/v1/experiments", json=_payload(project_id, dataset_id))
    experiment_id = created.json()["id"]

    db_session.add(
        ExperimentRun(
            experiment_id=uuid.UUID(experiment_id),
            status=ExperimentRunStatus.RUNNING,
            model="qwen2.5:0.5b",
            total_items=1,
        )
    )
    await db_session.flush()

    response = await client.delete(f"/api/v1/experiments/{experiment_id}")
    assert response.status_code == 422


async def test_experiment_reports_its_latest_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project_id, dataset_id = await _setup(client)
    created = await client.post("/api/v1/experiments", json=_payload(project_id, dataset_id))
    experiment_id = created.json()["id"]

    db_session.add(
        ExperimentRun(
            experiment_id=uuid.UUID(experiment_id),
            status=ExperimentRunStatus.COMPLETED,
            model="qwen2.5:0.5b",
            total_items=5,
            completed_items=5,
            successful_items=5,
        )
    )
    await db_session.flush()

    response = await client.get(f"/api/v1/experiments/{experiment_id}")

    assert response.status_code == 200
    latest_run = response.json()["latest_run"]
    assert latest_run is not None
    assert latest_run["status"] == "completed"
    assert latest_run["successful_items"] == 5
