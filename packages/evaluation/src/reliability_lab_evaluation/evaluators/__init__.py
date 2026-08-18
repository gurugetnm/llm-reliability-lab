"""Importing this module registers every built-in evaluator with
`EvaluatorRegistry`. `reliability_lab_evaluation/__init__.py` imports it
for its side effect so the registry is always fully populated as soon as
the package is imported — no evaluator module needs to be imported by
hand elsewhere.
"""

from reliability_lab_evaluation.evaluators.contains import ContainsEvaluator
from reliability_lab_evaluation.evaluators.exact_match import ExactMatchEvaluator

__all__ = [
    "ContainsEvaluator",
    "ExactMatchEvaluator",
]
