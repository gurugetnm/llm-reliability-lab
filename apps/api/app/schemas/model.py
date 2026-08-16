"""Response schema for `GET /api/v1/models/health`.

`GET /api/v1/models` itself returns `list[ModelSummary]` directly —
`ModelSummary` (from `reliability_lab_llm`) is already a provider-agnostic,
API-appropriate shape, so there's no separate api-layer schema to keep in
sync with it.
"""

from pydantic import BaseModel


class ModelsHealthResponse(BaseModel):
    available: bool
    provider: str
    model_count: int | None = None
    latency_ms: float | None = None
    error: str | None = None
