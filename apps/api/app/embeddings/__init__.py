"""FastAPI-specific wiring for the `EmbeddingProvider` abstraction.

Mirrors `app.llm.dependencies`'s shape: nothing outside this module
constructs a concrete `EmbeddingProvider` — swap `get_embedding_provider`
to support an additional local model (or a future provider) without
touching `SemanticSimilarityEvaluator` or any route.
"""
