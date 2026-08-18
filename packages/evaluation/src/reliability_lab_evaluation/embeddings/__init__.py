"""Embedding provider abstraction, used by `SemanticSimilarityEvaluator`
and reusable by future phases (Phase 5's RAG retrieval)."""

from reliability_lab_evaluation.embeddings.base import EmbeddingProvider

__all__ = ["EmbeddingProvider"]
