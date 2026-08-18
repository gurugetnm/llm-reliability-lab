"""Concurrency limits for evaluation runs.

Mirrors `app.experiments.concurrency` exactly, but as its own module —
an EvaluationRun's concurrency is about bounding parallel embedding/judge
calls, a different resource than parallel generation calls, so the two
are configured (and, in the API schema, validated) independently even
though today they share the same default/ceiling.
"""

#: Sensible default — comfortably parallel without overwhelming a local
#: embedding model or Ollama-hosted judge.
DEFAULT_CONCURRENCY = 3

#: Hard ceiling. Configurable up to here, never beyond (Part 21: no
#: unlimited concurrent embedding or judge requests).
MAX_CONCURRENCY = 10


def clamp_concurrency(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_CONCURRENCY
    return max(1, min(requested, MAX_CONCURRENCY))
