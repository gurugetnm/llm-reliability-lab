"""Exceptions raised by the evaluation engine.

Mirrors `reliability_lab_llm.exceptions`'s shape: a small, specific set of
exception types the caller (the evaluation runner, in `apps/api`) can
catch and classify, rather than letting arbitrary exceptions from
third-party libraries (an embedding model, `jsonschema`, ...) leak out
uncaught.
"""

from __future__ import annotations

from typing import Any


class EvaluationConfigError(ValueError):
    """Raised when evaluator configuration is missing, malformed, or
    fails the evaluator's own schema validation. Always a client error —
    never wraps a runtime failure."""


class EvaluatorExecutionError(Exception):
    """Raised when an evaluator fails to produce a result for an item —
    a judge model returned invalid structured output, an embedding call
    failed, a provider was unreachable, etc.

    Carries `details` (JSON-serializable) so the caller can persist
    useful diagnostic context (e.g. the judge's raw response) on the
    failed `EvaluationResult` without every evaluator needing its own
    exception subclass.
    """

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}
