"""Valid `ExperimentRunStatus` transitions.

Centralized so "can a run legally move from X to Y" has exactly one
answer, checked the same way whether the caller is the runner finishing
a run or the cancel endpoint requesting one stop.
"""

from __future__ import annotations

from app.models.enums import ExperimentRunStatus as Status

_VALID_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.PENDING: frozenset({Status.RUNNING, Status.CANCELLED}),
    Status.RUNNING: frozenset(
        {Status.COMPLETED, Status.COMPLETED_WITH_ERRORS, Status.FAILED, Status.CANCELLED}
    ),
    Status.COMPLETED: frozenset(),
    Status.COMPLETED_WITH_ERRORS: frozenset(),
    Status.FAILED: frozenset(),
    Status.CANCELLED: frozenset(),
}


class InvalidRunTransitionError(Exception):
    """Raised when code attempts a nonsensical run state change, e.g.
    `completed -> running`."""

    def __init__(self, current: Status, target: Status) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition an experiment run from {current!r} to {target!r}")


def can_transition(current: Status, target: Status) -> bool:
    return target in _VALID_TRANSITIONS.get(current, frozenset())


def require_transition(current: Status, target: Status) -> None:
    if not can_transition(current, target):
        raise InvalidRunTransitionError(current, target)


def is_terminal(status: Status) -> bool:
    return len(_VALID_TRANSITIONS.get(status, frozenset())) == 0
