"""Concurrency limits for experiment runs.

A single place defining "how many generations can run at once" so the
API schema, the service layer, and the runner itself all agree on the
same default and the same hard ceiling — a dataset of any size is never
run with unlimited concurrency.
"""

#: Sensible default — comfortably parallel without overwhelming a local
#: Ollama instance running on one machine.
DEFAULT_CONCURRENCY = 3

#: Hard ceiling. Configurable up to here, never beyond — Part 17 is
#: explicit that unlimited concurrency is not the goal.
MAX_CONCURRENCY = 10


def clamp_concurrency(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_CONCURRENCY
    return max(1, min(requested, MAX_CONCURRENCY))
