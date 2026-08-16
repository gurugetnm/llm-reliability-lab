"""Experiment run endpoints:

    POST /experiments/{id}/runs      start a run
    GET  /experiments/{id}/runs      list runs for an experiment
    GET  /runs/{id}                  run detail
    GET  /runs/{id}/items            paginated run items
    POST /runs/{id}/cancel           request cancellation

Split into two routers (nested under `/experiments` vs. top-level
`/runs`) because a run outlives the "start" call — once started, it's
addressed by its own id, not through its experiment.
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.llm.dependencies import LLMProviderDep
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
