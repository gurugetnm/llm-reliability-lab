"""Unit tests for ExactMatchEvaluator and ContainsEvaluator — deterministic,
no database, no provider of any kind.
"""

import pytest
from reliability_lab_evaluation import EvaluationConfigError, EvaluationInput, EvaluatorRegistry


def _input(expected: object, actual: str | None, **overrides: object) -> EvaluationInput:
    fields: dict[str, object] = {
        "input": "What is the capital of France?",
        "expected_output": expected,
        "actual_output": actual,
        "model": "test-model",
        "experiment_name": "test-experiment",
        "run_id": "11111111-1111-1111-1111-111111111111",
    }
    fields.update(overrides)
    return EvaluationInput(**fields)


class TestExactMatchEvaluator:
    async def test_exact_match_scores_one(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        result = await evaluator.evaluate(_input("Paris", "Paris"))
        assert result.score == 1.0
        assert result.passed is True

    async def test_mismatch_scores_zero(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        result = await evaluator.evaluate(_input("Paris", "London"))
        assert result.score == 0.0
        assert result.passed is False

    async def test_case_insensitive_by_default(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        result = await evaluator.evaluate(_input("Paris", "PARIS"))
        assert result.score == 1.0

    async def test_case_sensitive_configuration(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {"case_sensitive": True})
        result = await evaluator.evaluate(_input("Paris", "PARIS"))
        assert result.score == 0.0

    async def test_whitespace_normalized_by_default(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        result = await evaluator.evaluate(_input("Paris", "  Paris\r\n"))
        assert result.score == 1.0

    async def test_whitespace_significant_when_disabled(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {"ignore_whitespace": False})
        result = await evaluator.evaluate(_input("Paris", "  Paris"))
        assert result.score == 0.0

    async def test_missing_expected_output_yields_null_score(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        result = await evaluator.evaluate(_input(None, "Paris"))
        assert result.score is None
        assert result.passed is None

    async def test_uses_structured_output_when_no_plain_response(self) -> None:
        evaluator = EvaluatorRegistry.create("exact_match", {})
        item = _input('{"city": "Paris"}', None, actual_structured_output={"city": "Paris"})
        result = await evaluator.evaluate(item)
        assert result.score == 1.0

    async def test_invalid_config_raises(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create("exact_match", {"case_sensitive": "not-a-bool"})


class TestContainsEvaluator:
    async def test_partial_score(self) -> None:
        evaluator = EvaluatorRegistry.create(
            "contains",
            {"required_terms": ["three-way handshake", "SYN", "ACK"], "threshold": 0.66},
        )
        result = await evaluator.evaluate(
            _input(
                "TCP uses a three-way handshake.",
                "TCP establishes connections using a three-way handshake.",
            )
        )
        assert result.score == pytest.approx(1 / 3)
        assert result.passed is False
        assert result.details["matched_terms"] == ["three-way handshake"]
        assert result.details["missing_terms"] == ["SYN", "ACK"]

    async def test_all_terms_matched(self) -> None:
        evaluator = EvaluatorRegistry.create("contains", {"required_terms": ["SYN", "ACK"]})
        result = await evaluator.evaluate(_input("x", "SYN then ACK completes the handshake"))
        assert result.score == 1.0
        assert result.passed is True

    async def test_case_insensitive_by_default(self) -> None:
        evaluator = EvaluatorRegistry.create("contains", {"required_terms": ["SYN"]})
        result = await evaluator.evaluate(_input("x", "the syn packet"))
        assert result.score == 1.0

    async def test_threshold_boundary(self) -> None:
        evaluator = EvaluatorRegistry.create(
            "contains", {"required_terms": ["a", "b", "c"], "threshold": 0.5}
        )
        result = await evaluator.evaluate(_input("x", "a b"))
        assert result.score == pytest.approx(2 / 3)
        assert result.passed is True

    async def test_empty_required_terms_rejected(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create("contains", {"required_terms": []})

    async def test_blank_term_rejected(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create("contains", {"required_terms": ["ok", "  "]})


class TestEvaluatorRegistry:
    def test_names_lists_all_built_ins(self) -> None:
        assert set(EvaluatorRegistry.names()) == {
            "exact_match",
            "contains",
            "semantic_similarity",
            "llm_judge",
        }

    def test_unknown_evaluator_raises(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.get("not_a_real_evaluator")

    def test_list_metadata_includes_config_schema(self) -> None:
        metadata = {m.name: m for m in EvaluatorRegistry.list_metadata()}
        assert "required_terms" in metadata["contains"].config_schema["properties"]
        assert metadata["semantic_similarity"].requires_embedding_provider is True
        assert metadata["llm_judge"].requires_llm_provider is True

    def test_validate_config_without_instantiating(self) -> None:
        validated = EvaluatorRegistry.validate_config("exact_match", {"case_sensitive": True})
        assert validated.case_sensitive is True  # type: ignore[attr-defined]

    def test_semantic_similarity_requires_embedding_provider(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create("semantic_similarity", {})

    def test_llm_judge_requires_llm_provider(self) -> None:
        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create("llm_judge", {"judge_model": "qwen3"})
