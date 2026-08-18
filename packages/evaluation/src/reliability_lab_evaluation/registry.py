"""`EvaluatorRegistry` — a name -> `Evaluator` class lookup.

Deliberately not a giant `if/elif` chain (Part 5): adding a new evaluator
means writing a new `Evaluator` subclass and decorating it with
`@EvaluatorRegistry.register`, in its own module under `evaluators/` —
nothing in the runner, the API routes, or this file changes.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.exceptions import EvaluationConfigError
from reliability_lab_evaluation.types import EvaluatorMetadata

EvaluatorT = TypeVar("EvaluatorT", bound=type[Evaluator])


class EvaluatorRegistry:
    """Process-wide registry of known evaluator types."""

    _evaluators: dict[str, type[Evaluator]] = {}

    @classmethod
    def register(cls, evaluator_cls: EvaluatorT) -> EvaluatorT:
        name = evaluator_cls.metadata.name
        if name in cls._evaluators and cls._evaluators[name] is not evaluator_cls:
            raise ValueError(f"An evaluator named '{name}' is already registered")
        cls._evaluators[name] = evaluator_cls
        return evaluator_cls

    @classmethod
    def get(cls, name: str) -> type[Evaluator]:
        try:
            return cls._evaluators[name]
        except KeyError:
            raise EvaluationConfigError(
                f"Unknown evaluator type '{name}'. Known types: "
                f"{', '.join(sorted(cls._evaluators)) or '(none registered)'}"
            ) from None

    @classmethod
    def validate_config(cls, name: str, config: dict[str, Any]) -> BaseModel:
        """Validate `config` for evaluator `name` without instantiating
        it — used by the API to reject bad configuration (422) before an
        `EvaluationRun` row is ever created, and without needing an
        `EmbeddingProvider`/`LLMProvider` on hand just to validate."""
        evaluator_cls = cls.get(name)
        try:
            return evaluator_cls.validate_config(config)
        except ValidationError as exc:
            raise EvaluationConfigError(
                f"Invalid configuration for evaluator '{name}': {exc}"
            ) from exc

    @classmethod
    def create(
        cls,
        name: str,
        config: dict[str, Any],
        *,
        embedding_provider: Any | None = None,
        llm_provider: Any | None = None,
    ) -> Evaluator:
        evaluator_cls = cls.get(name)
        metadata = evaluator_cls.metadata
        if metadata.requires_embedding_provider and embedding_provider is None:
            raise EvaluationConfigError(
                f"Evaluator '{name}' requires an embedding provider, but none was configured"
            )
        if metadata.requires_llm_provider and llm_provider is None:
            raise EvaluationConfigError(
                f"Evaluator '{name}' requires an LLM provider, but none was configured"
            )
        try:
            return evaluator_cls(
                config, embedding_provider=embedding_provider, llm_provider=llm_provider
            )
        except ValidationError as exc:
            raise EvaluationConfigError(
                f"Invalid configuration for evaluator '{name}': {exc}"
            ) from exc

    @classmethod
    def list_metadata(cls) -> list[EvaluatorMetadata]:
        """Metadata for every registered evaluator, `config_schema`
        filled in from each evaluator's `config_model` — this is what
        `GET /api/v1/evaluators` returns so the frontend can render
        dynamic configuration forms instead of hard-coding them
        (Part 37)."""
        results = []
        for evaluator_cls in cls._evaluators.values():
            metadata = evaluator_cls.metadata
            schema = _config_schema(evaluator_cls)
            results.append(metadata.model_copy(update={"config_schema": schema}))
        return sorted(results, key=lambda m: m.name)

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._evaluators)


def _config_schema(evaluator_cls: type[Evaluator]) -> dict[str, Any]:
    return evaluator_cls.config_model.model_json_schema()
