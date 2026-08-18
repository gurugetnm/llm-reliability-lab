"""Request/response schemas for `/api/v1/evaluators` and
`/api/v1/evaluations`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.concurrency import DEFAULT_CONCURRENCY, MAX_CONCURRENCY
from app.models.enums import EvaluationResultStatus, EvaluationRunStatus


class EvaluatorInfo(BaseModel):
    """One entry in `GET /api/v1/evaluators` — lets the frontend
    discover evaluator capabilities and render a configuration form
    from `config_schema` instead of hard-coding them (Part 37)."""

    name: str
    version: str
    description: str
    score_range: tuple[float, float] | None
    higher_is_better: bool
    supports_pass_fail: bool
    config_schema: dict[str, Any]
    requires_embedding_provider: bool
    requires_llm_provider: bool


class EvaluationRunCreate(BaseModel):
    run_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    evaluator_type: str = Field(min_length=1, max_length=100)
    configuration: dict[str, Any] = Field(default_factory=dict)
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=MAX_CONCURRENCY)


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    name: str
    status: EvaluationRunStatus
    evaluator_type: str
    evaluator_version: str
    configuration: dict[str, Any]
    total_items: int
    completed_items: int
    successful_items: int
    failed_items: int
    cancel_requested: bool
    concurrency: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    run_item_id: uuid.UUID
    status: EvaluationResultStatus
    metric_name: str
    score: float | None
    passed: bool | None
    reason: str | None
    details: dict[str, Any]
    evaluator: str
    error_message: str | None
    created_at: datetime


class DistributionBucketRead(BaseModel):
    range_start: float
    range_end: float
    item_count: int


class EvaluationMetricsRead(BaseModel):
    """Aggregate metrics for one `EvaluationRun` — Part 26/27."""

    evaluation_run_id: uuid.UUID
    total: int
    evaluated: int
    failed: int
    passed: int | None
    pass_rate: float | None
    mean_score: float | None
    median_score: float | None
    min_score: float | None
    max_score: float | None
    distribution: list[DistributionBucketRead] | None


class RegressionRead(BaseModel):
    """Part 33/34 — a plain engineering comparison, never presented as
    statistical significance."""

    baseline_score: float
    candidate_score: float
    difference: float
    relative_difference: float | None
    threshold: float
    higher_is_better: bool
    regression_detected: bool


class EvaluationItemComparisonRead(BaseModel):
    """One dataset item's baseline vs. candidate score — Part 32's
    per-item comparison view."""

    dataset_item_id: uuid.UUID | None
    baseline_result_id: uuid.UUID | None
    candidate_result_id: uuid.UUID | None
    baseline_score: float | None
    candidate_score: float | None
    difference: float | None


class EvaluationComparisonRead(BaseModel):
    baseline: EvaluationRunRead
    candidate: EvaluationRunRead
    baseline_metrics: EvaluationMetricsRead
    candidate_metrics: EvaluationMetricsRead
    regression: RegressionRead | None
    items: list[EvaluationItemComparisonRead]
