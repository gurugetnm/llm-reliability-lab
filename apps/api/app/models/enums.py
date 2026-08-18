"""Shared enums for the experiment engine's persistence layer.

Plain `str` enums so they serialize naturally through Pydantic/JSON, and
are stored as `VARCHAR` + `CHECK` constraint (see `app/models/experiment.py`)
rather than a native Postgres `ENUM` type — adding a value to a native
enum requires an `ALTER TYPE ... ADD VALUE` that can't run inside a
transaction, which makes migrations awkward. A `CHECK` constraint is a
one-line migration to change.
"""

from enum import StrEnum


class ExperimentRunStatus(StrEnum):
    """Lifecycle of an `ExperimentRun`.

    Valid transitions (enforced by `app.experiments.lifecycle`):

        pending -> running -> completed
        pending -> running -> completed_with_errors
        pending -> running -> failed
        pending -> running -> cancelled
        pending -> cancelled   (cancelled before it ever started)
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Statuses an `ExperimentRun` cannot leave — a run in one of these is done.
TERMINAL_RUN_STATUSES = frozenset(
    {
        ExperimentRunStatus.COMPLETED,
        ExperimentRunStatus.COMPLETED_WITH_ERRORS,
        ExperimentRunStatus.FAILED,
        ExperimentRunStatus.CANCELLED,
    }
)


class RunItemStatus(StrEnum):
    """Lifecycle of a single `RunItem`."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunItemErrorType(StrEnum):
    """Classification of why a `RunItem` failed — lets the UI/Phase 4
    distinguish "the model was unreachable" from "our prompt was broken"
    without parsing free-text error messages.
    """

    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    PROMPT_RENDER_ERROR = "prompt_render_error"
    STRUCTURED_OUTPUT_ERROR = "structured_output_error"
    UNKNOWN_ERROR = "unknown_error"


class EvaluationRunStatus(StrEnum):
    """Lifecycle of an `EvaluationRun` — deliberately the same shape as
    `ExperimentRunStatus` (Part 2's statuses are identical), but kept as
    its own type since an EvaluationRun and an ExperimentRun are
    different aggregates that happen to share a lifecycle shape today;
    coupling them to the same enum would make an evaluation-only status
    (there are none yet, but Part 4's metric concept implies there could
    be) require touching the experiment engine's enum.

    Valid transitions (enforced by `app.evaluation.lifecycle`):

        pending -> running -> completed
        pending -> running -> completed_with_errors
        pending -> running -> failed
        pending -> running -> cancelled
        pending -> cancelled   (cancelled before it ever started)
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Statuses an `EvaluationRun` cannot leave.
TERMINAL_EVALUATION_STATUSES = frozenset(
    {
        EvaluationRunStatus.COMPLETED,
        EvaluationRunStatus.COMPLETED_WITH_ERRORS,
        EvaluationRunStatus.FAILED,
        EvaluationRunStatus.CANCELLED,
    }
)


class EvaluationResultStatus(StrEnum):
    """Lifecycle of a single `EvaluationResult` — mirrors `RunItemStatus`
    (pending is implicit: a row is only ever inserted once evaluation of
    that item has actually finished, succeeded, failed, or been
    cancelled, so there's no separate pending/running state to track)."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
