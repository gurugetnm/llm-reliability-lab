"""`sentence-transformers`-backed `EmbeddingProvider`.

The only file in this package that imports `sentence_transformers`, and
it does so lazily (inside `_model`, not at module import time) so that:

* importing `reliability_lab_evaluation` — including the evaluator
  registry, which imports every evaluator module up front — never
  requires `sentence-transformers` to be installed.
* unit tests (`SemanticSimilarityEvaluator` with a fake provider) never
  download a model.
* the real model is only loaded the first time it's actually needed,
  and loaded once, not per-request.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from reliability_lab_evaluation.embeddings.base import EmbeddingProvider

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

#: A small (~90MB), well-regarded general-purpose sentence embedding
#: model that runs comfortably on CPU — a reasonable default for a local
#: lab where nobody has necessarily provisioned a GPU.
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Embeds text locally via a `sentence-transformers` model.

    No paid/remote embedding API is used anywhere in this evaluator —
    everything runs against a model downloaded once to the local
    `sentence-transformers` cache.
    """

    name = "sentence_transformers"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: SentenceTransformer | None = None
        self._load_lock = asyncio.Lock()

    async def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:  # re-check: another task may have loaded it while we waited
                self._model = await asyncio.get_event_loop().run_in_executor(None, self._load_model)
            return self._model

    def _load_model(self) -> SentenceTransformer:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover — exercised only without the extra installed
            raise ImportError(
                "SentenceTransformerEmbeddingProvider requires the 'sentence-transformers' "
                "package. Install it with `pip install llm-reliability-lab-evaluation[embeddings]`."
            ) from exc
        return SentenceTransformer(self.model_name, device=self.device)

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = await self._get_model()
        # `.encode()` is synchronous and CPU-bound — run it off the event
        # loop so a large batch doesn't stall other concurrent evaluations
        # (or the FastAPI process) while it runs.
        vectors = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: model.encode(
                texts, batch_size=self.batch_size, convert_to_numpy=True, show_progress_bar=False
            ),
        )
        return [vector.tolist() for vector in vectors]
