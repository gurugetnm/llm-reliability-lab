"""The `Evaluator` abstraction every evaluation strategy implements.

    EvaluationRunner
       -> EvaluatorRegistry
       -> Evaluator
       -> Evaluation Strategy (exact_match / contains / semantic_similarity / llm_judge)

An `Evaluator` is constructed once per `EvaluationRun` (so it can hold
per-run state, e.g. `SemanticSimilarityEvaluator`'s embedding cache) and
then has `evaluate()` called once per `RunItem`. It must not touch a
database or any other RunItem — everything it needs comes in via
`EvaluationInput` (built by the runner) and its own `config`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata


class Evaluator(ABC):
    """Base class for every evaluation strategy.

    Subclasses declare `metadata` (a `ClassVar[EvaluatorMetadata]`, minus
    `config_schema` which is filled in automatically from `config_model`)
    and `config_model` (the Pydantic model describing/validating this
    evaluator's configuration — Part 10's "validate configuration before
    evaluation starts", without ever `eval()`-ing arbitrary expressions).
    """

    metadata: ClassVar[EvaluatorMetadata]
    config_model: ClassVar[type[BaseModel]]

    def __init__(
        self,
        config: dict[str, Any],
        *,
        embedding_provider: Any | None = None,
        llm_provider: Any | None = None,
    ) -> None:
        """`embedding_provider`/`llm_provider` are provided by the runner
        for the evaluators that declare they need one
        (`metadata.requires_embedding_provider`/`requires_llm_provider`);
        every evaluator accepts both keywords (and ignores what it
        doesn't need) so `EvaluatorRegistry.create()` has one uniform
        call signature regardless of evaluator type.
        """
        self.raw_config = config
        self.config = self.validate_config(config)

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> BaseModel:
        """Validate `config` against `config_model`.

        Raises `pydantic.ValidationError` (callers — see
        `EvaluatorRegistry.validate_config` — translate that into
        `EvaluationConfigError`/a 422). This is the *only* mechanism for
        interpreting evaluator configuration: there is no code path that
        executes configuration as an expression.
        """
        return cls.config_model.model_validate(config)

    @abstractmethod
    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        """Score one item.

        Raise `reliability_lab_evaluation.exceptions.EvaluatorExecutionError`
        (or let a lower-level exception propagate) if this item cannot be
        scored — the runner catches it, records a failed
        `EvaluationResult`, and continues with the rest of the run.
        """
        raise NotImplementedError
