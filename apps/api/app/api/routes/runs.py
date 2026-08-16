"""Experiment run endpoints:

    POST /experiments/{id}/runs      start a run
    GET  /experiments/{id}/runs      list runs for an experiment
    GET  /runs/{id}                  run detail
    GET  /runs/{id}/items            paginated run items
    POST /runs/{id}/cancel           request cancellation
    GET  /runs/{id}/events           live progress (SSE)

Split into two routers (nested under `/experiments` vs. top-level
`/runs`) because a run outlives the "start" call — once started, it's
addressed by its own id, not through its experiment.
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.core.sse import format_sse_event
from app.experiments.events import run_event_bus
from app.experiments.lifecycle import is_terminal
from app.llm.dependencies import LLMProviderDep
from app.models.experiment import ExperimentRun
from app.schemas.pagination import DEFAULT_PAGE_SIZE, Page, PageParam, PageSizeParam
from app.schemas.run import RunItemRead, RunRead, StartRunRequest
from app.services import run_service

experiment_runs_router = APIRouter(prefix="/experiments", tags=["runs"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])


@experiment_runs_router.post(
    "/{experiment_id}/runs", response_model=RunRead, status_code=status.HTTP_201_CREATED
)
async def start_run(
    experiment_id: uuid.UUID, data: StartRunRequest, db: DbSession, provider: LLMProviderDep
) -> RunRead:
    run = await run_service.start_run(
        db, experiment_id, provider=provider, concurrency=data.concurrency
    )
    return RunRead.model_validate(run)


@experiment_runs_router.get("/{experiment_id}/runs", response_model=Page[RunRead])
async def list_runs(
    experiment_id: uuid.UUID,
    db: DbSession,
    page: PageParam = 1,
    page_size: PageSizeParam = DEFAULT_PAGE_SIZE,
) -> Page[RunRead]:
    runs, total = await run_service.list_runs(db, experiment_id, page=page, page_size=page_size)
    return Page(
        items=[RunRead.model_validate(run) for run in runs],
        page=page,
        page_size=page_size,
        total=total,
    )


@runs_router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: uuid.UUID, db: DbSession) -> RunRead:
    run = await run_service.get_run_or_404(db, run_id)
    return RunRead.model_validate(run)


@runs_router.get("/{run_id}/items", response_model=Page[RunItemRead])
async def list_run_items(
    run_id: uuid.UUID,
    db: DbSession,
    page: PageParam = 1,
    page_size: PageSizeParam = DEFAULT_PAGE_SIZE,
) -> Page[RunItemRead]:
    items, total = await run_service.list_run_items(db, run_id, page=page, page_size=page_size)
    return Page(
        items=[RunItemRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@runs_router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel_run(run_id: uuid.UUID, db: DbSession) -> RunRead:
    run = await run_service.cancel_run(db, run_id)
    return RunRead.model_validate(run)


@runs_router.get("/{run_id}/events")
async def run_events(run_id: uuid.UUID, db: DbSession) -> StreamingResponse:
    run = await run_service.get_run_or_404(db, run_id)

    async def event_source() -> AsyncIterator[str]:
        # Already finished by the time a client subscribes (a slow
        # connection, a page refresh after completion, ...) — send one
        # terminal snapshot and close instead of hanging forever.
        if is_terminal(run.status):
            event = "run_cancelled" if run.status == "cancelled" else "run_completed"
            yield format_sse_event(event, _run_snapshot(run))
            return

        queue = run_event_bus.subscribe(run_id)
        try:
            # Catches a client up immediately on subscribe, rather than
            # leaving it waiting for the *next* change to arrive.
            yield format_sse_event("run_progress", _run_snapshot(run))
            while True:
                item = await queue.get()
                yield format_sse_event(item.event, item.data)
                if item.event in ("run_completed", "run_cancelled"):
                    break
        finally:
            run_event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run_snapshot(run: ExperimentRun) -> dict[str, object]:
    return {
        "run_id": str(run.id),
        "status": run.status,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
        "successful_items": run.successful_items,
        "failed_items": run.failed_items,
    }
