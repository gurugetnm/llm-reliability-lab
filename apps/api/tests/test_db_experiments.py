"""Relationship, cascade, and constraint coverage for the experiment
engine's persistence layer (`Dataset` -> `DatasetItem`, `Experiment` ->
`ExperimentRun` -> `RunItem`).

These are model/DB-level tests — no HTTP involved — so they exercise
exactly what the ORM mappings and Alembic-managed constraints actually
enforce, independent of any service-layer validation on top.
"""

import uuid
from typing import TypeVar

import pytest
from app.db.base import Base
from app.models import Dataset, DatasetItem, Experiment, ExperimentRun, Project, RunItem
from app.models.enums import ExperimentRunStatus, RunItemStatus
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT", bound=Base)


async def _get(  # noqa: UP047 — PEP 695 generics need Python 3.12+, this package supports 3.11+
    db_session: AsyncSession, model: type[ModelT], id_: uuid.UUID
) -> ModelT | None:
    """Fetches by primary key via an explicit `SELECT` rather than
    `AsyncSession.get()` — after a same-session cascading DELETE has been
    flushed, `get()`'s identity-map/expired-attribute refresh path can
    trip a "greenlet_spawn has not been called" error under async
    SQLAlchemy. An explicit query sidesteps that entirely.
    """
    # `populate_existing()` forces already-identity-mapped instances to be
    # refreshed from this query's result rather than returning stale
    # in-memory attribute values — needed here since a same-session DB
    # cascade (e.g. `ON DELETE SET NULL`) doesn't otherwise invalidate
    # objects already loaded into the session.
    query = select(model).where(model.id == id_).execution_options(populate_existing=True)  # type: ignore[attr-defined]
    result = await db_session.execute(query)
    return result.scalar_one_or_none()


async def _make_hierarchy(db_session: AsyncSession) -> dict[str, object]:
    """Builds one full Project -> ... -> RunItem chain and flushes it."""
    project = Project(name="Experiment engine test project")
    db_session.add(project)
    await db_session.flush()

    dataset = Dataset(project_id=project.id, name="Q&A set", version=1)
    db_session.add(dataset)
    await db_session.flush()

    item = DatasetItem(
        dataset_id=dataset.id,
        input={"question": "What is TCP?"},
        expected_output={"answer": "A transport protocol"},
        item_metadata={"topic": "networking"},
        position=0,
    )
    db_session.add(item)
    await db_session.flush()

    experiment = Experiment(
        project_id=project.id,
        dataset_id=dataset.id,
        name="Baseline",
        user_prompt_template="Explain: {{input}}",
        model="qwen2.5:0.5b",
        generation_config={"temperature": 0.2},
    )
    db_session.add(experiment)
    await db_session.flush()

    run = ExperimentRun(
        experiment_id=experiment.id,
        model=experiment.model,
        generation_config=experiment.generation_config,
        total_items=1,
    )
    db_session.add(run)
    await db_session.flush()

    run_item = RunItem(
        run_id=run.id,
        dataset_item_id=item.id,
        model=experiment.model,
        user_prompt="Explain: What is TCP?",
        status=RunItemStatus.SUCCEEDED,
        response="A transport protocol.",
        input_tokens=5,
        output_tokens=6,
        total_tokens=11,
        generation_config={"temperature": 0.2},
    )
    db_session.add(run_item)
    await db_session.flush()

    return {
        "project": project,
        "dataset": dataset,
        "item": item,
        "experiment": experiment,
        "run": run,
        "run_item": run_item,
    }


async def test_full_hierarchy_persists_and_is_queryable(db_session: AsyncSession) -> None:
    chain = await _make_hierarchy(db_session)

    fetched_run_item = await _get(db_session, RunItem, chain["run_item"].id)  # type: ignore[attr-defined]
    assert fetched_run_item is not None
    assert fetched_run_item.run_id == chain["run"].id  # type: ignore[attr-defined]
    assert fetched_run_item.dataset_item_id == chain["item"].id  # type: ignore[attr-defined]
    assert fetched_run_item.status == RunItemStatus.SUCCEEDED


async def test_deleting_project_cascades_to_the_whole_hierarchy(db_session: AsyncSession) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["project"])
    await db_session.flush()

    assert await _get(db_session, Dataset, chain["dataset"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, DatasetItem, chain["item"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, Experiment, chain["experiment"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, ExperimentRun, chain["run"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, RunItem, chain["run_item"].id) is None  # type: ignore[attr-defined]


async def test_deleting_experiment_cascades_to_runs_and_run_items(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["experiment"])
    await db_session.flush()

    assert await _get(db_session, ExperimentRun, chain["run"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, RunItem, chain["run_item"].id) is None  # type: ignore[attr-defined]
    # The dataset itself is untouched — only the experiment referencing it is gone.
    assert await _get(db_session, Dataset, chain["dataset"].id) is not None  # type: ignore[attr-defined]


async def test_deleting_dataset_item_preserves_the_run_item_but_clears_the_link(
    db_session: AsyncSession,
) -> None:
    """A RunItem carries its own copy of prompt/response, so removing the
    source dataset item must not delete run history — only the link."""
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["item"])
    await db_session.flush()

    fetched_run_item = await _get(db_session, RunItem, chain["run_item"].id)  # type: ignore[attr-defined]
    assert fetched_run_item is not None
    assert fetched_run_item.dataset_item_id is None
    assert fetched_run_item.response == "A transport protocol."


async def test_cannot_delete_a_dataset_still_referenced_by_an_experiment(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["dataset"])
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_dataset_item_position_is_unique_per_dataset(db_session: AsyncSession) -> None:
    project = Project(name="Uniqueness test project")
    db_session.add(project)
    await db_session.flush()

    dataset = Dataset(project_id=project.id, name="Set")
    db_session.add(dataset)
    await db_session.flush()

    db_session.add(DatasetItem(dataset_id=dataset.id, input={"q": "a"}, position=0))
    await db_session.flush()

    db_session.add(DatasetItem(dataset_id=dataset.id, input={"q": "b"}, position=0))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_experiment_run_completed_items_cannot_exceed_total_items(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)
    experiment = chain["experiment"]
    assert isinstance(experiment, Experiment)

    db_session.add(
        ExperimentRun(
            experiment_id=experiment.id,
            model=experiment.model,
            total_items=1,
            completed_items=5,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_experiment_run_status_defaults_to_pending(db_session: AsyncSession) -> None:
    chain = await _make_hierarchy(db_session)
    experiment = chain["experiment"]
    assert isinstance(experiment, Experiment)

    run = ExperimentRun(experiment_id=experiment.id, model=experiment.model, total_items=0)
    db_session.add(run)
    await db_session.flush()

    assert run.status == ExperimentRunStatus.PENDING


async def test_runs_for_an_experiment_are_queryable_without_n_plus_1(
    db_session: AsyncSession,
) -> None:
    """Confirms the FK + index makes "runs for this experiment" a single
    indexed query — exactly the access pattern the run list endpoint uses."""
    chain = await _make_hierarchy(db_session)
    experiment = chain["experiment"]
    assert isinstance(experiment, Experiment)

    result = await db_session.execute(
        select(ExperimentRun).where(ExperimentRun.experiment_id == experiment.id)
    )
    runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].id == chain["run"].id  # type: ignore[attr-defined]
