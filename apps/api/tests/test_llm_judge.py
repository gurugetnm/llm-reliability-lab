"""Unit tests for LLMJudgeEvaluator, against FakeLLMProvider — no real
model call. Covers Part 41's required failure modes: invalid JSON,
malformed schema, and provider failure (timeout is a runner-level
concern, covered in test_evaluation_runner.py)."""

import pytest
from reliability_lab_evaluation import EvaluationInput, EvaluatorExecutionError, EvaluatorRegistry
from reliability_lab_llm import ProviderConnectionError, StructuredOutputError

from tests.fakes import FakeLLMProvider


def _input(expected: object = "A protocol") -> EvaluationInput:
    return EvaluationInput(
        input="What is TCP?",
        expected_output=expected,
        actual_output="TCP is a transport-layer protocol.",
        model="candidate-model",
        experiment_name="test-experiment",
        run_id="11111111-1111-1111-1111-111111111111",
    )


def _valid_judgment(score: float = 4, criteria: dict[str, float] | None = None) -> dict:
    return {
        "score": score,
        "passed": True,
        "reason": "Accurate and relevant.",
        "criteria": criteria or {"accuracy": 4, "relevance": 5, "completeness": 4},
    }


class TestLLMJudgeEvaluator:
    async def test_valid_structured_result_is_normalized(self) -> None:
        provider = FakeLLMProvider(structured_result=_valid_judgment(score=4))
        evaluator = EvaluatorRegistry.create(
            "llm_judge",
            {"judge_model": "qwen3", "score_scale": 5, "threshold": 0.7},
            llm_provider=provider,
        )
        result = await evaluator.evaluate(_input())
        assert result.score == pytest.approx(0.8)  # 4 / 5
        assert result.passed is True
        assert result.reason == "Accurate and relevant."
        assert result.details["judge_model"] == "qwen3"
        assert result.details["criteria"]["relevance"] == 5

    async def test_score_below_threshold_fails(self) -> None:
        provider = FakeLLMProvider(structured_result=_valid_judgment(score=2))
        evaluator = EvaluatorRegistry.create(
            "llm_judge",
            {"judge_model": "qwen3", "score_scale": 5, "threshold": 0.7},
            llm_provider=provider,
        )
        result = await evaluator.evaluate(_input())
        assert result.score == pytest.approx(0.4)
        assert result.passed is False

    async def test_captures_usage_and_latency(self) -> None:
        provider = FakeLLMProvider(
            structured_result=_valid_judgment(),
            structured_usage=(120, 40, 160),
            structured_latency_ms=88.0,
        )
        evaluator = EvaluatorRegistry.create(
            "llm_judge", {"judge_model": "qwen3"}, llm_provider=provider
        )
        result = await evaluator.evaluate(_input())
        assert result.details["usage"] == {
            "input_tokens": 120,
            "output_tokens": 40,
            "total_tokens": 160,
        }
        assert result.details["latency_ms"] == 88.0

    async def test_invalid_json_raises_evaluator_execution_error(self) -> None:
        provider = FakeLLMProvider(
            structured_error=StructuredOutputError("bad json", raw_text="not json")
        )
        evaluator = EvaluatorRegistry.create(
            "llm_judge", {"judge_model": "qwen3"}, llm_provider=provider
        )
        with pytest.raises(EvaluatorExecutionError) as exc_info:
            await evaluator.evaluate(_input())
        assert exc_info.value.details["raw_response"] == "not json"

    async def test_malformed_schema_raises_evaluator_execution_error(self) -> None:
        # Well-formed JSON, but missing the required "criteria" key —
        # FakeLLMProvider doesn't validate against the schema itself, so
        # this exercises the evaluator's own jsonschema.validate() check.
        provider = FakeLLMProvider(structured_result={"score": 4, "passed": True, "reason": "ok"})
        evaluator = EvaluatorRegistry.create(
            "llm_judge", {"judge_model": "qwen3"}, llm_provider=provider
        )
        with pytest.raises(EvaluatorExecutionError, match="did not match the expected schema"):
            await evaluator.evaluate(_input())

    async def test_provider_failure_raises_evaluator_execution_error(self) -> None:
        provider = FakeLLMProvider(structured_error=ProviderConnectionError("unreachable"))
        evaluator = EvaluatorRegistry.create(
            "llm_judge", {"judge_model": "qwen3"}, llm_provider=provider
        )
        with pytest.raises(EvaluatorExecutionError, match="Judge model call failed"):
            await evaluator.evaluate(_input())

    async def test_missing_expected_output_still_judges(self) -> None:
        # Unlike exact_match/contains, the judge can grade a candidate
        # answer "on its own merits" without a reference answer.
        provider = FakeLLMProvider(structured_result=_valid_judgment())
        evaluator = EvaluatorRegistry.create(
            "llm_judge", {"judge_model": "qwen3"}, llm_provider=provider
        )
        result = await evaluator.evaluate(_input(expected=None))
        assert result.score is not None

    async def test_default_criteria_used_when_not_configured(self) -> None:
        evaluator = EvaluatorRegistry.create(
            "llm_judge",
            {"judge_model": "qwen3"},
            llm_provider=FakeLLMProvider(structured_result=_valid_judgment()),
        )
        assert evaluator.config.criteria == ["accuracy", "relevance", "completeness"]  # type: ignore[attr-defined]

    async def test_duplicate_criteria_rejected(self) -> None:
        from reliability_lab_evaluation import EvaluationConfigError

        with pytest.raises(EvaluationConfigError):
            EvaluatorRegistry.create(
                "llm_judge",
                {"judge_model": "qwen3", "criteria": ["accuracy", "accuracy"]},
                llm_provider=FakeLLMProvider(),
            )
