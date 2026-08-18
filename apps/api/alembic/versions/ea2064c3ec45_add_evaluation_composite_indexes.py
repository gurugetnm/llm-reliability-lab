"""add evaluation composite indexes

Revision ID: ea2064c3ec45
Revises: 5b560d9b9674
Create Date: 2026-08-18 21:20:00.000000

Adds the composite indexes the evaluation API's actual query patterns
need, on top of the single-column indexes the previous two migrations
already created:

* `evaluation_runs(run_id, created_at)` — "list an ExperimentRun's
  evaluations, newest first" (GET /api/v1/evaluations?run_id=...).
* `evaluation_results(evaluation_run_id, status)` — "an EvaluationRun's
  results by outcome", used both by the paginated results endpoint and
  by aggregate metric calculation (only succeeded results are scored).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea2064c3ec45"
down_revision: str | Sequence[str] | None = "5b560d9b9674"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_evaluation_runs_run_id_created_at",
        "evaluation_runs",
        ["run_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_evaluation_results_evaluation_run_id_status",
        "evaluation_results",
        ["evaluation_run_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_evaluation_results_evaluation_run_id_status", table_name="evaluation_results")
    op.drop_index("ix_evaluation_runs_run_id_created_at", table_name="evaluation_runs")
