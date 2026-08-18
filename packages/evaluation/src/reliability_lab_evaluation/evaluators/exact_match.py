"""`ExactMatchEvaluator` — the simplest possible evaluator, and the one
every future evaluator's tests get compared against for behavior."""

from __future__ import annotations

from pydantic import BaseModel, Field

from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata


class ExactMatchConfig(BaseModel):
    case_sensitive: bool = Field(
        default=False, description="Compare case-sensitively. Off by default."
    )
    ignore_whitespace: bool = Field(
        default=True,
        description="Trim leading/trailing whitespace and normalize line endings before comparing.",
    )


def _normalize(text: str, config: ExactMatchConfig) -> str:
    if config.ignore_whitespace:
        # Normalize CRLF/CR to LF first so a text's line-ending style
        # never causes a false mismatch, then trim. Deliberately not
        # collapsing internal whitespace — that's "aggressively modify
        # text" territory (Part 8 warns against it) and belongs to
        # ContainsEvaluator's substring matching instead, if anywhere.
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not config.case_sensitive:
        text = text.lower()
    return text


@EvaluatorRegistry.register
class ExactMatchEvaluator(Evaluator):
    """Compares `expected_output` and `actual_output` for equality after
    safe, configurable normalization."""

    metadata = EvaluatorMetadata(
        name="exact_match",
        version="v1",
        description=(
            "Scores 1.0 if the (normalized) actual output exactly equals the expected "
            "output, else 0.0."
        ),
        score_range=(0.0, 1.0),
        higher_is_better=True,
    )
    config_model = ExactMatchConfig

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: ExactMatchConfig = self.config  # type: ignore[assignment]
        if item.expected_output is None:
            return EvaluationOutput(
                score=None,
                passed=None,
                reason="No expected_output on this dataset item — nothing to compare against.",
                details={},
            )

        expected = _normalize(str(item.expected_output), config)
        actual = _normalize(item.actual_text(), config)
        matched = expected == actual
        return EvaluationOutput(
            score=1.0 if matched else 0.0,
            passed=matched,
            reason=(
                "Exact match." if matched else "Output did not exactly match the expected output."
            ),
            details={
                "expected": expected,
                "actual": actual,
                "case_sensitive": config.case_sensitive,
                "ignore_whitespace": config.ignore_whitespace,
            },
        )
