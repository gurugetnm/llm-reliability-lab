"""Evaluation engine — scoring `RunItem`s against a dataset's expected
outputs, independently of generation.

    EvaluationRunner
       -> EvaluatorRegistry
       -> Evaluator
       -> Evaluation Strategy (exact_match / contains / semantic_similarity / llm_judge)

Everything here is framework-agnostic: no FastAPI, no SQLAlchemy, no
Ollama. `apps/api/app/evaluation/` (the runner, persistence, API routes)
is what wires this into the rest of the application — see
`docs/evaluation.md`.
"""

# Importing this registers every built-in evaluator (see evaluators/__init__.py).
from reliability_lab_evaluation import evaluators as _evaluators  # noqa: F401
from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.embeddings.base import EmbeddingProvider
from reliability_lab_evaluation.exceptions import EvaluationConfigError, EvaluatorExecutionError
from reliability_lab_evaluation.metrics import (
    AggregateMetrics,
    ResultRecord,
    calculate_aggregate_metrics,
)
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.regression import (
    DEFAULT_REGRESSION_THRESHOLD,
    RegressionResult,
    detect_regression,
)
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata

__version__ = "0.1.0"

__all__ = [
    "AggregateMetrics",
    "DEFAULT_REGRESSION_THRESHOLD",
    "EmbeddingProvider",
    "EvaluationConfigError",
    "EvaluationInput",
    "EvaluationOutput",
    "Evaluator",
    "EvaluatorExecutionError",
    "EvaluatorMetadata",
    "EvaluatorRegistry",
    "RegressionResult",
    "ResultRecord",
    "calculate_aggregate_metrics",
    "detect_regression",
]
