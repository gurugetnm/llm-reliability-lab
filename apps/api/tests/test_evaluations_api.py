"""Route-level tests for the evaluation endpoints
(`/evaluators`, `/evaluations`, `/evaluations/{id}/...`, `/evaluations/compare`).

Background execution is stubbed out (see test_runs_api.py's docstring
for the same pattern) — these tests are about request/response shape,
status codes, and the validation evaluation_service performs before an
EvaluationRun row is ever created. The runner itself is covered by
test_evaluation_runner.py.
"""

import uuid
from collections.abc import Callable

import pytest
from app.models.enums import ExperimentRunStatus, RunItemStatus
from app.models.experiment import ExperimentRun, RunItem
from app.services import evaluation_service, run_service
from httpx import AsyncClient
from reliability_lab_llm import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fakes import FakeLLMProvider


@pytest.fixture(autouse=True)
def _no_real_background_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "_spawn_run", lambda provider, run_id: None)
    monkeypatch.setattr(
        evaluation_service, "_spawn_evaluation", lambda evaluation_run_id, **kwargs: None
    )


async def _setup_completed_run(
    client: AsyncClient,
    set_provider: Callable[[LLMProvider], None],
    db_session: AsyncSession,
    *,
    item_count: int = 3,
    expected_output: bool = True,
) -> str:
    """Creates Project -> Dataset (+N items) -> Experiment -> a
    *completed* ExperimentRun with N succeeded RunItems, and returns the
    run's id. Real generation never runs — RunItems are inserted directly."""
    set_provider(FakeLLMProvider())
    project = await client.post("/api/v1/projects", json={"name": "Evaluations API test"})
    dataset = await client.post(
        "/api/v1/datasets", json={"project_id": project.json()["id"], "name": "Set"}
    )
    dataset_id = dataset.json()["id"]
    item_ids = []
    for i in range(item_count):
        item = await client.post(
            f"/api/v1/datasets/{dataset_id}/items",
            json={"input": f"q{i}", **({"expected_output": f"a{i}"} if expected_output else {})},
        )
        item_ids.append(item.json()["id"])
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
    created = await client.post(f"/api/v1/experiments/{experiment.json()['id']}/runs", json={})
    run_id = created.json()["id"]

    run = await db_session.get(ExperimentRun, uuid.UUID(run_id))
    assert run is not None
    run.status = ExperimentRunStatus.COMPLETED
    run.successful_items = item_count
    for i, item_id in enumerate(item_ids):
        db_session.add(
            RunItem(
                run_id=run.id,
                dataset_item_id=uuid.UUID(item_id),
                model="qwen2.5:0.5b",
                user_prompt=f"q{i}",
                status=RunItemStatus.SUCCEEDED,
                response=f"a{i}" if expected_output else "some response",
                generation_config={},
            )
        )
    await db_session.flush()
    return run_id


async def test_list_evaluators_returns_all_built_ins(client: AsyncClient) -> None:
    response = await client.get("/api/v1/evaluators")
    assert response.status_code == 200
    names = {e["name"] for e in response.json()}
    assert {"exact_match", "contains", "semantic_similarity", "llm_judge"} <= names


async def test_create_evaluation(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)

    response = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "Exact match check", "evaluator_type": "exact_match"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["evaluator_type"] == "exact_match"
    assert body["evaluator_version"] == "v1"
    assert body["run_id"] == run_id


async def test_create_evaluation_rejects_a_still_running_experiment_run(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(FakeLLMProvider())
    project = await client.post("/api/v1/projects", json={"name": "Still running"})
    dataset = await client.post(
        "/api/v1/datasets", json={"project_id": project.json()["id"], "name": "Set"}
    )
    dataset_id = dataset.json()["id"]
    await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": "q"})
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
    created = await client.post(f"/api/v1/experiments/{experiment.json()['id']}/runs", json={})
    run_id = created.json()["id"]  # still "pending" — background execution is stubbed out

    response = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "Too early", "evaluator_type": "exact_match"},
    )

    assert response.status_code == 422


async def test_create_evaluation_for_missing_run_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/evaluations",
        json={"run_id": str(uuid.uuid4()), "name": "x", "evaluator_type": "exact_match"},
    )
    assert response.status_code == 404


async def test_create_evaluation_rejects_unknown_evaluator_type(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)

    response = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "not_a_real_evaluator"},
    )

    assert response.status_code == 422


async def test_create_evaluation_rejects_invalid_configuration(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)

    response = await client.post(
        "/api/v1/evaluations",
        json={
            "run_id": run_id,
            "name": "x",
            "evaluator_type": "contains",
            "configuration": {"required_terms": []},  # min_length=1
        },
    )

    assert response.status_code == 422


async def test_create_evaluation_rejects_concurrency_above_the_maximum(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)

    response = await client.post(
        "/api/v1/evaluations",
        json={
            "run_id": run_id,
            "name": "x",
            "evaluator_type": "exact_match",
            "concurrency": 999,
        },
    )

    assert response.status_code == 422


async def test_list_evaluations_filtered_by_run_id(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)
    await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "First", "evaluator_type": "exact_match"},
    )
    await client.post(
        "/api/v1/evaluations",
        json={
            "run_id": run_id,
            "name": "Second",
            "evaluator_type": "contains",
            "configuration": {"required_terms": ["x"]},
        },
    )

    response = await client.get(f"/api/v1/evaluations?run_id={run_id}")

    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_get_evaluation_detail(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)
    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "exact_match"},
    )
    evaluation_id = created.json()["id"]

    response = await client.get(f"/api/v1/evaluations/{evaluation_id}")

    assert response.status_code == 200
    assert response.json()["id"] == evaluation_id


async def test_get_evaluation_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/evaluations/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_evaluation_results_is_paginated(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)
    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "exact_match"},
    )
    evaluation_id = created.json()["id"]

    response = await client.get(f"/api/v1/evaluations/{evaluation_id}/results")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0  # no background execution happened in this test
    assert body["page"] == 1


async def test_get_evaluation_metrics_on_a_pending_evaluation_reports_empty(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)
    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "exact_match"},
    )
    evaluation_id = created.json()["id"]

    response = await client.get(f"/api/v1/evaluations/{evaluation_id}/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["mean_score"] is None
    assert body["distribution"] is None


async def test_cancel_evaluation(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _setup_completed_run(client, set_provider, db_session)
    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "exact_match"},
    )
    evaluation_id = created.json()["id"]

    response = await client.post(f"/api/v1/evaluations/{evaluation_id}/cancel")

    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True


async def test_cancel_evaluation_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/evaluations/{uuid.uuid4()}/cancel")
    assert response.status_code == 404


async def test_cancel_evaluation_rejects_an_already_terminal_evaluation(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    from app.models.enums import EvaluationRunStatus
    from app.models.evaluation import EvaluationRun

    run_id = await _setup_completed_run(client, set_provider, db_session)
    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "x", "evaluator_type": "exact_match"},
    )
    evaluation_id = created.json()["id"]

    evaluation_run = await db_session.get(EvaluationRun, uuid.UUID(evaluation_id))
    assert evaluation_run is not None
    evaluation_run.status = EvaluationRunStatus.COMPLETED
    await db_session.flush()

    response = await client.post(f"/api/v1/evaluations/{evaluation_id}/cancel")
    assert response.status_code == 422
