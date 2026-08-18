"""End-to-end integration test for the full pipeline, driven entirely
through the HTTP API (Part 43):

    Dataset -> Experiment -> Experiment Run -> Evaluation ->
    Evaluation Results -> Aggregate Metrics

Same reasoning as test_experiment_integration.py: a `committing_client`
(each request gets its own real, committing session against the test
database) plus monkeypatching both `run_service.AsyncSessionLocal` and
`evaluation_service.AsyncSessionLocal` so the background
`ExperimentRunner`/`EvaluationRunner` tasks see the same test database an
HTTP request already wrote to, exactly as happens in production. This is
the one test that proves route -> service -> background task ->
EvaluationRunner -> Evaluator -> persisted EvaluationResult is actually
wired together correctly end-to-end, not just each layer in isolation.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio
from app.db.session import get_db
from app.main import app
from app.services import evaluation_service, run_service
from httpx import ASGITransport, AsyncClient
from reliability_lab_evaluation import EmbeddingProvider
from reliability_lab_llm import GenerationResult, LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import test_engine
from tests.fakes import FakeEmbeddingProvider, ScriptedLLMProvider

_TestSessionFactory = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def _committing_test_db() -> AsyncGenerator[AsyncSession]:
    async with _TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def committing_client() -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_db] = _committing_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _run_the_real_background_tasks_against_the_test_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "AsyncSessionLocal", _TestSessionFactory)
    monkeypatch.setattr(evaluation_service, "AsyncSessionLocal", _TestSessionFactory)


def _ok(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        model="qwen2.5:0.5b",
        provider="scripted",
        prompt_tokens=4,
        completion_tokens=2,
        total_tokens=6,
        finish_reason="stop",
        latency_ms=1.0,
    )


async def _build_experiment_with_answers(
    client: AsyncClient, *, answers: list[str]
) -> tuple[str, list[str]]:
    """Builds Dataset (+N items, each `expected_output` == its answer) ->
    Experiment. Returns (experiment_id, dataset_item_ids)."""
    project = await client.post("/api/v1/projects", json={"name": "Eval integration project"})
    dataset = await client.post(
        "/api/v1/datasets",
        json={"project_id": project.json()["id"], "name": "Eval integration dataset"},
    )
    dataset_id = dataset.json()["id"]
    item_ids = []
    for i, answer in enumerate(answers):
        item = await client.post(
            f"/api/v1/datasets/{dataset_id}/items",
            json={"input": f"question {i}", "expected_output": answer},
        )
        assert item.status_code == 201
        item_ids.append(item.json()["id"])

    experiment = await client.post(
        "/api/v1/experiments",
        json={
            "project_id": project.json()["id"],
            "dataset_id": dataset_id,
            "name": "Eval integration experiment",
            "user_prompt_template": "Answer: {{input}}",
            "model": "qwen2.5:0.5b",
        },
    )
    assert experiment.status_code == 201
    return experiment.json()["id"], item_ids


async def _wait_for(
    poll: Callable[[], "asyncio.Future[dict]"],
    *,
    is_terminal: Callable[[dict], bool],
    timeout: float = 5.0,
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        body = await poll()
        if is_terminal(body):
            return body
        await asyncio.sleep(0.02)
    pytest.fail(f"Condition not met within {timeout}s")


async def _wait_for_run(client: AsyncClient, run_id: str) -> dict:
    async def poll() -> dict:
        response = await client.get(f"/api/v1/runs/{run_id}")
        return response.json()

    return await _wait_for(
        poll, is_terminal=lambda body: body["status"] not in ("pending", "running")
    )


async def _wait_for_evaluation(client: AsyncClient, evaluation_id: str) -> dict:
    async def poll() -> dict:
        response = await client.get(f"/api/v1/evaluations/{evaluation_id}")
        return response.json()

    return await _wait_for(
        poll, is_terminal=lambda body: body["status"] not in ("pending", "running")
    )


async def test_full_pipeline_dataset_to_evaluation_metrics(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    answers = ["Paris", "London", "Berlin"]
    set_provider(ScriptedLLMProvider([_ok(a) for a in answers]))
    experiment_id, item_ids = await _build_experiment_with_answers(
        committing_client, answers=answers
    )

    start = await committing_client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 1}
    )
    run_id = start.json()["id"]
    run = await _wait_for_run(committing_client, run_id)
    assert run["status"] == "completed"

    evaluation = await committing_client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "Exact match", "evaluator_type": "exact_match"},
    )
    assert evaluation.status_code == 201
    evaluation_id = evaluation.json()["id"]

    final_evaluation = await _wait_for_evaluation(committing_client, evaluation_id)
    assert final_evaluation["status"] == "completed"
    assert final_evaluation["total_items"] == 3
    assert final_evaluation["successful_items"] == 3
    assert final_evaluation["failed_items"] == 0

    results = (await committing_client.get(f"/api/v1/evaluations/{evaluation_id}/results")).json()
    assert results["total"] == 3
    assert all(r["score"] == 1.0 and r["passed"] is True for r in results["items"])
    assert {r["evaluator"] for r in results["items"]} == {"exact_match:v1"}

    metrics = (await committing_client.get(f"/api/v1/evaluations/{evaluation_id}/metrics")).json()
    assert metrics["total"] == 3
    assert metrics["evaluated"] == 3
    assert metrics["passed"] == 3
    assert metrics["pass_rate"] == 1.0
    assert metrics["mean_score"] == 1.0
    assert metrics["distribution"][-1]["item_count"] == 3  # everything in the top bucket


async def test_full_pipeline_with_a_wrong_answer_produces_a_partial_score(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(ScriptedLLMProvider([_ok("Paris"), _ok("not-london-at-all")]))
    experiment_id, _ = await _build_experiment_with_answers(
        committing_client, answers=["Paris", "London"]
    )

    start = await committing_client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 1}
    )
    run_id = start.json()["id"]
    await _wait_for_run(committing_client, run_id)

    evaluation = await committing_client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "Exact match", "evaluator_type": "exact_match"},
    )
    evaluation_id = evaluation.json()["id"]
    final_evaluation = await _wait_for_evaluation(committing_client, evaluation_id)
    assert final_evaluation["status"] == "completed"  # a low score is not an evaluator failure

    metrics = (await committing_client.get(f"/api/v1/evaluations/{evaluation_id}/metrics")).json()
    assert metrics["mean_score"] == 0.5
    assert metrics["passed"] == 1
    assert metrics["pass_rate"] == 0.5


async def test_full_pipeline_with_semantic_similarity_evaluator(
    committing_client: AsyncClient,
    set_provider: Callable[[LLMProvider], None],
    set_embedding_provider: Callable[[EmbeddingProvider], None],
) -> None:
    set_provider(ScriptedLLMProvider([_ok("Paris"), _ok("Paris")]))
    set_embedding_provider(FakeEmbeddingProvider())
    experiment_id, _ = await _build_experiment_with_answers(
        committing_client, answers=["Paris", "Paris"]
    )

    start = await committing_client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    run_id = start.json()["id"]
    await _wait_for_run(committing_client, run_id)

    evaluation = await committing_client.post(
        "/api/v1/evaluations",
        json={
            "run_id": run_id,
            "name": "Semantic similarity",
            "evaluator_type": "semantic_similarity",
            "configuration": {"threshold": 0.5},
        },
    )
    evaluation_id = evaluation.json()["id"]
    final_evaluation = await _wait_for_evaluation(committing_client, evaluation_id)
    assert final_evaluation["status"] == "completed"

    metrics = (await committing_client.get(f"/api/v1/evaluations/{evaluation_id}/metrics")).json()
    assert metrics["mean_score"] == pytest.approx(1.0, abs=1e-6)  # identical text -> similarity ~1


async def test_full_pipeline_evaluation_cannot_start_before_run_completes(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(ScriptedLLMProvider([_ok("Paris")], delay_seconds=0.3))
    experiment_id, _ = await _build_experiment_with_answers(committing_client, answers=["Paris"])

    start = await committing_client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    run_id = start.json()["id"]
    # Deliberately not awaiting completion — the run is still "running".

    response = await committing_client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "Too early", "evaluator_type": "exact_match"},
    )
    assert response.status_code == 422

    await _wait_for_run(committing_client, run_id)  # let the run finish before the test ends
