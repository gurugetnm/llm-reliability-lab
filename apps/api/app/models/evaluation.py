"""`EvaluationRun` and `EvaluationResult` — the evaluation layer.

    ExperimentRun -> EvaluationRun -> EvaluationResult

An `EvaluationRun` evaluates one already-completed `ExperimentRun` under
one evaluator configuration; each of its `EvaluationResult`s scores one
`RunItem`. Deliberately a separate pair of tables rather than columns
bolted onto `RunItem`/`ExperimentRun` — the same `RunItem` can be
evaluated multiple times (different evaluators, or the same evaluator
re-run after a threshold change) without re-running generation, and
`RunItem` stays purely a generation record. See `docs/evaluation.md`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import EvaluationResultStatus, EvaluationRunStatus


class EvaluationRun(UUIDPrimaryKeyMixin, Base):
    """Deliberately no `TimestampMixin` — like `ExperimentRun`, its own
    `created_at`/`started_at`/`completed_at` already capture its
    lifecycle; there's no separate "config was edited" event an
    `updated_at` would need to track (an EvaluationRun's configuration is
    immutable once created — Part 35's reproducibility requirement)."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "completed_items <= total_items", name="ck_evaluation_runs_completed_le_total"
        ),
        Index("ix_evaluation_runs_run_id_created_at", "run_id", "created_at"),
    )

    # CASCADE: an EvaluationRun only makes sense relative to the
    # ExperimentRun (and its RunItems) it evaluated — if that
    # ExperimentRun is deleted, its RunItems cascade away too, so any
    # EvaluationResult referencing them would be meaningless.
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[EvaluationRunStatus] = mapped_column(
        Enum(EvaluationRunStatus, name="evaluation_run_status", native_enum=False, length=32),
        nullable=False,
        default=EvaluationRunStatus.PENDING,
        index=True,
    )
    evaluator_type: Mapped[str] = mapped_column(String(100), nullable=False)
    #: e.g. "v1" — `EvaluatorRegistry`'s `metadata.version` at the time
    #: this run was created, snapshotted so a later evaluator code change
    #: never silently changes the meaning of a past run (Part 36).
    evaluator_version: Mapped[str] = mapped_column(String(20), nullable=False)
    #: The evaluator's full validated configuration (thresholds, judge
    #: model, criteria, embedding model, ...) — Part 35's reproducibility
    #: requirement: everything needed to re-run this exact evaluation.
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(nullable=False, default=False)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="evaluation_run", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return (
            f"EvaluationRun(id={self.id!r}, run_id={self.run_id!r}, "
            f"evaluator_type={self.evaluator_type!r}, status={self.status!r})"
        )


class EvaluationResult(UUIDPrimaryKeyMixin, Base):
    """Deliberately no `TimestampMixin` — one `created_at` (set once,
    when the item finishes evaluating) is all an immutable scoring
    record needs."""

    __tablename__ = "evaluation_results"
    __table_args__ = (
        Index("ix_evaluation_results_evaluation_run_id_status", "evaluation_run_id", "status"),
    )

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("run_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[EvaluationResultStatus] = mapped_column(
        Enum(EvaluationResultStatus, name="evaluation_result_status", native_enum=False, length=32),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Evaluator-specific structured metadata — similarity + threshold,
    #: judge per-criterion scores + usage, contains' matched/missing
    #: terms, ... Never forced into one shared shape (Part 3).
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    #: "<evaluator_type>:<evaluator_version>", e.g. "semantic_similarity:v1"
    #: — readable on this row alone, without joining back to EvaluationRun.
    evaluator: Mapped[str] = mapped_column(String(140), nullable=False)
    #: Set only when status=failed — the evaluator raised (a judge
    #: returned invalid output, an embedding call failed, ...). Partial
    #: failure handling (Part 22) needs this to survive independently of
    #: the (then-null) score/passed/reason.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="results")

    def __repr__(self) -> str:
        return (
            f"EvaluationResult(id={self.id!r}, evaluation_run_id={self.evaluation_run_id!r}, "
            f"status={self.status!r}, score={self.score!r})"
        )
