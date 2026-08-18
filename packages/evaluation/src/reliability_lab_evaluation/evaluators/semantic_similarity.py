"""`SemanticSimilarityEvaluator` — cosine similarity between the expected
and actual output's embeddings.

    SemanticSimilarityEvaluator
            -> EmbeddingProvider
            -> Local embedding model

Depends only on the `EmbeddingProvider` abstraction — never on
`sentence-transformers` (or any other embedding library) directly, so
tests exercise it with a fake and it doesn't care what produces the
vectors.
"""

from __future__ import annotations

import asyncio
import math

from pydantic import BaseModel, Field

from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.embeddings.base import EmbeddingProvider
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata


class SemanticSimilarityConfig(BaseModel):
    threshold: float = Field(
        default=0.8, ge=-1.0, le=1.0, description="Cosine similarity at/above which passed=true."
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Embedding dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@EvaluatorRegistry.register
class SemanticSimilarityEvaluator(Evaluator):
    """Embeds `expected_output` and `actual_output` and scores their
    cosine similarity.

    One instance is constructed per `EvaluationRun` and reused across all
    of that run's items (see `app.evaluation.runner`), which is what
    makes the embedding cache below effective — Part 13 asks for at
    least a within-run cache so an expected_output shared by many items
    (or an actual_output repeated by a deterministic model) is only ever
    embedded once.
    """

    metadata = EvaluatorMetadata(
        name="semantic_similarity",
        version="v1",
        description="Scores cosine similarity between expected and actual output embeddings.",
        score_range=(0.0, 1.0),
        higher_is_better=True,
        requires_embedding_provider=True,
    )
    config_model = SemanticSimilarityConfig

    def __init__(
        self,
        config: dict[str, object],
        *,
        embedding_provider: EmbeddingProvider | None = None,
        llm_provider: object | None = None,
    ) -> None:
        super().__init__(config, embedding_provider=embedding_provider, llm_provider=llm_provider)
        assert embedding_provider is not None  # enforced by EvaluatorRegistry.create
        self._embedding_provider = embedding_provider
        self._cache: dict[str, list[float]] = {}
        self._cache_lock = asyncio.Lock()

    async def _embed_cached(self, texts: list[str]) -> list[list[float]]:
        """Embeds `texts`, reusing cached vectors and batching the rest
        into a single `embed_batch()` call (Part 46: prefer batching over
        embedding one text at a time)."""
        async with self._cache_lock:
            to_embed = [text for text in dict.fromkeys(texts) if text not in self._cache]
            if to_embed:
                vectors = await self._embedding_provider.embed_batch(to_embed)
                self._cache.update(zip(to_embed, vectors, strict=True))
            return [self._cache[text] for text in texts]

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: SemanticSimilarityConfig = self.config  # type: ignore[assignment]
        if item.expected_output is None:
            return EvaluationOutput(
                score=None,
                passed=None,
                reason="No expected_output on this dataset item — nothing to embed and compare.",
                details={},
            )

        expected_text = str(item.expected_output)
        actual_text = item.actual_text()
        expected_vector, actual_vector = await self._embed_cached([expected_text, actual_text])
        similarity = cosine_similarity(expected_vector, actual_vector)
        passed = similarity >= config.threshold

        return EvaluationOutput(
            score=similarity,
            passed=passed,
            reason=f"Cosine similarity {similarity:.4f} vs threshold {config.threshold:.4f}.",
            details={
                "similarity": similarity,
                "threshold": config.threshold,
                "embedding_model": getattr(
                    self._embedding_provider, "model_name", self._embedding_provider.name
                ),
                "embedding_dimensions": len(expected_vector),
            },
        )
