"""`Experiment` — a reproducible LLM run configuration.

`ExperimentRun`/`RunItem` (the execution side) land in a follow-up
change. Structured columns hold everything a list/filter query needs
(model, dataset_id, timestamps); JSONB is used only where the shape is
genuinely variable (generation parameters, an optional JSON Schema).
See `docs/experiments.md` for the full architecture.
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

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.dataset import Dataset, DatasetItem
from app.models.enums import ExperimentRunStatus, RunItemErrorType, RunItemStatus


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_project_id_created_at", "project_id", "created_at"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # RESTRICT (the default): a dataset in use by an experiment can't be
    # deleted out from under it. DatasetService checks this up front and
    # raises a friendly error rather than surfacing the DB's own.
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    # {"temperature": 0.2, "max_tokens": 1000, "top_p": ..., "seed": ...}
    generation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # None disables structured output; otherwise {"schema": {...}}.
    structured_output_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="experiments")
    runs: Mapped[list[ExperimentRun]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Experiment(id={self.id!r}, name={self.name!r}, model={self.model!r})"


class ExperimentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_runs"
    __table_args__ = (
        CheckConstraint(
            "completed_items <= total_items", name="ck_experiment_runs_completed_le_total"
        ),
        Index("ix_experiment_runs_experiment_id_created_at", "experiment_id", "created_at"),
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ExperimentRunStatus] = mapped_column(
        Enum(ExperimentRunStatus, name="experiment_run_status", native_enum=False, length=32),
        nullable=False,
        default=ExperimentRunStatus.PENDING,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Snapshot of the experiment's config at run time — a later edit to
    # the experiment must never change the meaning of a past run.
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    generation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    experiment: Mapped[Experiment] = relationship(back_populates="runs")
    items: Mapped[list[RunItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"ExperimentRun(id={self.id!r}, status={self.status!r})"


class RunItem(UUIDPrimaryKeyMixin, Base):
    """Deliberately no `TimestampMixin` — `created_at`/`completed_at` below
    already capture an item's lifecycle; an `updated_at` would just track
    the same one status-flip `completed_at` already records.
    """

    __tablename__ = "run_items"
    __table_args__ = (Index("ix_run_items_run_id_status", "run_id", "status"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL rather than CASCADE/RESTRICT: a RunItem carries its own
    # copy of input/prompt/response, so it stays fully inspectable even
    # if the dataset item it was generated from is later removed.
    dataset_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RunItemStatus] = mapped_column(
        Enum(RunItemStatus, name="run_item_status", native_enum=False, length=32),
        nullable=False,
        default=RunItemStatus.PENDING,
    )
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_type: Mapped[RunItemErrorType | None] = mapped_column(
        Enum(RunItemErrorType, name="run_item_error_type", native_enum=False, length=32),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[ExperimentRun] = relationship(back_populates="items")
    dataset_item: Mapped[DatasetItem | None] = relationship()

    def __repr__(self) -> str:
        return f"RunItem(id={self.id!r}, run_id={self.run_id!r}, status={self.status!r})"
