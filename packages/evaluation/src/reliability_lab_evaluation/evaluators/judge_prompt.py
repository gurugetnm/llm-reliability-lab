"""Builds the structured judge prompt and its JSON Schema for
`LLMJudgeEvaluator`. Split out from `llm_judge.py` so the prompt itself
is independently readable/testable.
"""

from __future__ import annotations

import json
from typing import Any

from reliability_lab_llm import Message

from reliability_lab_evaluation.types import EvaluationInput

DEFAULT_JUDGE_SYSTEM_PROMPT = (
    "You are a strict, impartial evaluator for an LLM reliability lab. "
    "You compare a candidate answer against a question and (optionally) a "
    "reference expected answer, and grade it against the given criteria. "
    "Respond with JSON only — no prose before or after the JSON object."
)


def build_response_schema(criteria: list[str], score_scale: int) -> dict[str, Any]:
    """The JSON Schema the judge's structured output is validated
    against (Part 17: never trust raw model output)."""
    return {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": score_scale,
                "description": f"Overall score from 0 to {score_scale}.",
            },
            "passed": {"type": "boolean"},
            "reason": {"type": "string", "description": "Brief justification for the score."},
            "criteria": {
                "type": "object",
                "properties": {
                    criterion: {"type": "number", "minimum": 0, "maximum": score_scale}
                    for criterion in criteria
                },
                "required": criteria,
                "additionalProperties": False,
            },
        },
        "required": ["score", "passed", "reason", "criteria"],
        "additionalProperties": False,
    }


def build_judge_messages(
    item: EvaluationInput,
    *,
    criteria: list[str],
    score_scale: int,
    system_prompt: str | None,
) -> list[Message]:
    criteria_list = "\n".join(f"- {criterion}" for criterion in criteria)
    expected = (
        json.dumps(item.expected_output, indent=2, sort_keys=True)
        if item.expected_output is not None
        else "(no reference answer provided — judge the candidate answer on its own merits)"
    )
    user_prompt = f"""Question/Input:
{item.input if isinstance(item.input, str) else json.dumps(item.input, indent=2, sort_keys=True)}

Expected Answer:
{expected}

Candidate Answer:
{item.actual_text() or "(empty response)"}

Evaluation Criteria (score each from 0 to {score_scale}):
{criteria_list}

Grade the candidate answer against each criterion above, then give an
overall score from 0 to {score_scale} and a brief reason. Set "passed" to
your best judgment of whether the candidate answer is acceptable overall.
Respond with a single JSON object matching the required schema — no other
text."""

    return [
        Message(role="system", content=system_prompt or DEFAULT_JUDGE_SYSTEM_PROMPT),
        Message(role="user", content=user_prompt),
    ]
