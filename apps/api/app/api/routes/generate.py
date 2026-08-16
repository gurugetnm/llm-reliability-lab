"""`/api/v1/generate` and `/api/v1/generate/stream`.

Non-streaming and streaming generation, both translating `GenerateRequest`
into provider-agnostic calls via `app.services.generation_service`.
Provider errors (Ollama down, model missing, bad structured output) are
handled centrally for the non-streaming route (see `app.core.exceptions`)
— but a streaming response has already started sending bytes by the time
an error can occur mid-stream, so `/generate/stream` catches provider
errors itself and emits an `error` SSE event instead of relying on
FastAPI's exception handlers, which can't apply once the body has begun.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from reliability_lab_llm import ModelNotFoundError, ProviderConnectionError, ProviderError

from app.core.exceptions import ValidationError
from app.llm.dependencies import LLMProviderDep
from app.schemas.generation import ExecutionResult, GenerateRequest, TokenUsage
from app.services import generation_service

router = APIRouter(tags=["generate"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=ExecutionResult)
async def generate(request: GenerateRequest, provider: LLMProviderDep) -> ExecutionResult:
    if request.response_schema is not None:
        return await generation_service.run_structured_generation(provider, request)
    return await generation_service.run_text_generation(provider, request)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/generate/stream")
async def generate_stream(request: GenerateRequest, provider: LLMProviderDep) -> StreamingResponse:
    if request.response_schema is not None:
        raise ValidationError("Structured output is not supported in streaming mode yet")

    async def event_source() -> AsyncIterator[str]:
        request_id = uuid.uuid4()
        started_at = time.perf_counter()
        chunks: list[str] = []
        finish_reason: str | None = None
        usage = TokenUsage()

        try:
            messages = generation_service.build_messages(request)
            options = generation_service.build_options(request)
            async for chunk in provider.stream(messages, model=request.model, options=options):
                chunks.append(chunk.delta)
                finish_reason = chunk.finish_reason or finish_reason
                if chunk.done:
                    usage = TokenUsage(
                        prompt_tokens=chunk.prompt_tokens,
                        completion_tokens=chunk.completion_tokens,
                        total_tokens=chunk.total_tokens,
                    )
                yield _sse("chunk", {"delta": chunk.delta, "done": chunk.done})
        except ModelNotFoundError as exc:
            yield _sse("error", {"detail": str(exc)})
            return
        except ProviderConnectionError as exc:
            yield _sse("error", {"detail": str(exc)})
            return
        except ProviderError as exc:
            logger.exception("Streaming generation failed")
            yield _sse("error", {"detail": str(exc)})
            return

        result = ExecutionResult(
            id=request_id,
            model=request.model,
            provider=provider.name,
            response="".join(chunks),
            finish_reason=finish_reason,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            usage=usage,
            parameters=generation_service.build_parameters(request),
        )
        yield _sse("done", json.loads(result.model_dump_json()))

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
