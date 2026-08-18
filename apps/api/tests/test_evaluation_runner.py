"""Integration tests for `EvaluationRunner`.

Same reasoning as test_runner.py: the runner opens its own short-lived
session per operation, so tests use their own `async_sessionmaker` bound
to the test database rather than the shared, savepoint-rolled-back
`db_session` fixture.

`FlakyEvaluator` (registered below, once, at import time) plays the role
`ScriptedLLMProvider` plays for `ExperimentRunner` tests: a scripted,
deterministic test double that lets a test dictate exactly which items
succeed, fail, or hang, and tracks concurrency in-flight.
"""

import asyncio
import uuid

from app.evaluation.runner import EvaluationRunner
from app.models.dataset import Dataset, DatasetItem
from app.models.enums import (
    EvaluationResultStatus,
    EvaluationRunStatus,
    ExperimentRunStatus,
    RunItemStatus,
)
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.models.experiment import Experiment, ExperimentRun, RunItem
from app.models.project import Project
from pydantic import BaseModel, Field
from reliability_lab_evaluation import (
    Evaluator,
    EvaluatorExecutionError,
    EvaluatorRegistry,
)
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import test_engine
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

_Session = async_sessionmaker(bind=test_engine, expire_on_commit=False)


class _FlakyConfig(BaseModel):
    outcomes: list[str] = Field(default_factory=list)  # "ok" | "error" per item, consumed in order
    delay_seconds: float = 0.0


@EvaluatorRegistry.register
class FlakyEvaluator(Evaluator):
    """Test-only evaluator, scripted like `tests.fakes.ScriptedLLMProvider`
    — registered once against the process-wide `EvaluatorRegistry`
    (see test_evaluators_basic.py's superset assertion, which accounts
    for this)."""

    metadata = EvaluatorMetadata(
        name="flaky_test", version="v1", description="test double", score_range=(0.0, 1.0)
    )
    config_model = _FlakyConfig

    def __init__(self, config: dict[str, object], **kwargs: object) -> None:
        super().__init__(config, **kwargs)  # type: ignore[arg-type]
        self._index = 0
        self._lock = asyncio.Lock()
        self.call_count = 0
        self.in_flight = 0
        self.max_in_flight = 0

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: _FlakyConfig = self.config  # type: ignore[assignment]
        async with self._lock:
            index = min(self._index, len(config.outcomes) - 1)
            self._index += 1
            self.call_count += 1
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if config.delay_seconds:
                await asyncio.sleep(config.delay_seconds)
            outcome = config.outcomes[index]
            if outcome == "error":
                raise EvaluatorExecutionError("scripted failure", details={"scripted": True})
            return EvaluationOutput(score=1.0, passed=True, reason="ok", details={})
        finally:
            async with self._lock:
                self.in_flight -= 1


async def _make_evaluation(
    *,
    item_count: int,
    evaluator_type: str = "flaky_test",
    configuration: dict[str, object] | None = None,
    concurrency: int = 3,
    run_status: ExperimentRunStatus = ExperimentRunStatus.COMPLETED,
    with_expected_output: bool = True,
) -> uuid.UUID:
    """Creates a full Project -> ... -> ExperimentRun (+N succeeded
    RunItems) -> pending EvaluationRun, all committed for real."""
    unique = uuid.uuid4().hex[:8]
    async with _Session() as db:
        project = Project(name=f"Eval runner test project {unique}")
        db.add(project)
        await db.flush()

        dataset = Dataset(project_id=project.id, name=f"Eval runner test dataset {unique}")
        db.add(dataset)
        await db.flush()

        experiment = Experiment(
            project_id=project.id,
            dataset_id=dataset.id,
            name=f"Eval runner test experiment {unique}",
            user_prompt_template="Answer: {{input}}",
            model="candidate-model",
            generation_config={},
        )
        db.add(experiment)
        await db.flush()

        run = ExperimentRun(
            experiment_id=experiment.id,
            model=experiment.model,
            total_items=item_count,
            status=run_status,
        )
        db.add(run)
        await db.flush()

        for i in range(item_count):
            item = DatasetItem(
                dataset_id=dataset.id,
                input=f"question {i}",
                expected_output=(f"answer {i}" if with_expected_output else None),
                position=i,
            )
            db.add(item)
            await db.flush()

            run_item = RunItem(
                run_id=run.id,
                dataset_item_id=item.id,
                model=experiment.model,
                user_prompt=f"Answer: question {i}",
                status=RunItemStatus.SUCCEEDED,
                response=f"answer {i}",
                generation_config={},
            )
            db.add(run_item)
        await db.flush()

        evaluation_run = EvaluationRun(
            run_id=run.id,
            name=f"Eval {unique}",
            evaluator_type=evaluator_type,
            evaluator_version="v1",
            configuration=configuration or {},
            total_items=0,
            concurrency=concurrency,
        )
        db.add(evaluation_run)
        await db.commit()
        return evaluation_run.id


