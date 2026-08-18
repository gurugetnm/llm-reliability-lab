"""Tests for `GET /api/v1/evaluations/{id}/events` (SSE progress
streaming) — same approach as test_run_events_api.py: the real
`EvaluationRunner` isn't exercised here, events are published directly
onto `evaluation_event_bus` to test the SSE plumbing in isolation.
"""

import asyncio
import re
import uuid
from collections.abc import Callable

import pytest
from app.evaluation.events import evaluation_event_bus
from app.models.enums import EvaluationRunStatus, ExperimentRunStatus
from app.models.evaluation import EvaluationRun
from app.models.experiment import ExperimentRun
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


async def _create_pending_evaluation(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> str:
    set_provider(FakeLLMProvider())
    project = await client.post("/api/v1/projects", json={"name": "Eval SSE test"})
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
    created_run = await client.post(f"/api/v1/experiments/{experiment.json()['id']}/runs", json={})
    run_id = created_run.json()["id"]
    run = await db_session.get(ExperimentRun, uuid.UUID(run_id))
    assert run is not None
    run.status = ExperimentRunStatus.COMPLETED
    await db_session.flush()

    created = await client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "name": "SSE eval", "evaluator_type": "exact_match"},
    )
    return created.json()["id"]


async def test_events_for_an_already_completed_evaluation_sends_one_snapshot_and_closes(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    evaluation_id = await _create_pending_evaluation(client, set_provider, db_session)
    evaluation_run = await db_session.get(EvaluationRun, uuid.UUID(evaluation_id))
    assert evaluation_run is not None
    evaluation_run.status = EvaluationRunStatus.COMPLETED
    evaluation_run.successful_items = 1
    await db_session.flush()

    async with client.stream("GET", f"/api/v1/evaluations/{evaluation_id}/events") as response:
        body = await response.aread()

    events = _parse_sse(body.decode())
    assert len(events) == 1
    assert events[0][0] == "evaluation_completed"


async def test_events_streams_live_progress_and_closes_on_completion(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    evaluation_id = await _create_pending_evaluation(client, set_provider, db_session)
    collected: list[tuple[str, str]] = []

    async def _read() -> None:
        async with client.stream("GET", f"/api/v1/evaluations/{evaluation_id}/events") as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    parsed = _parse_sse(block + "\n\n")
                    collected.extend(parsed)
                    if parsed and parsed[0][0] in ("evaluation_completed", "evaluation_cancelled"):
                        return

    reader = asyncio.create_task(_read())
    await asyncio.sleep(0.05)  # let the subscription register

    evaluation_uuid = uuid.UUID(evaluation_id)
    await evaluation_event_bus.publish(
        evaluation_uuid,
        "evaluation_started",
        {"evaluation_run_id": evaluation_id, "total_items": 1},
    )
    await evaluation_event_bus.publish(
        evaluation_uuid,
        "evaluation_item_completed",
        {
            "evaluation_run_id": evaluation_id,
            "evaluation_result_id": str(uuid.uuid4()),
            "status": "succeeded",
            "score": 1.0,
            "passed": True,
        },
    )
    await evaluation_event_bus.publish(
        evaluation_uuid,
        "evaluation_completed",
        {"evaluation_run_id": evaluation_id, "status": "completed", "successful_items": 1},
    )

    await asyncio.wait_for(reader, timeout=5)

    event_names = [name for name, _ in collected]
    assert event_names[0] == "evaluation_progress"  # catch-up snapshot sent on subscribe
    assert "evaluation_started" in event_names
    assert "evaluation_item_completed" in event_names
    assert event_names[-1] == "evaluation_completed"
