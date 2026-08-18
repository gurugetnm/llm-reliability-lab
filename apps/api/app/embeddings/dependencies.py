"""FastAPI wiring for `EmbeddingProvider` — the `app.llm.dependencies`
pattern applied to embeddings.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from reliability_lab_evaluation import EmbeddingProvider
from reliability_lab_evaluation.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)

from app.config import get_settings


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured `EmbeddingProvider` singleton.

    Cached so the underlying model is loaded (lazily, on first use) once
    per process rather than once per request. Constructing this is cheap
    — it doesn't load the model or import `sentence_transformers` itself;
    that only happens the first time `embed`/`embed_batch` is actually
    called (see `SentenceTransformerEmbeddingProvider`).
    """
    settings = get_settings()
    return SentenceTransformerEmbeddingProvider(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )


EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
