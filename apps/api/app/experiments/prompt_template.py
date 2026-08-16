"""A deliberately small `{{variable}}` prompt template system.

Not a general templating engine (no conditionals, loops, or filters) —
an experiment's user prompt template renders one dataset item into one
prompt, nothing more. `{{input}}` is the only variable today;
`KNOWN_VARIABLES` is the single place to extend that later (e.g. a
future `{{expected_output}}`) without touching the renderer itself.
"""

from __future__ import annotations

import json
import re
from typing import Any

#: Variables a template is allowed to reference. Extend this (and
#: `build_context`) to add new ones — the renderer itself never changes.
KNOWN_VARIABLES = frozenset({"input"})

#: Generous enough for any realistic prompt template while catching a
#: pasted-in document or an accidental duplication.
MAX_TEMPLATE_LENGTH = 20_000
MAX_RENDERED_LENGTH = 50_000

_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PromptTemplateError(ValueError):
    """A template failed validation or rendering — the caller must not
    execute an LLM request with it (see `app/models/enums.py`'s
    `RunItemErrorType.PROMPT_RENDER_ERROR` / `VALIDATION_ERROR`)."""


def _placeholder_names(template: str) -> list[str]:
    """Extracts every `{{...}}` placeholder's inner text, and raises if
    any is not a valid, known variable name or if braces are unbalanced."""
    if template.count("{{") != template.count("}}"):
        raise PromptTemplateError("Template error: unbalanced '{{' / '}}' braces")

    names = []
    for match in _PLACEHOLDER.finditer(template):
        raw = match.group(1).strip()
        if not _VALID_NAME.match(raw):
            raise PromptTemplateError(
                f'Template error: malformed placeholder "{{{{{match.group(1)}}}}}"'
            )
        names.append(raw)
    return names


def validate_template(template: str) -> None:
    """Validates a template without rendering it — used at
    experiment-create/update time so a broken template is rejected before
    any dataset item (or LLM call) is involved.
    """
    if not template or not template.strip():
        raise PromptTemplateError("Template error: template cannot be empty")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise PromptTemplateError(
            "Template error: template exceeds the maximum length of "
            f"{MAX_TEMPLATE_LENGTH} characters"
        )

    for name in _placeholder_names(template):
        if name not in KNOWN_VARIABLES:
            raise PromptTemplateError(f'Template error: Unknown variable "{name}"')


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def build_context(dataset_item_input: Any) -> dict[str, Any]:
    """Maps a dataset item's fields onto the template's variable
    namespace. A separate function from `render_prompt` so callers that
    just need "what variables would be available" (e.g. a future preview
    UI) don't need a template to ask."""
    return {"input": dataset_item_input}


def render_prompt(template: str, context: dict[str, Any]) -> str:
    """Renders `template` against `context`. Always call `validate_template`
    first (or expect `PromptTemplateError` here too) — this does not
    re-check variable names against `KNOWN_VARIABLES`, only against
    what `context` actually provides.
    """
    validate_template(template)

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name not in context:
            raise PromptTemplateError(f'Template error: Unknown variable "{name}"')
        return _stringify(context[name])

    rendered = _PLACEHOLDER.sub(_replace, template)

    if len(rendered) > MAX_RENDERED_LENGTH:
        raise PromptTemplateError(
            f"Template error: rendered prompt exceeds the maximum length of "
            f"{MAX_RENDERED_LENGTH} characters"
        )
    return rendered
