"""Relationship, cascade, and constraint coverage for the evaluation
engine's persistence layer (`ExperimentRun` -> `EvaluationRun` ->
`EvaluationResult`).

Model/DB-level tests only — no HTTP, no evaluator/runner involved — so
they exercise exactly what the ORM mappings and Alembic-managed
constraints enforce, the same way test_db_experiments.py does for Phase 3.
"""

import uuid
from typing import TypeVar

import pytest
from app.db.base import Base
from app.models import (
    Dataset,
    DatasetItem,
    EvaluationResult,
    EvaluationRun,
    Experiment,
    ExperimentRun,
    Project,
    RunItem,
)
from app.models.enums import EvaluationResultStatus, EvaluationRunStatus, RunItemStatus
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT", bound=Base)


async def _get(  # noqa: UP047 — PEP 695 generics need Python 3.12+, this package supports 3.11+
    db_session: AsyncSession, model: type[ModelT], id_: uuid.UUID
) -> ModelT | None:
    query = select(model).where(model.id == id_).execution_options(populate_existing=True)  # type: ignore[attr-defined]
    result = await db_session.execute(query)
    return result.scalar_one_or_none()


async def _make_hierarchy(db_session: AsyncSession) -> dict[str, object]:
    """Builds Project -> ... -> RunItem -> EvaluationRun -> EvaluationResult."""
    project = Project(name="Evaluation engine test project")
    db_session.add(project)
    await db_session.flush()

    dataset = Dataset(project_id=project.id, name="Q&A set", version=1)
    db_session.add(dataset)
    await db_session.flush()

    item = DatasetItem(
        dataset_id=dataset.id,
        input={"question": "What is TCP?"},
        expected_output="A protocol",
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
        generation_config={"temperature": 0.2},
    )
    db_session.add(run_item)
    await db_session.flush()

    evaluation_run = EvaluationRun(
        run_id=run.id,
        name="Exact match check",
        evaluator_type="exact_match",
        evaluator_version="v1",
        configuration={"case_sensitive": False},
        total_items=1,
    )
    db_session.add(evaluation_run)
    await db_session.flush()

    evaluation_result = EvaluationResult(
        evaluation_run_id=evaluation_run.id,
        run_item_id=run_item.id,
        status=EvaluationResultStatus.SUCCEEDED,
        metric_name="exact_match",
        score=1.0,
        passed=True,
        reason="Exact match.",
        details={"expected": "a protocol", "actual": "a protocol"},
        evaluator="exact_match:v1",
    )
    db_session.add(evaluation_result)
    await db_session.flush()

    return {
        "project": project,
        "dataset": dataset,
        "item": item,
        "experiment": experiment,
        "run": run,
        "run_item": run_item,
        "evaluation_run": evaluation_run,
        "evaluation_result": evaluation_result,
    }


async def test_full_hierarchy_persists_and_is_queryable(db_session: AsyncSession) -> None:
    chain = await _make_hierarchy(db_session)

    fetched = await _get(db_session, EvaluationResult, chain["evaluation_result"].id)  # type: ignore[attr-defined]
    assert fetched is not None
    assert fetched.evaluation_run_id == chain["evaluation_run"].id  # type: ignore[attr-defined]
    assert fetched.run_item_id == chain["run_item"].id  # type: ignore[attr-defined]
    assert fetched.score == 1.0
    assert fetched.passed is True


async def test_evaluation_run_status_defaults_to_pending(db_session: AsyncSession) -> None:
    chain = await _make_hierarchy(db_session)
    run = chain["run"]
    assert isinstance(run, ExperimentRun)

    evaluation_run = EvaluationRun(
        run_id=run.id, name="Second pass", evaluator_type="contains", evaluator_version="v1"
    )
    db_session.add(evaluation_run)
    await db_session.flush()

    assert evaluation_run.status == EvaluationRunStatus.PENDING
    assert evaluation_run.configuration == {}


