"""Integration tests for `ExperimentRunner`.

These need real cross-connection visibility — the runner opens its own
short-lived session per operation (by design, see runner.py's
docstring), so the shared, savepoint-rolled-back `db_session` fixture
used elsewhere can't see its writes. Every test here uses its own
`async_sessionmaker` bound to the same test database instead, and each
test uses uniquely-named rows so leftover data (cleaned up only at the
end of the test session) never cross-contaminates.
"""

import asyncio
import uuid

from app.experiments.runner import ExperimentRunner
from app.models.dataset import Dataset, DatasetItem
from app.models.enums import ExperimentRunStatus, RunItemErrorType, RunItemStatus
from app.models.experiment import Experiment, ExperimentRun, RunItem
from app.models.project import Project
from reliability_lab_llm import GenerationResult, ProviderConnectionError
from reliability_lab_llm.exceptions import StructuredOutputError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import test_engine
from tests.fakes import ScriptedLLMProvider

_Session = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def _make_run(
    *, item_count: int, concurrency: int = 3, structured: bool = False
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Creates a Project -> Dataset (+N items) -> Experiment -> pending
    ExperimentRun, all committed for real, and returns (run_id, item_ids)."""
    unique = uuid.uuid4().hex[:8]
    async with _Session() as db:
        project = Project(name=f"Runner test project {unique}")
        db.add(project)
        await db.flush()

        dataset = Dataset(project_id=project.id, name=f"Runner test dataset {unique}")
        db.add(dataset)
        await db.flush()

        item_ids = []
        for i in range(item_count):
            item = DatasetItem(dataset_id=dataset.id, input=f"question {i}", position=i)
            db.add(item)
            await db.flush()
            item_ids.append(item.id)

        experiment = Experiment(
            project_id=project.id,
            dataset_id=dataset.id,
            name=f"Runner test experiment {unique}",
            user_prompt_template="Answer: {{input}}",
            model="scripted-model",
            generation_config={"temperature": 0.1},
            structured_output_config=(
                {"schema": {"type": "object", "properties": {"answer": {"type": "string"}}}}
                if structured
                else None
            ),
        )
        db.add(experiment)
        await db.flush()

        run = ExperimentRun(
            experiment_id=experiment.id,
            model=experiment.model,
            generation_config=experiment.generation_config,
            total_items=item_count,
            concurrency=concurrency,
        )
        db.add(run)
        await db.commit()
        return run.id, item_ids


async def _get_run(run_id: uuid.UUID) -> ExperimentRun:
    async with _Session() as db:
        run = await db.get(ExperimentRun, run_id)
        assert run is not None
        return run


async def _get_run_items(run_id: uuid.UUID) -> list[RunItem]:
    async with _Session() as db:
        result = await db.execute(
            select(RunItem).where(RunItem.run_id == run_id).order_by(RunItem.created_at)
        )
        return list(result.scalars().all())


def _ok(text: str = "an answer") -> GenerationResult:
    return GenerationResult(
        text=text,
        model="scripted-model",
        provider="scripted",
        prompt_tokens=5,
        completion_tokens=3,
        total_tokens=8,
        finish_reason="stop",
        latency_ms=1.0,
    )


# --- success ---------------------------------------------------------------


async def test_runner_success_marks_run_completed() -> None:
    run_id, _ = await _make_run(item_count=3, concurrency=3)
    provider = ScriptedLLMProvider([_ok(), _ok(), _ok()])

    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.COMPLETED
    assert run.completed_items == 3
    assert run.successful_items == 3
    assert run.failed_items == 0
    assert run.started_at is not None
    assert run.completed_at is not None

    items = await _get_run_items(run_id)
    assert len(items) == 3
    assert all(item.status == RunItemStatus.SUCCEEDED for item in items)
    assert all(item.total_tokens == 8 for item in items)
    assert all(item.user_prompt.startswith("Answer: question") for item in items)


# --- partial failure ---------------------------------------------------------


async def test_runner_partial_failure_marks_completed_with_errors() -> None:
    run_id, _ = await _make_run(item_count=3, concurrency=1)
    provider = ScriptedLLMProvider([_ok(), ProviderConnectionError("Ollama is unreachable"), _ok()])

    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.COMPLETED_WITH_ERRORS
    assert run.successful_items == 2
    assert run.failed_items == 1

    items = await _get_run_items(run_id)
    failed = [item for item in items if item.status == RunItemStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].error_type == RunItemErrorType.PROVIDER_ERROR
    assert failed[0].error_message is not None


async def test_runner_continues_after_a_single_item_failure() -> None:
    """A single failed item must not abort the run — every item is
    still attempted."""
    run_id, _ = await _make_run(item_count=5, concurrency=1)
    provider = ScriptedLLMProvider(
        [_ok(), Exception("boom"), _ok(), Exception("boom again"), _ok()]
    )

    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    run = await _get_run(run_id)
    assert run.completed_items == 5
    assert run.successful_items == 3
    assert run.failed_items == 2


# --- structured output failure ---------------------------------------------------------


async def test_runner_classifies_structured_output_failures() -> None:
    run_id, _ = await _make_run(item_count=1, concurrency=1, structured=True)
    provider = ScriptedLLMProvider(
        [StructuredOutputError("Output did not match the schema", raw_text="not json")]
    )

    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.COMPLETED_WITH_ERRORS
    items = await _get_run_items(run_id)
    assert items[0].error_type == RunItemErrorType.STRUCTURED_OUTPUT_ERROR


# --- timeout (slow model) ---------------------------------------------------------


async def test_runner_classifies_a_hung_generation_as_a_timeout() -> None:
    run_id, _ = await _make_run(item_count=1, concurrency=1)
    provider = ScriptedLLMProvider([_ok()], delay_seconds=0.5)

    runner = ExperimentRunner(provider, session_factory=_Session, item_timeout_seconds=0.05)
    await runner.execute_run(run_id)

    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.COMPLETED_WITH_ERRORS
    items = await _get_run_items(run_id)
    assert items[0].error_type == RunItemErrorType.TIMEOUT


# --- concurrency ---------------------------------------------------------


async def test_runner_never_exceeds_the_configured_concurrency() -> None:
    run_id, _ = await _make_run(item_count=8, concurrency=2)
    provider = ScriptedLLMProvider([_ok() for _ in range(8)], delay_seconds=0.05)

    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    assert provider.call_count == 8
    assert provider.max_in_flight <= 2


# --- cancellation ---------------------------------------------------------


async def test_runner_cancellation_stops_new_items_but_finishes_in_flight() -> None:
    run_id, _ = await _make_run(item_count=6, concurrency=2)
    provider = ScriptedLLMProvider([_ok() for _ in range(6)], delay_seconds=0.1)

    runner = ExperimentRunner(provider, session_factory=_Session)
    run_task = asyncio.create_task(runner.execute_run(run_id))

    # Give the first batch a moment to start, then request cancellation
    # mid-run — items already in flight should still finish; items that
    # haven't started yet should not be sent to the provider at all.
    await asyncio.sleep(0.05)
    async with _Session() as db:
        run = await db.get(ExperimentRun, run_id)
        assert run is not None
        run.cancel_requested = True
        await db.commit()

    await run_task

    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.CANCELLED
    assert run.completed_at is not None
    # Fewer than all 6 items should have reached the provider.
    assert provider.call_count < 6

    items = await _get_run_items(run_id)
    assert len(items) == 6  # every item still gets a RunItem record...
    cancelled = [item for item in items if item.status == RunItemStatus.CANCELLED]
    assert len(cancelled) > 0  # ...even the ones that never ran


async def test_runner_pre_cancelled_run_never_calls_the_provider() -> None:
    run_id, _ = await _make_run(item_count=3, concurrency=3)
    async with _Session() as db:
        run = await db.get(ExperimentRun, run_id)
        assert run is not None
        run.cancel_requested = True
        await db.commit()

    provider = ScriptedLLMProvider([_ok(), _ok(), _ok()])
    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    assert provider.call_count == 0
    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.CANCELLED


# --- prompt rendering failure ---------------------------------------------------------


async def test_runner_classifies_a_broken_prompt_template_without_calling_the_provider() -> None:
    unique = uuid.uuid4().hex[:8]
    async with _Session() as db:
        project = Project(name=f"Broken template project {unique}")
        db.add(project)
        await db.flush()
        dataset = Dataset(project_id=project.id, name=f"Broken template dataset {unique}")
        db.add(dataset)
        await db.flush()
        item = DatasetItem(dataset_id=dataset.id, input="x", position=0)
        db.add(item)
        await db.flush()
        # A template that's valid at experiment-creation time can't exist
        # here (validate_template would reject it) — this simulates
        # persisted state where the stored template is nonetheless broken
        # (e.g. hand-edited in the database).
        experiment = Experiment(
            project_id=project.id,
            dataset_id=dataset.id,
            name=f"Broken template experiment {unique}",
            user_prompt_template="{{unknown_variable}}",
            model="scripted-model",
            generation_config={},
        )
        db.add(experiment)
        await db.flush()
        run = ExperimentRun(
            experiment_id=experiment.id, model=experiment.model, total_items=1, concurrency=1
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    provider = ScriptedLLMProvider([_ok()])
    await ExperimentRunner(provider, session_factory=_Session).execute_run(run_id)

    assert provider.call_count == 0
    run = await _get_run(run_id)
    assert run.status == ExperimentRunStatus.COMPLETED_WITH_ERRORS
    items = await _get_run_items(run_id)
    assert items[0].error_type == RunItemErrorType.PROMPT_RENDER_ERROR
