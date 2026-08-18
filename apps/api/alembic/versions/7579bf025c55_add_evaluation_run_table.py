"""add evaluation run table

Revision ID: 7579bf025c55
Revises: 4b4a44314e0f
Create Date: 2026-08-18 21:10:17.460108

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7579bf025c55"
down_revision: str | Sequence[str] | None = "4b4a44314e0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evaluation_runs",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "COMPLETED_WITH_ERRORS",
                "FAILED",
                "CANCELLED",
                name="evaluation_run_status",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("evaluator_type", sa.String(length=100), nullable=False),
        sa.Column("evaluator_version", sa.String(length=20), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("completed_items", sa.Integer(), nullable=False),
        sa.Column("successful_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "completed_items <= total_items", name="ck_evaluation_runs_completed_le_total"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_runs_run_id"), "evaluation_runs", ["run_id"], unique=False)
    op.create_index(op.f("ix_evaluation_runs_status"), "evaluation_runs", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_evaluation_runs_status"), table_name="evaluation_runs")
    op.drop_index(op.f("ix_evaluation_runs_run_id"), table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
