"""Translates between the `/generate` API schema and `LLMProvider`'s
provider-agnostic types.

Kept separate from the routes so the routes stay thin, and so this
translation is independently testable/reusable — the future experiment
engine (Phase 3) will build requests the same way, just from a stored
prompt/config instead of a request body.
"""

import time

from reliability_lab_llm import GenerationOptions, LLMProvider, Message
from reliability_lab_llm.types import GenerationResult

from app.schemas.generation import (
    ExecutionResult,
    GenerateRequest,
    GenerationParameters,
    TokenUsage,
)


def build_messages(request: GenerateRequest) -> list[Message]:
    return [Message(role=m.role, content=m.content) for m in request.messages]


def build_options(request: GenerateRequest) -> GenerationOptions:
    return GenerationOptions(
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        stop=request.stop,
        seed=request.seed,
    )


def build_parameters(request: GenerateRequest) -> GenerationParameters:
    return GenerationParameters(
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        stop=request.stop,
        seed=request.seed,
    )


def _usage_from_result(result: GenerationResult) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )


async def run_text_generation(provider: LLMProvider, request: GenerateRequest) -> ExecutionResult:
    result = await provider.generate(
        build_messages(request), model=request.model, options=build_options(request)
    )
    return ExecutionResult(
        model=result.model,
        provider=result.provider,
        response=result.text,
        finish_reason=result.finish_reason,
        latency_ms=result.latency_ms or 0.0,
        usage=_usage_from_result(result),
        parameters=build_parameters(request),
    )


async def run_structured_generation(
    provider: LLMProvider, request: GenerateRequest
) -> ExecutionResult:
    assert request.response_schema is not None  # enforced by the route before calling this

    started_at = time.perf_counter()
    data = await provider.generate_structured(
        build_messages(request),
        model=request.model,
        schema=request.response_schema,
        options=build_options(request),
    )
    latency_ms = (time.perf_counter() - started_at) * 1000

    return ExecutionResult(
        model=request.model,
        provider=provider.name,
        response="",
        structured_output=data if isinstance(data, dict) else data.model_dump(mode="json"),
        latency_ms=latency_ms,
        usage=TokenUsage(),
        parameters=build_parameters(request),
    )
