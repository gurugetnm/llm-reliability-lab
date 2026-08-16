"""`ExperimentRunner` — drives one `ExperimentRun` to completion.

    ExperimentRunner
       -> GenerationService  (app.services.generation_service)
       -> LLMProvider        (reliability_lab_llm)
       -> OllamaProvider
       -> Ollama

Independent of FastAPI on purpose: it takes a plain `LLMProvider` and a
session factory, not a request-scoped DB session or any FastAPI
dependency, so it runs equally well from a background `asyncio.Task`
(this phase) or, later, from a real job queue worker without change.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from reliability_lab_llm import LLMProvider
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.experiments.errors import classify_exception
from app.experiments.events import run_event_bus
from app.experiments.prompt_template import PromptTemplateError, build_context, render_prompt
from app.models.dataset import DatasetItem
from app.models.enums import ExperimentRunStatus, RunItemErrorType, RunItemStatus
from app.models.experiment import Experiment, ExperimentRun, RunItem
from app.schemas.generation import GenerateMessage, GenerateRequest
from app.services import generation_service

logger = logging.getLogger(__name__)

#: One item generation may not run forever — a hung Ollama request must
#: not hold a concurrency slot (and the run) open indefinitely.
DEFAULT_ITEM_TIMEOUT_SECONDS = 180.0

SessionFactory = Callable[[], AsyncSession]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExperimentRunner:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        session_factory: SessionFactory = AsyncSessionLocal,
        item_timeout_seconds: float = DEFAULT_ITEM_TIMEOUT_SECONDS,
    ) -> None:
        self._provider = provider
        self._session_factory = session_factory
        self._item_timeout_seconds = item_timeout_seconds

    async def execute_run(self, run_id: uuid.UUID) -> None:
        try:
            experiment, items = await self._start(run_id)
        except _RunAlreadyHandled:
            return

        if experiment is None:  # run/experiment vanished — nothing to do
            return

        run = await self._load_run(run_id)
        semaphore = asyncio.Semaphore(run.concurrency)
        await asyncio.gather(
            *(self._process_item(run_id, experiment, item, semaphore) for item in items)
        )

        await self._finish_run(run_id)

    # --- run-level bookkeeping ------------------------------------------

    async def _start(self, run_id: uuid.UUID) -> tuple[Experiment | None, list[DatasetItem]]:
        async with self._session_factory() as db:
            run = await db.get(ExperimentRun, run_id)
            if run is None:
                logger.warning("Run %s vanished before it could start", run_id)
                raise _RunAlreadyHandled

            if run.cancel_requested:
                run.status = ExperimentRunStatus.CANCELLED
                run.completed_at = _utcnow()
                await db.commit()
                await run_event_bus.publish(run_id, "run_cancelled", {"run_id": str(run_id)})
                raise _RunAlreadyHandled

            experiment = await db.get(Experiment, run.experiment_id)
            if experiment is None:
                run.status = ExperimentRunStatus.FAILED
                run.completed_at = _utcnow()
                await db.commit()
                await run_event_bus.publish(
                    run_id, "run_completed", {"run_id": str(run_id), "status": run.status}
                )
                raise _RunAlreadyHandled

            items = list(
                (
                    await db.execute(
                        select(DatasetItem)
                        .where(DatasetItem.dataset_id == experiment.dataset_id)
                        .order_by(DatasetItem.position)
                    )
                )
                .scalars()
                .all()
            )

            run.status = ExperimentRunStatus.RUNNING
            run.started_at = _utcnow()
            await db.commit()

        await run_event_bus.publish(
            run_id, "run_started", {"run_id": str(run_id), "total_items": len(items)}
        )
        return experiment, items

    async def _load_run(self, run_id: uuid.UUID) -> ExperimentRun:
        async with self._session_factory() as db:
            run = await db.get(ExperimentRun, run_id)
            assert run is not None
            return run

    async def _finish_run(self, run_id: uuid.UUID) -> None:
        async with self._session_factory() as db:
            run = await db.get(ExperimentRun, run_id)
            assert run is not None
            if run.cancel_requested:
                run.status = ExperimentRunStatus.CANCELLED
            elif run.failed_items == 0:
                run.status = ExperimentRunStatus.COMPLETED
            else:
                run.status = ExperimentRunStatus.COMPLETED_WITH_ERRORS
            run.completed_at = _utcnow()
            await db.commit()
            snapshot = _run_snapshot(run)

        await run_event_bus.publish(
            run_id,
            "run_cancelled" if run.status == ExperimentRunStatus.CANCELLED else "run_completed",
            snapshot,
        )

    # --- per-item processing ---------------------------------------------

    async def _process_item(
        self,
        run_id: uuid.UUID,
        experiment: Experiment,
        item: DatasetItem,
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            if await self._is_cancelled(run_id):
                await self._record_cancelled(run_id, item, experiment)
                return
            await self._generate_one(run_id, experiment, item)

    async def _is_cancelled(self, run_id: uuid.UUID) -> bool:
        async with self._session_factory() as db:
            result = await db.execute(
                select(ExperimentRun.cancel_requested).where(ExperimentRun.id == run_id)
            )
            return bool(result.scalar_one_or_none())

    async def _record_cancelled(
        self, run_id: uuid.UUID, item: DatasetItem, experiment: Experiment
    ) -> None:
        rendered_prompt = _try_render(experiment, item)
        run_item_id = await self._insert_run_item(
            run_id,
            experiment,
            item,
            status=RunItemStatus.CANCELLED,
            rendered_prompt=rendered_prompt,
        )
        await self._bump_counters(run_id, successful=False, failed=False)
        await run_event_bus.publish(
            run_id,
            "run_item_failed",
            {"run_id": str(run_id), "run_item_id": str(run_item_id), "status": "cancelled"},
        )
        await self._publish_progress(run_id)

    async def _generate_one(
        self, run_id: uuid.UUID, experiment: Experiment, item: DatasetItem
    ) -> None:
        try:
            rendered_prompt = render_prompt(
                experiment.user_prompt_template, build_context(item.input)
            )
        except PromptTemplateError as exc:
            run_item_id = await self._insert_run_item(
                run_id, experiment, item, status=RunItemStatus.RUNNING, rendered_prompt=""
            )
            await self._finish_item(
                run_id,
                run_item_id,
                status=RunItemStatus.FAILED,
                error_type=classify_exception(exc),
                error_message=str(exc),
            )
            await self._on_item_failed(run_id, run_item_id)
            return

        run_item_id = await self._insert_run_item(
            run_id, experiment, item, status=RunItemStatus.RUNNING, rendered_prompt=rendered_prompt
        )
        started_at = time.perf_counter()

        try:
            request = _build_generate_request(experiment, rendered_prompt)
            coro = (
                generation_service.run_structured_generation(self._provider, request)
                if experiment.structured_output_config
                else generation_service.run_text_generation(self._provider, request)
            )
            result = await asyncio.wait_for(coro, timeout=self._item_timeout_seconds)
        except TimeoutError:
            await self._finish_item(
                run_id,
                run_item_id,
                status=RunItemStatus.FAILED,
                error_type=RunItemErrorType.TIMEOUT,
                error_message=(
                    f"Generation did not complete within {self._item_timeout_seconds:.0f}s"
                ),
            )
            await self._on_item_failed(run_id, run_item_id)
            return
        except Exception as exc:  # noqa: BLE001 — a single item's failure must never abort the run
            logger.warning("Run %s item %s failed: %s", run_id, item.id, exc)
            await self._finish_item(
                run_id,
                run_item_id,
                status=RunItemStatus.FAILED,
                error_type=classify_exception(exc),
                error_message=str(exc)[:2000],
            )
            await self._on_item_failed(run_id, run_item_id)
            return

        latency_ms = (
            result.latency_ms
            if result.latency_ms is not None
            else (time.perf_counter() - started_at) * 1000
        )
        await self._finish_item(
            run_id,
            run_item_id,
            status=RunItemStatus.SUCCEEDED,
            response=result.response or None,
            structured_output=result.structured_output,
            input_tokens=result.usage.prompt_tokens,
            output_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            latency_ms=latency_ms,
        )
        await self._bump_counters(run_id, successful=True, failed=False)
        await run_event_bus.publish(
            run_id,
            "run_item_completed",
            {"run_id": str(run_id), "run_item_id": str(run_item_id), "status": "succeeded"},
        )
        await self._publish_progress(run_id)

    async def _on_item_failed(self, run_id: uuid.UUID, run_item_id: uuid.UUID) -> None:
        await self._bump_counters(run_id, successful=False, failed=True)
        await run_event_bus.publish(
            run_id,
            "run_item_failed",
            {"run_id": str(run_id), "run_item_id": str(run_item_id), "status": "failed"},
        )
        await self._publish_progress(run_id)

    async def _publish_progress(self, run_id: uuid.UUID) -> None:
        async with self._session_factory() as db:
            run = await db.get(ExperimentRun, run_id)
            assert run is not None
            snapshot = _run_snapshot(run)
        await run_event_bus.publish(run_id, "run_progress", snapshot)

    # --- RunItem persistence ----------------------------------------------

    async def _insert_run_item(
        self,
        run_id: uuid.UUID,
        experiment: Experiment,
        item: DatasetItem,
        *,
        status: RunItemStatus,
        rendered_prompt: str,
    ) -> uuid.UUID:
        async with self._session_factory() as db:
            run_item = RunItem(
                run_id=run_id,
                dataset_item_id=item.id,
                status=status,
                model=experiment.model,
                system_prompt=experiment.system_prompt,
                user_prompt=rendered_prompt,
                generation_config=experiment.generation_config,
            )
            db.add(run_item)
            await db.commit()
            await db.refresh(run_item)
            return run_item.id

    async def _finish_item(
        self,
        run_id: uuid.UUID,
        run_item_id: uuid.UUID,
        *,
        status: RunItemStatus,
        response: str | None = None,
        structured_output: dict[str, Any] | None = None,
        error_type: RunItemErrorType | None = None,
        error_message: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        async with self._session_factory() as db:
            run_item = await db.get(RunItem, run_item_id)
            assert run_item is not None
            run_item.status = status
            run_item.response = response
            run_item.structured_output = structured_output
            run_item.error_type = error_type
            run_item.error_message = error_message
            run_item.input_tokens = input_tokens
            run_item.output_tokens = output_tokens
            run_item.total_tokens = total_tokens
            run_item.latency_ms = latency_ms
            run_item.completed_at = _utcnow()
            await db.commit()

    async def _bump_counters(self, run_id: uuid.UUID, *, successful: bool, failed: bool) -> None:
        """A single atomic `UPDATE` (server-side arithmetic) rather than a
        read-modify-write — safe under concurrent items finishing at once,
        even though each uses its own short-lived session/connection."""
        async with self._session_factory() as db:
            await db.execute(
                update(ExperimentRun)
                .where(ExperimentRun.id == run_id)
                .values(
                    completed_items=ExperimentRun.completed_items + 1,
                    successful_items=ExperimentRun.successful_items + (1 if successful else 0),
                    failed_items=ExperimentRun.failed_items + (1 if failed else 0),
                )
            )
            await db.commit()


def _try_render(experiment: Experiment, item: DatasetItem) -> str:
    """Best-effort rendering for a `RunItem` that won't call the LLM
    anyway (e.g. it's being recorded as cancelled) — a broken template
    just means the record's `user_prompt` is left blank."""
    try:
        return render_prompt(experiment.user_prompt_template, build_context(item.input))
    except PromptTemplateError:
        return ""


class _RunAlreadyHandled(Exception):
    """Internal control-flow signal: `_start` already finalized the run
    (it was pre-cancelled, or its experiment vanished) — nothing left to do."""


def _build_generate_request(experiment: Experiment, rendered_prompt: str) -> GenerateRequest:
    config = experiment.generation_config or {}
    messages = []
    if experiment.system_prompt:
        messages.append(GenerateMessage(role="system", content=experiment.system_prompt))
    messages.append(GenerateMessage(role="user", content=rendered_prompt))

    response_schema = None
    if experiment.structured_output_config:
        response_schema = experiment.structured_output_config.get("schema")

    return GenerateRequest(
        model=experiment.model,
        messages=messages,
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens"),
        top_p=config.get("top_p"),
        stop=config.get("stop"),
        seed=config.get("seed"),
        response_schema=response_schema,
    )


def _run_snapshot(run: ExperimentRun) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "status": run.status,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
        "successful_items": run.successful_items,
        "failed_items": run.failed_items,
    }