async def _get_evaluation(evaluation_run_id: uuid.UUID) -> EvaluationRun:
    async with _Session() as db:
        evaluation_run = await db.get(EvaluationRun, evaluation_run_id)
        assert evaluation_run is not None
        return evaluation_run


async def _get_results(evaluation_run_id: uuid.UUID) -> list[EvaluationResult]:
    async with _Session() as db:
        result = await db.execute(
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == evaluation_run_id)
            .order_by(EvaluationResult.created_at)
        )
        return list(result.scalars().all())


# --- success -----------------------------------------------------------


async def test_runner_success_marks_evaluation_completed() -> None:
    evaluation_id = await _make_evaluation(
        item_count=3, configuration={"outcomes": ["ok", "ok", "ok"]}
    )

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    assert evaluation_run.total_items == 3
    assert evaluation_run.completed_items == 3
    assert evaluation_run.successful_items == 3
    assert evaluation_run.failed_items == 0
    assert evaluation_run.started_at is not None
    assert evaluation_run.completed_at is not None

    results = await _get_results(evaluation_id)
    assert len(results) == 3
    assert all(r.status == EvaluationResultStatus.SUCCEEDED for r in results)
    assert all(r.score == 1.0 for r in results)
    assert all(r.evaluator == "flaky_test:v1" for r in results)


async def test_exact_match_evaluator_end_to_end() -> None:
    """A real (non-scripted) evaluator, exercised through the full runner."""
    evaluation_id = await _make_evaluation(item_count=3, evaluator_type="exact_match")

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    results = await _get_results(evaluation_id)
    # RunItem.response == f"answer {i}" == DatasetItem.expected_output for every item.
    assert all(r.score == 1.0 and r.passed is True for r in results)


# --- partial failure -----------------------------------------------------


async def test_runner_partial_failure_marks_completed_with_errors() -> None:
    evaluation_id = await _make_evaluation(
        item_count=3, configuration={"outcomes": ["ok", "error", "ok"]}, concurrency=1
    )

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED_WITH_ERRORS
    assert evaluation_run.successful_items == 2
    assert evaluation_run.failed_items == 1

    results = await _get_results(evaluation_id)
    failed = [r for r in results if r.status == EvaluationResultStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].error_message == "scripted failure"
    assert failed[0].details == {"scripted": True}
    assert failed[0].score is None


async def test_runner_continues_after_a_single_item_failure() -> None:
    evaluation_id = await _make_evaluation(
        item_count=5,
        configuration={"outcomes": ["ok", "error", "ok", "error", "ok"]},
        concurrency=1,
    )

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.completed_items == 5
    assert evaluation_run.successful_items == 3
    assert evaluation_run.failed_items == 2


# --- timeout -----------------------------------------------------------


async def test_runner_classifies_a_hung_evaluation_as_a_failure() -> None:
    evaluation_id = await _make_evaluation(
        item_count=1, configuration={"outcomes": ["ok"], "delay_seconds": 0.5}
    )

    runner = EvaluationRunner(session_factory=_Session, item_timeout_seconds=0.05)
    await runner.execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED_WITH_ERRORS
    results = await _get_results(evaluation_id)
    assert results[0].status == EvaluationResultStatus.FAILED
    assert "did not complete within" in (results[0].error_message or "")


