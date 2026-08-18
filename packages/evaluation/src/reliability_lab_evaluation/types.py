"""Provider-independent input/output types for the evaluation engine.

`EvaluationInput` is built entirely by the caller (the evaluation
runner in `apps/api`, which has the database) — evaluators never query a
database themselves. That's what keeps them deterministic and testable
with plain Python values, the same way `reliability_lab_llm`'s types keep
`LLMProvider` implementations decoupled from FastAPI/SQLAlchemy.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvaluationInput(BaseModel):
    """Everything an evaluator needs to score one `RunItem`, with no
    access to the database or any other RunItem."""

    input: Any = Field(description="The dataset item's input, as given to the experiment.")
    expected_output: Any | None = Field(
        default=None, description="The dataset item's expected output, if any."
    )
    actual_output: str | None = Field(
        default=None, description="The RunItem's plain-text response, if any."
    )
    actual_structured_output: dict[str, Any] | None = Field(
        default=None, description="The RunItem's structured-output response, if any."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="The dataset item's metadata, if any."
    )
    model: str = Field(description="The model that produced actual_output.")
    experiment_name: str = Field(description="Name of the experiment the RunItem belongs to.")
    run_id: str = Field(description="id of the ExperimentRun the RunItem belongs to.")

    def actual_text(self) -> str:
        """The text an evaluator should compare against — the plain
        response if there is one, else the structured output rendered as
        JSON, else empty. Centralized so every evaluator treats a
        structured-output RunItem the same way."""
        if self.actual_output:
            return self.actual_output
        if self.actual_structured_output is not None:
            import json

            return json.dumps(self.actual_structured_output, sort_keys=True)
        return ""


class EvaluationOutput(BaseModel):
    """The result of successfully evaluating one item.

    `score`/`passed` are both optional — some evaluators can't naturally
    produce one or the other (Part 7 is explicit: never fake a score to
    fill this in). Evaluators that fail to produce a result at all raise
    `EvaluatorExecutionError` instead of returning an `EvaluationOutput`
    with placeholder values.
    """

    score: float | None = None
    passed: bool | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluatorMetadata(BaseModel):
    """Self-describing metadata for one evaluator, returned by
    `GET /api/v1/evaluators` so the frontend can discover evaluator
    capabilities instead of hard-coding them (Part 37)."""

    name: str
    version: str
    description: str
    score_range: tuple[float, float] | None = None
    higher_is_better: bool = True
    supports_pass_fail: bool = True
    config_schema: dict[str, Any] = Field(default_factory=dict)
    requires_embedding_provider: bool = False
    requires_llm_provider: bool = False
