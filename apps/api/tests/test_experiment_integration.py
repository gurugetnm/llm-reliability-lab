"""End-to-end integration test for the full experiment engine, driven
entirely through the HTTP API — Part 32's

    Create Project -> Create Dataset -> Create Dataset Items ->
    Create Experiment -> Start Run -> Generate RunItems -> Complete Run

This deliberately does *not* use the shared `client`/`db_session`
fixtures: those wrap every request in one savepoint-rolled-back
transaction shared across the whole test, which is perfect for
isolating fast unit/route tests but wrong here — `_spawn_run`'s
background task genuinely needs a *separate* real connection to see
data an HTTP request already wrote, exactly as happens in production.
`committing_client` below gives each request its own real,
committing session (bound to the test database), and
`run_service.AsyncSessionLocal` is monkeypatched so the background
`ExperimentRunner` uses that same test database instead of the real
one. Together, this is the one test that proves the full stack — route
-> service -> background task -> runner -> GenerationService -> (fake)
provider -> persisted RunItems — is actually wired together correctly,
not just each layer in isolation.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio
from app.db.session import get_db
from app.main import app
from app.services import run_service
from httpx import ASGITransport, AsyncClient
from reliability_lab_llm import GenerationResult, LLMProvider, ProviderConnectionError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import test_engine
from tests.fakes import ScriptedLLMProvider

_TestSessionFactory = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def _committing_test_db() -> AsyncGenerator[AsyncSession]:
    """Mirrors the real (fixed) `get_db`: commits a request's session on
    success, rolls back on exception — but bound to the test database."""
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
def _run_the_real_background_task_against_the_test_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "AsyncSessionLocal", _TestSessionFactory)


def _ok(text: str = "an answer") -> GenerationResult:
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


async def _build_experiment(client: AsyncClient, *, item_count: int) -> str:
    project = await client.post("/api/v1/projects", json={"name": "Integration test project"})
    dataset = await client.post(
        "/api/v1/datasets",
        json={"project_id": project.json()["id"], "name": "Integration test dataset"},
    )
    dataset_id = dataset.json()["id"]
    for i in range(item_count):
        response = await client.post(
            f"/api/v1/datasets/{dataset_id}/items", json={"input": f"What is {i}?"}
        )
        assert response.status_code == 201

    experiment = await client.post(
        "/api/v1/experiments",
        json={
            "project_id": project.json()["id"],
            "dataset_id": dataset_id,
            "name": "Integration test experiment",
            "system_prompt": "Be terse.",
            "user_prompt_template": "Answer: {{input}}",
            "model": "qwen2.5:0.5b",
            "generation_config": {"temperature": 0.1},
        },
    )
    assert experiment.status_code == 201
    return experiment.json()["id"]


async def _wait_for_terminal_status(
    client: AsyncClient, run_id: str, *, timeout: float = 5.0
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/v1/runs/{run_id}")
        body = response.json()
        if body["status"] not in ("pending", "running"):
            return body
        await asyncio.sleep(0.02)
    pytest.fail(f"Run {run_id} did not reach a terminal status within {timeout}s")


async def test_full_experiment_lifecycle_end_to_end(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(ScriptedLLMProvider([_ok(f"answer {i}") for i in range(5)]))
    experiment_id = await _build_experiment(committing_client, item_count=5)

    start = await committing_client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    assert start.status_code == 201
    run_id = start.json()["id"]
    assert start.json()["status"] == "pending"

    final_run = await _wait_for_terminal_status(committing_client, run_id)
    assert final_run["status"] == "completed"
    assert final_run["total_items"] == 5
    assert final_run["completed_items"] == 5
    assert final_run["successful_items"] == 5
    assert final_run["failed_items"] == 0
    assert final_run["started_at"] is not None
    assert final_run["completed_at"] is not None

    items_response = await committing_client.get(f"/api/v1/runs/{run_id}/items")
    items = items_response.json()["items"]
    assert len(items) == 5
    for item in items:
        assert item["status"] == "succeeded"
        assert item["response"].startswith("answer")
        assert item["system_prompt"] == "Be terse."
        assert item["user_prompt"].startswith("Answer: What is")
        assert item["total_tokens"] == 6
        assert item["latency_ms"] is not None

    # The experiment now reports this run as its latest.
    experiment = await committing_client.get(f"/api/v1/experiments/{experiment_id}")
    assert experiment.json()["latest_run"]["id"] == run_id
    assert experiment.json()["latest_run"]["status"] == "completed"


async def test_full_experiment_lifecycle_with_partial_failure(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(
        ScriptedLLMProvider(
            [
                _ok("a"),
                ProviderConnectionError("Ollama unreachable"),
                _ok("c"),
                _ok("d"),
                ProviderConnectionError("Ollama unreachable"),
            ]
        )
    )
    experiment_id = await _build_experiment(committing_client, item_count=5)

    start = await committing_client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 1}
    )
    run_id = start.json()["id"]

    final_run = await _wait_for_terminal_status(committing_client, run_id)
    assert final_run["status"] == "completed_with_errors"
    assert final_run["successful_items"] == 3
    assert final_run["failed_items"] == 2

    items = (await committing_client.get(f"/api/v1/runs/{run_id}/items")).json()["items"]
    failed = [item for item in items if item["status"] == "failed"]
    assert len(failed) == 2
    assert all(item["error_type"] == "provider_error" for item in failed)
    assert all(item["error_message"] for item in failed)


async def test_full_experiment_lifecycle_with_cancellation(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(ScriptedLLMProvider([_ok() for _ in range(6)], delay_seconds=0.15))
    experiment_id = await _build_experiment(committing_client, item_count=6)

    start = await committing_client.post(
        f"/api/v1/experiments/{experiment_id}/runs", json={"concurrency": 2}
    )
    run_id = start.json()["id"]

    await asyncio.sleep(0.05)  # let the first batch start
    cancel = await committing_client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["cancel_requested"] is True

    final_run = await _wait_for_terminal_status(committing_client, run_id, timeout=5.0)
    assert final_run["status"] == "cancelled"

    items = (
        await committing_client.get(f"/api/v1/runs/{run_id}/items", params={"page_size": 100})
    ).json()["items"]
    # Every item still gets a record, even the ones cancelled before they started.
    assert len(items) == 6
    assert any(item["status"] == "cancelled" for item in items)


async def test_deleting_a_dataset_item_after_a_run_preserves_the_run_item(
    committing_client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    set_provider(ScriptedLLMProvider([_ok("preserved")]))
    project = await committing_client.post(
        "/api/v1/projects", json={"name": "Preserve test project"}
    )
    dataset = await committing_client.post(
        "/api/v1/datasets", json={"project_id": project.json()["id"], "name": "Preserve set"}
    )
    dataset_id = dataset.json()["id"]
    item = await committing_client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": "q"})
    item_id = item.json()["id"]
    experiment = await committing_client.post(
        "/api/v1/experiments",
        json={
            "project_id": project.json()["id"],
            "dataset_id": dataset_id,
            "name": "Preserve experiment",
            "user_prompt_template": "{{input}}",
            "model": "qwen2.5:0.5b",
        },
    )
    start = await committing_client.post(
        f"/api/v1/experiments/{experiment.json()['id']}/runs", json={}
    )
    run_id = start.json()["id"]
    await _wait_for_terminal_status(committing_client, run_id)

    delete_response = await committing_client.delete(
        f"/api/v1/datasets/{dataset_id}/items/{item_id}"
    )
    assert delete_response.status_code == 204

    items = (await committing_client.get(f"/api/v1/runs/{run_id}/items")).json()["items"]
    assert len(items) == 1
    assert items[0]["dataset_item_id"] is None  # link cleared...
    assert items[0]["response"] == "preserved"  # ...but the record itself remains


async def test_get_db_commits_flushed_changes_so_other_connections_can_see_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for the request-scoped session bug this file's
    module docstring describes: without `get_db` committing on success,
    every write the experiment engine makes (most of it uses `flush()`,
    matching the repository-layer convention, not `commit()`) would be
    silently rolled back the moment the request's session closed."""
    import app.db.session as session_module
    from app.models.project import Project

    monkeypatch.setattr(session_module, "AsyncSessionLocal", _TestSessionFactory)

    unique = uuid.uuid4().hex[:8]
    gen = get_db()
    db = await gen.__anext__()
    try:
        project = Project(name=f"get_db commit test {unique}")
        db.add(project)
        await db.flush()  # NOT committed yet — mirrors the repositories' own pattern
        project_id = project.id
    finally:
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()  # drives past `yield` -> triggers the commit

    async with _TestSessionFactory() as other_connection:
        found = await other_connection.get(Project, project_id)
    assert found is not None