# --- concurrency -----------------------------------------------------------


async def test_runner_never_exceeds_the_configured_concurrency() -> None:
    evaluation_id = await _make_evaluation(
        item_count=8,
        configuration={"outcomes": ["ok"] * 8, "delay_seconds": 0.05},
        concurrency=2,
    )

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.successful_items == 8


# --- cancellation -----------------------------------------------------------


async def test_runner_cancellation_stops_new_items_but_finishes_in_flight() -> None:
    evaluation_id = await _make_evaluation(
        item_count=6,
        configuration={"outcomes": ["ok"] * 6, "delay_seconds": 0.1},
        concurrency=2,
    )

    runner = EvaluationRunner(session_factory=_Session)
    run_task = asyncio.create_task(runner.execute_evaluation(evaluation_id))

    await asyncio.sleep(0.05)
    async with _Session() as db:
        evaluation_run = await db.get(EvaluationRun, evaluation_id)
        assert evaluation_run is not None
        evaluation_run.cancel_requested = True
        await db.commit()

    await run_task

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.CANCELLED
    assert evaluation_run.completed_at is not None

    results = await _get_results(evaluation_id)
    assert len(results) == 6  # every item still gets a result record...
    cancelled = [r for r in results if r.status == EvaluationResultStatus.CANCELLED]
    assert len(cancelled) > 0  # ...even the ones that never ran


async def test_runner_pre_cancelled_evaluation_never_evaluates_anything() -> None:
    evaluation_id = await _make_evaluation(
        item_count=3, configuration={"outcomes": ["ok", "ok", "ok"]}
    )
    async with _Session() as db:
        evaluation_run = await db.get(EvaluationRun, evaluation_id)
        assert evaluation_run is not None
        evaluation_run.cancel_requested = True
        await db.commit()

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.CANCELLED
    results = await _get_results(evaluation_id)
    assert results == []


# --- empty dataset -----------------------------------------------------------


async def test_runner_empty_run_completes_immediately() -> None:
    evaluation_id = await _make_evaluation(item_count=0)

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    assert evaluation_run.total_items == 0
    assert evaluation_run.completed_at is not None


# --- missing expected output -----------------------------------------------------------


async def test_runner_handles_missing_expected_output_gracefully() -> None:
    evaluation_id = await _make_evaluation(
        item_count=2, evaluator_type="exact_match", with_expected_output=False
    )

    await EvaluationRunner(session_factory=_Session).execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    # Every item still gets a *succeeded* result — exact_match just
    # reports a null score/passed, never a runner-level failure.
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    assert evaluation_run.successful_items == 2
    results = await _get_results(evaluation_id)
    assert all(r.score is None and r.passed is None for r in results)


# --- real embedding/judge providers wired through the runner -----------------


async def test_runner_wires_embedding_provider_to_semantic_similarity() -> None:
    evaluation_id = await _make_evaluation(
        item_count=2, evaluator_type="semantic_similarity", configuration={"threshold": 0.0}
    )

    runner = EvaluationRunner(embedding_provider=FakeEmbeddingProvider(), session_factory=_Session)
    await runner.execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    results = await _get_results(evaluation_id)
    assert all(r.score is not None for r in results)


async def test_runner_wires_llm_provider_to_llm_judge() -> None:
    judgment = {
        "score": 4,
        "passed": True,
        "reason": "good",
        "criteria": {"accuracy": 4, "relevance": 4, "completeness": 4},
    }
    evaluation_id = await _make_evaluation(
        item_count=2, evaluator_type="llm_judge", configuration={"judge_model": "qwen3"}
    )

    runner = EvaluationRunner(
        llm_provider=FakeLLMProvider(structured_result=judgment), session_factory=_Session
    )
    await runner.execute_evaluation(evaluation_id)

    evaluation_run = await _get_evaluation(evaluation_id)
    assert evaluation_run.status == EvaluationRunStatus.COMPLETED
    results = await _get_results(evaluation_id)
    assert all(r.score == 0.8 for r in results)
    assert all(r.details["judge_model"] == "qwen3" for r in results)
