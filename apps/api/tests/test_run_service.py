"""Service-level tests for `app.services.run_service`.

`_spawn_run` (which schedules the real background `ExperimentRunner`
task against the production session factory) is monkeypatched to a
no-op here — actual run execution is covered end-to-end, against the
test database, in `test_runner.py`. These tests are about the
service's own bookkeeping: validation, counters, and lifecycle rules.
"""

import uuid

import pytest
from app.core.exceptions import NotFoundError, ValidationError
from app.experiments.concurrency import MAX_CONCURRENCY
from app.models.dataset import Dataset, DatasetItem
from app.models.enums import ExperimentRunStatus
from app.models.experiment import Experiment, ExperimentRun
from app.models.project import Project
from app.services import run_service
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fakes import FakeLLMProvider


@pytest.fixture(autouse=True)
def _no_real_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_service, "_spawn_run", lambda provider, run_id: None)


async def _make_experiment(db_session: AsyncSession, *, item_count: int = 3) -> Experiment:
    project = Project(name="Run service test project")
    db_session.add(project)
    await db_session.flush()
    dataset = Dataset(project_id=project.id, name="Run service test dataset")
    db_session.add(dataset)
    await db_session.flush()
    for i in range(item_count):
        db_session.add(DatasetItem(dataset_id=dataset.id, input=f"q{i}", position=i))
    await db_session.flush()
    experiment = Experiment(
        project_id=project.id,
        dataset_id=dataset.id,
        name="Baseline",
        user_prompt_template="{{input}}",
        model="qwen2.5:0.5b",
    )
    db_session.add(experiment)
    await db_session.flush()
    return experiment


async def test_start_run_creates_a_pending_run_snapshotting_the_experiment(
    db_session: AsyncSession,
) -> None:
    experiment = await _make_experiment(db_session, item_count=5)

    run = await run_service.start_run(
        db_session, experiment.id, provider=FakeLLMProvider(), concurrency=2
    )

    assert run.status == ExperimentRunStatus.PENDING
    assert run.total_items == 5
    assert run.completed_items == 0
    assert run.concurrency == 2
    assert run.model == experiment.model


async def test_start_run_clamps_concurrency_to_the_maximum(db_session: AsyncSession) -> None:
    experiment = await _make_experiment(db_session)

    run = await run_service.start_run(
        db_session, experiment.id, provider=FakeLLMProvider(), concurrency=999
    )

    assert run.concurrency == MAX_CONCURRENCY


async def test_start_run_rejects_an_empty_dataset(db_session: AsyncSession) -> None:
    experiment = await _make_experiment(db_session, item_count=0)

    with pytest.raises(ValidationError, match="no items"):
        await run_service.start_run(
            db_session, experiment.id, provider=FakeLLMProvider(), concurrency=None
        )


async def test_start_run_requires_an_existing_experiment(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await run_service.start_run(
            db_session, uuid.uuid4(), provider=FakeLLMProvider(), concurrency=None
        )


async def test_list_runs_paginates_newest_first(db_session: AsyncSession) -> None:
    experiment = await _make_experiment(db_session)
    for _ in range(3):
        await run_service.start_run(
            db_session, experiment.id, provider=FakeLLMProvider(), concurrency=1
        )

    page_one, total = await run_service.list_runs(db_session, experiment.id, page=1, page_size=2)

    assert total == 3
    assert len(page_one) == 2


async def test_cancel_run_sets_cancel_requested_on_a_pending_run(
    db_session: AsyncSession,
) -> None:
    experiment = await _make_experiment(db_session)
    run = await run_service.start_run(
        db_session, experiment.id, provider=FakeLLMProvider(), concurrency=1
    )

    cancelled = await run_service.cancel_run(db_session, run.id)

    assert cancelled.cancel_requested is True


async def test_cancel_run_rejects_an_already_terminal_run(db_session: AsyncSession) -> None:
    experiment = await _make_experiment(db_session)
    run = await run_service.start_run(
        db_session, experiment.id, provider=FakeLLMProvider(), concurrency=1
    )
    # Simulate the run having already finished.
    fetched = await db_session.get(ExperimentRun, run.id)
    assert fetched is not None
    fetched.status = ExperimentRunStatus.COMPLETED
    await db_session.flush()

    with pytest.raises(ValidationError, match="already"):
        await run_service.cancel_run(db_session, run.id)


async def test_get_run_or_404_raises_for_a_missing_run(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await run_service.get_run_or_404(db_session, uuid.uuid4())
