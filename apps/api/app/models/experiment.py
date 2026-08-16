"""`Experiment` — a reproducible LLM run configuration.

`ExperimentRun`/`RunItem` (the execution side) land in a follow-up
change. Structured columns hold everything a list/filter query needs
(model, dataset_id, timestamps); JSONB is used only where the shape is
genuinely variable (generation parameters, an optional JSON Schema).
See `docs/experiments.md` for the full architecture.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.dataset import Dataset


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

    def __repr__(self) -> str:
        return f"Experiment(id={self.id!r}, name={self.name!r}, model={self.model!r})"
