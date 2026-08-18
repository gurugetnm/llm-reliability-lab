"""`ContainsEvaluator` — partial credit for how many required
phrases/keywords appear in the actual output."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata


class ContainsConfig(BaseModel):
    required_terms: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Phrases/keywords the actual output should contain.",
    )
    case_sensitive: bool = Field(
        default=False, description="Match case-sensitively. Off by default."
    )
    threshold: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of required_terms that must match for passed=true.",
    )

    @field_validator("required_terms")
    @classmethod
    def _no_blank_terms(cls, value: list[str]) -> list[str]:
        cleaned = [term.strip() for term in value]
        if any(not term for term in cleaned):
            raise ValueError("required_terms cannot contain blank entries")
        return cleaned


@EvaluatorRegistry.register
class ContainsEvaluator(Evaluator):
    """Scores `matched_terms / len(required_terms)` — teaches partial
    scoring rather than a single pass/fail bit."""

    metadata = EvaluatorMetadata(
        name="contains",
        version="v1",
        description="Scores the fraction of configured required_terms found in the actual output.",
        score_range=(0.0, 1.0),
        higher_is_better=True,
    )
    config_model = ContainsConfig

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: ContainsConfig = self.config  # type: ignore[assignment]
        haystack = item.actual_text()
        haystack_cmp = haystack if config.case_sensitive else haystack.lower()

        matched: list[str] = []
        missing: list[str] = []
        for term in config.required_terms:
            needle = term if config.case_sensitive else term.lower()
            (matched if needle in haystack_cmp else missing).append(term)

        score = len(matched) / len(config.required_terms)
        passed = score >= config.threshold
        return EvaluationOutput(
            score=score,
            passed=passed,
            reason=f"Matched {len(matched)}/{len(config.required_terms)} required terms.",
            details={
                "required_terms": config.required_terms,
                "matched_terms": matched,
                "missing_terms": missing,
                "threshold": config.threshold,
            },
        )
