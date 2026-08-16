"""`Dataset` — the input side of an experiment.

`DatasetItem` (the rows inside a dataset) lands in a follow-up change —
see `docs/experiments.md` for why the two are split.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


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

    def __repr__(self) -> str:
        return f"Dataset(id={self.id!r}, name={self.name!r}, version={self.version})"
