"""Valid `EvaluationRunStatus` transitions — the evaluation-run analogue
of `app.experiments.lifecycle`, kept as its own module for the same
reason `app.evaluation.concurrency` is: EvaluationRun and ExperimentRun
are different aggregates that happen to share a lifecycle shape.
"""

from __future__ import annotations

from app.models.enums import EvaluationRunStatus as Status

_VALID_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.PENDING: frozenset({Status.RUNNING, Status.CANCELLED, Status.COMPLETED}),
    Status.RUNNING: frozenset(
        {Status.COMPLETED, Status.COMPLETED_WITH_ERRORS, Status.FAILED, Status.CANCELLED}
    ),
    Status.COMPLETED: frozenset(),
    Status.COMPLETED_WITH_ERRORS: frozenset(),
    Status.FAILED: frozenset(),
    Status.CANCELLED: frozenset(),
}


class InvalidEvaluationTransitionError(Exception):
    """Raised when code attempts a nonsensical evaluation status change,
    e.g. `completed -> running`."""

    def __init__(self, current: Status, target: Status) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition an evaluation run from {current!r} to {target!r}")


def can_transition(current: Status, target: Status) -> bool:
    return target in _VALID_TRANSITIONS.get(current, frozenset())


def require_transition(current: Status, target: Status) -> None:
    if not can_transition(current, target):
        raise InvalidEvaluationTransitionError(current, target)


def is_terminal(status: Status) -> bool:
    return len(_VALID_TRANSITIONS.get(status, frozenset())) == 0
