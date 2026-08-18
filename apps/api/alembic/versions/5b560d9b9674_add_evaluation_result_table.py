"""add evaluation result table

Revision ID: 5b560d9b9674
Revises: 7579bf025c55
Create Date: 2026-08-18 21:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5b560d9b9674"
down_revision: str | Sequence[str] | None = "7579bf025c55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evaluation_results",
        sa.Column("evaluation_run_id", sa.UUID(), nullable=False),
        sa.Column("run_item_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="evaluation_result_status",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluator", sa.String(length=140), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_item_id"], ["run_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_results_evaluation_run_id"),
        "evaluation_results",
        ["evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_results_run_item_id"),
        "evaluation_results",
        ["run_item_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_evaluation_results_run_item_id"), table_name="evaluation_results")
    op.drop_index(op.f("ix_evaluation_results_evaluation_run_id"), table_name="evaluation_results")
    op.drop_table("evaluation_results")
