"""`/api/v1/models` — model discovery against the configured LLMProvider.

`ProviderConnectionError` (Ollama unreachable) and `ModelNotFoundError`
are handled centrally (see `app.core.exceptions`) — routes here don't
need their own try/except for those.
"""

import time

from fastapi import APIRouter
from reliability_lab_llm import ModelSummary

from app.llm.dependencies import LLMProviderDep
from app.schemas.model import ModelsHealthResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelSummary])
async def list_models(provider: LLMProviderDep) -> list[ModelSummary]:
    return await provider.get_models()


@router.get("/health", response_model=ModelsHealthResponse)
async def models_health(provider: LLMProviderDep) -> ModelsHealthResponse:
    started_at = time.perf_counter()
    try:
        models = await provider.get_models()
    except Exception as exc:  # noqa: BLE001 — this endpoint's whole job is to report provider health, never raise
        return ModelsHealthResponse(available=False, provider=provider.name, error=str(exc))

    return ModelsHealthResponse(
        available=True,
        provider=provider.name,
        model_count=len(models),
        latency_ms=(time.perf_counter() - started_at) * 1000,
    )
