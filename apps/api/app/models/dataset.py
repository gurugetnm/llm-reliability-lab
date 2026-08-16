"""`Dataset` and `DatasetItem` — the input side of an experiment.

`DatasetItem.input` / `expected_output` are JSONB rather than plain text
so an item can hold a string, a structured object (e.g. RAG context +
question), or omit `expected_output` entirely — Phase 4's evaluators
decide what shape they need, not this schema. See `docs/experiments.md`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.experiment import Experiment


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Bumped by DatasetService on bulk import — a cheap signal that "the
    # items backing this dataset changed" without diffing item history.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    items: Mapped[list[DatasetItem]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )
    experiments: Mapped[list[Experiment]] = relationship(back_populates="dataset")

    def __repr__(self) -> str:
        return f"Dataset(id={self.id!r}, name={self.name!r}, version={self.version})"


class DatasetItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_items"
    __table_args__ = (
        # Keeps item ordering stable and unambiguous for pagination —
        # DatasetService assigns `position` sequentially on insert.
        UniqueConstraint("dataset_id", "position", name="uq_dataset_items_dataset_id_position"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input: Mapped[Any] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    # Mapped to the "metadata" column under a non-reserved Python name —
    # `metadata` is reserved on declarative models (it's SQLAlchemy's own
    # `Base.metadata`).
    item_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return (
            f"DatasetItem(id={self.id!r}, dataset_id={self.dataset_id!r}, position={self.position})"
        )
