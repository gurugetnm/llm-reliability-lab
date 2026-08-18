"""`LLMJudgeEvaluator` — uses an LLM to grade a candidate answer.

    LLMJudgeEvaluator
            -> LLMProvider
            -> OllamaProvider
            -> Ollama

Never calls Ollama (or any provider) directly — it only knows about
`LLMProvider.generate_structured()`, exactly like `GenerationService`
does for the experiment side. Part 40 requires the judge model to be
kept isolated from the candidate model being evaluated; this evaluator
enforces that by construction — `config.judge_model` is always a
separate, explicit field, never inherited from the experiment/RunItem
being judged.
"""

from __future__ import annotations

import time
from typing import Any

import jsonschema
from pydantic import BaseModel, Field, field_validator
from reliability_lab_llm import GenerationOptions, LLMProvider
from reliability_lab_llm.exceptions import ProviderError, StructuredOutputError

from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.evaluators.judge_prompt import (
    build_judge_messages,
    build_response_schema,
)
from reliability_lab_evaluation.exceptions import EvaluatorExecutionError
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata

DEFAULT_CRITERIA = ["accuracy", "relevance", "completeness"]


class LLMJudgeConfig(BaseModel):
    judge_model: str = Field(
        min_length=1, description="Model used to judge — kept separate from the candidate model."
    )
    score_scale: int = Field(
        default=5, ge=2, le=10, description="Judge scores on a 0..score_scale scale."
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Normalized score (score/score_scale) at/above which passed=true.",
    )
    criteria: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CRITERIA), min_length=1, max_length=10
    )
    judge_system_prompt: str | None = Field(default=None, max_length=5_000)
    judge_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    @field_validator("criteria")
    @classmethod
    def _no_blank_criteria(cls, value: list[str]) -> list[str]:
        cleaned = [c.strip() for c in value]
        if any(not c for c in cleaned):
            raise ValueError("criteria cannot contain blank entries")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("criteria must be unique")
        return cleaned


@EvaluatorRegistry.register
class LLMJudgeEvaluator(Evaluator):
    """Grades a candidate answer with a judge model via `LLMProvider`,
    validating its structured output against a JSON Schema before
    trusting any of it."""

    metadata = EvaluatorMetadata(
        name="llm_judge",
        version="v1",
        description=(
            "Uses an LLM (via LLMProvider) to grade the candidate answer against "
            "configurable criteria."
        ),
        score_range=(0.0, 1.0),
        higher_is_better=True,
        requires_llm_provider=True,
    )
    config_model = LLMJudgeConfig

    def __init__(
        self,
        config: dict[str, Any],
        *,
        embedding_provider: object | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        super().__init__(config, embedding_provider=embedding_provider, llm_provider=llm_provider)
        assert llm_provider is not None  # enforced by EvaluatorRegistry.create
        self._llm_provider = llm_provider
        judge_config: LLMJudgeConfig = self.config  # type: ignore[assignment]
        self._schema = build_response_schema(judge_config.criteria, judge_config.score_scale)

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: LLMJudgeConfig = self.config  # type: ignore[assignment]
        messages = build_judge_messages(
            item,
            criteria=config.criteria,
            score_scale=config.score_scale,
            system_prompt=config.judge_system_prompt,
        )

        started_at = time.perf_counter()
        try:
            result = await self._llm_provider.generate_structured(
                messages,
                model=config.judge_model,
                schema=self._schema,
                options=GenerationOptions(temperature=config.judge_temperature),
            )
        except StructuredOutputError as exc:
            raise EvaluatorExecutionError(
                f"Judge model '{config.judge_model}' returned invalid structured output: {exc}",
                details={"judge_model": config.judge_model, "raw_response": exc.raw_text[:4_000]},
            ) from exc
        except ProviderError as exc:
            raise EvaluatorExecutionError(
                f"Judge model call failed: {exc}", details={"judge_model": config.judge_model}
            ) from exc
        latency_ms = (
            result.latency_ms
            if result.latency_ms is not None
            else (time.perf_counter() - started_at) * 1000
        )

        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        try:
            jsonschema.validate(data, self._schema)
        except jsonschema.ValidationError as exc:
            raise EvaluatorExecutionError(
                f"Judge model '{config.judge_model}' response did not match the expected "
                f"schema: {exc.message}",
                details={"judge_model": config.judge_model, "raw_response": data},
            ) from exc

        raw_score = float(data["score"])
        normalized_score = raw_score / config.score_scale
        passed = normalized_score >= config.threshold

        return EvaluationOutput(
            score=normalized_score,
            passed=bool(passed),
            reason=data.get("reason"),
            details={
                "raw_score": raw_score,
                "score_scale": config.score_scale,
                "threshold": config.threshold,
                "criteria": data.get("criteria", {}),
                "judge_model": config.judge_model,
                "judge_provider": result.provider,
                "usage": {
                    "input_tokens": result.prompt_tokens,
                    "output_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                },
                "latency_ms": latency_ms,
            },
        )
