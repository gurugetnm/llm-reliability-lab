"""Unit tests for SemanticSimilarityEvaluator, against FakeEmbeddingProvider
(`tests/fakes.py`) — no sentence-transformers model download."""

import pytest
from reliability_lab_evaluation import EvaluationInput, EvaluatorRegistry
from reliability_lab_evaluation.evaluators.semantic_similarity import cosine_similarity

from tests.fakes import FakeEmbeddingProvider


def _input(expected: object, actual: str | None) -> EvaluationInput:
    return EvaluationInput(
        input="q",
        expected_output=expected,
        actual_output=actual,
        model="test-model",
        experiment_name="test-experiment",
        run_id="11111111-1111-1111-1111-111111111111",
    )


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self) -> None:
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_score_negative_one(self) -> None:
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_is_zero_not_nan(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity([1.0], [1.0, 0.0])


class TestSemanticSimilarityEvaluator:
    async def test_identical_text_scores_near_one(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create(
            "semantic_similarity", {"threshold": 0.8}, embedding_provider=provider
        )
        result = await evaluator.evaluate(_input("hello world", "hello world"))
        assert result.score == pytest.approx(1.0)
        assert result.passed is True
        assert result.details["threshold"] == 0.8

    async def test_different_text_below_threshold_fails(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create(
            "semantic_similarity", {"threshold": 0.999}, embedding_provider=provider
        )
        result = await evaluator.evaluate(_input("hello world", "completely different text"))
        assert result.passed is False

    async def test_missing_expected_output_yields_null_score(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create("semantic_similarity", {}, embedding_provider=provider)
        result = await evaluator.evaluate(_input(None, "anything"))
        assert result.score is None
        assert provider.batch_calls == []  # never embeds when there's nothing to compare

    async def test_caches_repeated_text_within_one_evaluator_instance(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create("semantic_similarity", {}, embedding_provider=provider)
        await evaluator.evaluate(_input("same expected", "response A"))
        await evaluator.evaluate(_input("same expected", "response B"))

        # "same expected" is embedded once, not twice, across both calls.
        all_embedded_texts = [text for batch in provider.batch_calls for text in batch]
        assert all_embedded_texts.count("same expected") == 1
        assert all_embedded_texts.count("response A") == 1
        assert all_embedded_texts.count("response B") == 1

    async def test_batches_uncached_texts_in_one_call(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create("semantic_similarity", {}, embedding_provider=provider)
        await evaluator.evaluate(_input("expected text", "actual text"))
        assert provider.batch_calls == [["expected text", "actual text"]]

    async def test_details_include_embedding_model_name(self) -> None:
        provider = FakeEmbeddingProvider()
        evaluator = EvaluatorRegistry.create("semantic_similarity", {}, embedding_provider=provider)
        result = await evaluator.evaluate(_input("x", "x"))
        assert result.details["embedding_model"] == "fake"
        assert result.details["embedding_dimensions"] == FakeEmbeddingProvider.dimensions
