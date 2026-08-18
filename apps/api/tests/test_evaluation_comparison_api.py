"""Route-level tests for `GET /api/v1/evaluations/compare` — pairing two
EvaluationRuns' results and running regression detection over them.

Results are inserted directly (bypassing the runner, like the other
route-level tests) so each test controls baseline/candidate scores
precisely.
"""

import uuid
from collections.abc import Callable

import pytest
from app.models.enums import EvaluationResultStatus, EvaluationRunStatus, ExperimentRunStatus
from app.models.evaluation import EvaluationResult, EvaluationRun
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


async def _make_completed_evaluation(
    client: AsyncClient,
    set_provider: Callable[[LLMProvider], None],
    db_session: AsyncSession,
    *,
    scores: list[float],
    evaluator_type: str = "exact_match",
    dataset_id: str | None = None,
    item_ids: list[str] | None = None,
    project_id: str | None = None,
) -> tuple[str, list[str], str, str]:
    """Creates a completed ExperimentRun with len(scores) RunItems, a
    completed EvaluationRun, and one EvaluationResult per item with the
    given score. Returns (evaluation_run_id, dataset_item_ids, dataset_id, project_id).

    Regression detection and per-item comparison both hinge on baseline
    and candidate sharing the *same* dataset (the same question set,
    scored by two different models/prompts) — pass `dataset_id`/
    `item_ids` from a first call to make a second call share it, exactly
    like a real baseline-vs-candidate comparison would.
    """
    set_provider(FakeLLMProvider())
    if dataset_id is None:
        project = await client.post("/api/v1/projects", json={"name": "Comparison API test"})
        project_id = project.json()["id"]
        dataset = await client.post(
            "/api/v1/datasets", json={"project_id": project_id, "name": "Set"}
        )
        dataset_id = dataset.json()["id"]
        item_ids = []
        for i in range(len(scores)):
            item = await client.post(
                f"/api/v1/datasets/{dataset_id}/items",
                json={"input": f"q{i}", "expected_output": f"a{i}"},
            )
            item_ids.append(item.json()["id"])
    assert item_ids is not None and project_id is not None
    experiment = await client.post(
        "/api/v1/experiments",
        json={
            "project_id": project_id,
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

    evaluation_run = EvaluationRun(
        run_id=run.id,
        name="Comparison eval",
        status=EvaluationRunStatus.COMPLETED,
        evaluator_type=evaluator_type,
        evaluator_version="v1",
        total_items=len(scores),
        completed_items=len(scores),
        successful_items=len(scores),
    )
    db_session.add(evaluation_run)
    await db_session.flush()

    for i, (item_id, score) in enumerate(zip(item_ids, scores, strict=True)):
        run_item = RunItem(
            run_id=run.id,
            dataset_item_id=uuid.UUID(item_id),
            model="qwen2.5:0.5b",
            user_prompt=f"q{i}",
            response=f"a{i}",
            generation_config={},
        )
        db_session.add(run_item)
        await db_session.flush()
        db_session.add(
            EvaluationResult(
                evaluation_run_id=evaluation_run.id,
                run_item_id=run_item.id,
                status=EvaluationResultStatus.SUCCEEDED,
                metric_name=evaluator_type,
                score=score,
                passed=score >= 0.5,
                evaluator=f"{evaluator_type}:v1",
            )
        )
    await db_session.flush()
    return str(evaluation_run.id), item_ids, dataset_id, project_id


async def test_compare_detects_a_regression(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    baseline_id, item_ids, dataset_id, project_id = await _make_completed_evaluation(
        client, set_provider, db_session, scores=[0.9, 0.92, 0.91]
    )
    candidate_id, _, _, _ = await _make_completed_evaluation(
        client,
        set_provider,
        db_session,
        scores=[0.8, 0.82, 0.81],
        dataset_id=dataset_id,
        item_ids=item_ids,
        project_id=project_id,
    )

    response = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["regression"]["regression_detected"] is True
    assert body["regression"]["baseline_score"] == pytest.approx(0.91, abs=0.01)
    assert body["regression"]["candidate_score"] == pytest.approx(0.81, abs=0.01)
    assert len(body["items"]) == 3


async def test_compare_no_regression_when_scores_improve(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    baseline_id, item_ids, dataset_id, project_id = await _make_completed_evaluation(
        client, set_provider, db_session, scores=[0.5]
    )
    candidate_id, _, _, _ = await _make_completed_evaluation(
        client,
        set_provider,
        db_session,
        scores=[0.9],
        dataset_id=dataset_id,
        item_ids=item_ids,
        project_id=project_id,
    )

    response = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
    )

    assert response.status_code == 200
    assert response.json()["regression"]["regression_detected"] is False


async def test_compare_respects_custom_threshold(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    baseline_id, item_ids, dataset_id, project_id = await _make_completed_evaluation(
        client, set_provider, db_session, scores=[0.90]
    )
    candidate_id, _, _, _ = await _make_completed_evaluation(
        client,
        set_provider,
        db_session,
        scores=[0.83],
        dataset_id=dataset_id,
        item_ids=item_ids,
        project_id=project_id,
    )

    default = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
    )
    assert default.json()["regression"]["regression_detected"] is True  # -0.07 vs default 0.05

    loose = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
        "&regression_threshold=0.1"
    )
    assert loose.json()["regression"]["regression_detected"] is False


async def test_compare_rejects_different_evaluator_types(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    baseline_id, item_ids, dataset_id, project_id = await _make_completed_evaluation(
        client, set_provider, db_session, scores=[0.9], evaluator_type="exact_match"
    )
    candidate_id, _, _, _ = await _make_completed_evaluation(
        client,
        set_provider,
        db_session,
        scores=[0.8],
        evaluator_type="contains",
        dataset_id=dataset_id,
        item_ids=item_ids,
        project_id=project_id,
    )

    response = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
    )

    assert response.status_code == 422


async def test_compare_returns_404_for_a_missing_evaluation(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={uuid.uuid4()}&candidate_id={uuid.uuid4()}"
    )
    assert response.status_code == 404


async def test_compare_pairs_items_by_dataset_item_id(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    baseline_id, item_ids, dataset_id, project_id = await _make_completed_evaluation(
        client, set_provider, db_session, scores=[0.6, 0.9]
    )
    candidate_id, _, _, _ = await _make_completed_evaluation(
        client,
        set_provider,
        db_session,
        scores=[0.95, 0.5],
        dataset_id=dataset_id,
        item_ids=item_ids,
        project_id=project_id,
    )

    response = await client.get(
        f"/api/v1/evaluations/compare?baseline_id={baseline_id}&candidate_id={candidate_id}"
    )

    body = response.json()
    items_by_index = {item["dataset_item_id"]: item for item in body["items"]}
    first = items_by_index[item_ids[0]]
    assert first["baseline_score"] == pytest.approx(0.6)
    assert first["candidate_score"] == pytest.approx(0.95)
    assert first["difference"] == pytest.approx(0.35)
