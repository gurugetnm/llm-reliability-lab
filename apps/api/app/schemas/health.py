"""Response schema for `GET /api/v1/health`."""

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    status: str
    error: str | None = None


class LLMProviderInfo(BaseModel):
    provider: str
    base_url: str
    default_model: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: DatabaseHealth
    llm_provider: LLMProviderInfo