async def test_deleting_experiment_run_cascades_to_evaluation_run_and_results(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["run"])
    await db_session.flush()

    assert await _get(db_session, EvaluationRun, chain["evaluation_run"].id) is None  # type: ignore[attr-defined]
    assert await _get(db_session, EvaluationResult, chain["evaluation_result"].id) is None  # type: ignore[attr-defined]


async def test_deleting_evaluation_run_cascades_to_its_results_only(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["evaluation_run"])
    await db_session.flush()

    assert await _get(db_session, EvaluationResult, chain["evaluation_result"].id) is None  # type: ignore[attr-defined]
    # The RunItem it evaluated is untouched — evaluation is re-runnable
    # without needing to re-execute generation.
    assert await _get(db_session, RunItem, chain["run_item"].id) is not None  # type: ignore[attr-defined]


async def test_deleting_run_item_cascades_to_its_evaluation_results(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)

    await db_session.delete(chain["run_item"])
    await db_session.flush()

    assert await _get(db_session, EvaluationResult, chain["evaluation_result"].id) is None  # type: ignore[attr-defined]
    # The EvaluationRun record itself survives — only the one result tied
    # to the deleted item is gone.
    assert await _get(db_session, EvaluationRun, chain["evaluation_run"].id) is not None  # type: ignore[attr-defined]


async def test_evaluation_run_completed_items_cannot_exceed_total_items(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)
    run = chain["run"]
    assert isinstance(run, ExperimentRun)

    db_session.add(
        EvaluationRun(
            run_id=run.id,
            name="Bad counters",
            evaluator_type="exact_match",
            evaluator_version="v1",
            total_items=1,
            completed_items=5,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_a_run_item_can_have_multiple_evaluation_results(db_session: AsyncSession) -> None:
    """The same RunItem can be scored by more than one evaluator (or the
    same evaluator re-run) without touching generation at all."""
    chain = await _make_hierarchy(db_session)
    run = chain["run"]
    run_item = chain["run_item"]
    assert isinstance(run, ExperimentRun)
    assert isinstance(run_item, RunItem)

    second_run = EvaluationRun(
        run_id=run.id,
        name="Contains check",
        evaluator_type="contains",
        evaluator_version="v1",
        total_items=1,
    )
    db_session.add(second_run)
    await db_session.flush()

    db_session.add(
        EvaluationResult(
            evaluation_run_id=second_run.id,
            run_item_id=run_item.id,
            status=EvaluationResultStatus.SUCCEEDED,
            metric_name="contains",
            score=0.5,
            passed=False,
            evaluator="contains:v1",
        )
    )
    await db_session.flush()

    result = await db_session.execute(
        select(EvaluationResult).where(EvaluationResult.run_item_id == run_item.id)
    )
    assert len(result.scalars().all()) == 2


async def test_results_for_an_evaluation_run_are_queryable_without_n_plus_1(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)
    evaluation_run = chain["evaluation_run"]
    assert isinstance(evaluation_run, EvaluationRun)

    result = await db_session.execute(
        select(EvaluationResult).where(EvaluationResult.evaluation_run_id == evaluation_run.id)
    )
    results = result.scalars().all()
    assert len(results) == 1
    assert results[0].id == chain["evaluation_result"].id  # type: ignore[attr-defined]


async def test_a_failed_result_can_have_a_null_score_and_an_error_message(
    db_session: AsyncSession,
) -> None:
    chain = await _make_hierarchy(db_session)
    evaluation_run = chain["evaluation_run"]
    run_item = chain["run_item"]
    assert isinstance(evaluation_run, EvaluationRun)
    assert isinstance(run_item, RunItem)

    failed = EvaluationResult(
        evaluation_run_id=evaluation_run.id,
        run_item_id=run_item.id,
        status=EvaluationResultStatus.FAILED,
        metric_name="llm_judge",
        evaluator="llm_judge:v1",
        error_message="Judge model returned invalid structured output",
    )
    db_session.add(failed)
    await db_session.flush()

    fetched = await _get(db_session, EvaluationResult, failed.id)
    assert fetched is not None
    assert fetched.score is None
    assert fetched.passed is None
    assert fetched.error_message == "Judge model returned invalid structured output"
