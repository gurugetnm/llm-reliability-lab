"""Tests for `GET /api/v1/runs/{id}/events` (SSE progress streaming).

The real `ExperimentRunner` isn't exercised here (see
`test_run_service.py`'s docstring) — these publish directly onto
`run_event_bus`, exactly as the runner would, to test the SSE plumbing
in isolation: subscribing, the initial catch-up snapshot, forwarding
published events, and closing the stream on a terminal event.
"""

import asyncio
import re
import uuid
from collections.abc import Callable

import pytest
from app.experiments.events import run_event_bus
from app.models.enums import ExperimentRunStatus
from app.models.experiment import ExperimentRun
from app.services import run_service
from httpx import AsyncClient
from reliability_lab_llm import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fakes import FakeLLMProvider


@pytest.fixture(autouse=True)
def _no_real_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "_spawn_run", lambda provider, run_id: None)


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


async def _start_pending_run(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> str:
    set_provider(FakeLLMProvider())
    project = await client.post("/api/v1/projects", json={"name": "SSE test"})
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
    run = await client.post(f"/api/v1/experiments/{experiment.json()['id']}/runs", json={})
    return run.json()["id"]


async def test_events_for_an_already_completed_run_sends_one_snapshot_and_closes(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None], db_session: AsyncSession
) -> None:
    run_id = await _start_pending_run(client, set_provider)
    run = await db_session.get(ExperimentRun, uuid.UUID(run_id))
    assert run is not None
    run.status = ExperimentRunStatus.COMPLETED
    run.successful_items = 1
    await db_session.flush()

    async with client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
        body = await response.aread()

    events = _parse_sse(body.decode())
    assert len(events) == 1
    assert events[0][0] == "run_completed"


async def test_events_streams_live_progress_and_closes_on_completion(
    client: AsyncClient, set_provider: Callable[[LLMProvider], None]
) -> None:
    run_id = await _start_pending_run(client, set_provider)
    collected: list[tuple[str, str]] = []

    async def _read() -> None:
        async with client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    parsed = _parse_sse(block + "\n\n")
                    collected.extend(parsed)
                    if parsed and parsed[0][0] in ("run_completed", "run_cancelled"):
                        return

    reader = asyncio.create_task(_read())
    await asyncio.sleep(0.05)  # let the subscription register

    await run_event_bus.publish(
        uuid.UUID(run_id), "run_started", {"run_id": run_id, "total_items": 1}
    )
    await run_event_bus.publish(
        uuid.UUID(run_id),
        "run_item_completed",
        {"run_id": run_id, "run_item_id": str(uuid.uuid4()), "status": "succeeded"},
    )
    await run_event_bus.publish(
        uuid.UUID(run_id),
        "run_completed",
        {"run_id": run_id, "status": "completed", "successful_items": 1, "failed_items": 0},
    )

    await asyncio.wait_for(reader, timeout=5)

    event_names = [name for name, _ in collected]
    # The first event is always the catch-up snapshot the route sends
    # immediately on subscribe.
    assert event_names[0] == "run_progress"
    assert "run_started" in event_names
    assert "run_item_completed" in event_names
    assert event_names[-1] == "run_completed"


async def test_events_never_exposes_internal_exception_details() -> None:
    """SSE payloads are built entirely from curated snapshot fields —
    there's no code path that could serialize a raw exception into one."""
    from app.api.routes.runs import _run_snapshot

    run = ExperimentRun(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        status=ExperimentRunStatus.RUNNING,
        model="m",
        total_items=1,
        completed_items=0,
        successful_items=0,
        failed_items=0,
    )
    snapshot = _run_snapshot(run)
    assert set(snapshot) == {
        "run_id",
        "status",
        "total_items",
        "completed_items",
        "successful_items",
        "failed_items",
    }
