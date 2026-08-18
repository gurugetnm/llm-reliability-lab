"""The `EmbeddingProvider` interface every embedding backend implements.

Mirrors `reliability_lab_llm.LLMProvider`'s shape on purpose:
`SemanticSimilarityEvaluator` (and, later, Phase 5's retrieval code)
should depend on this abstraction, never on a concrete library
(`sentence-transformers`, a future API-based provider, ...).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Provider-agnostic interface for turning text into vectors."""

    #: Short, stable identifier used in result metadata, e.g.
    #: "sentence_transformers".
    name: str

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single piece of text."""
        raise NotImplementedError

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one call.

        Implementations should prefer batching the underlying model call
        over looping `embed()` — this is the method the evaluation
        runner and evaluators actually call (Part 46)."""
        raise NotImplementedError
