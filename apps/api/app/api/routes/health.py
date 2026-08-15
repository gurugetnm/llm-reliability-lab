"""`GET /api/v1/health` — service, database, and provider status."""

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession
from app.config import get_settings
from app.schemas.health import DatabaseHealth, HealthResponse, LLMProviderInfo

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health(db: DbSession) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        database = DatabaseHealth(status="ok")
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any DB error is "unhealthy"
        database = DatabaseHealth(status="error", error=str(exc))

    return HealthResponse(
        status="ok" if database.status == "ok" else "degraded",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        database=database,
        llm_provider=LLMProviderInfo(
            provider="ollama",
            base_url=settings.ollama_base_url,
            default_model=settings.default_model,
        ),
    )
