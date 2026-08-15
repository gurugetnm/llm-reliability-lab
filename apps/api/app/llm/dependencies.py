"""FastAPI wiring for the LLM provider abstraction.

Nothing here is Ollama-specific except this one factory function — swap
it out (or make it settings-driven) to support additional providers
without touching any route or service that depends on `LLMProvider`.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from reliability_lab_llm import LLMProvider, OllamaProvider

from app.config import get_settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Return the configured `LLMProvider` singleton.

    Cached so the underlying HTTP client (and its connection pool) is
    reused across requests instead of being recreated per call.
    """
    settings = get_settings()
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        default_model=settings.default_model,
    )


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
