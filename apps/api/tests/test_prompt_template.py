"""Tests for the `{{variable}}` prompt template system."""

import pytest
from app.experiments.prompt_template import (
    PromptTemplateError,
    build_context,
    render_prompt,
    validate_template,
)


def test_render_substitutes_input() -> None:
    rendered = render_prompt(
        "Explain the following concept simply:\n\n{{input}}",
        build_context("Explain TCP handshake"),
    )
    assert rendered == "Explain the following concept simply:\n\nExplain TCP handshake"


def test_render_supports_multiple_uses_of_the_same_variable() -> None:
    rendered = render_prompt("{{input}} / {{input}}", build_context("x"))
    assert rendered == "x / x"


def test_render_json_stringifies_non_string_input() -> None:
    rendered = render_prompt("Q: {{input}}", build_context({"question": "hi"}))
    assert rendered == 'Q: {"question": "hi"}'


def test_render_with_no_placeholders_returns_the_template_unchanged() -> None:
    rendered = render_prompt("Just a static prompt.", build_context("unused"))
    assert rendered == "Just a static prompt."


def test_validate_template_rejects_empty_template() -> None:
    with pytest.raises(PromptTemplateError, match="cannot be empty"):
        validate_template("")

    with pytest.raises(PromptTemplateError, match="cannot be empty"):
        validate_template("   ")


def test_validate_template_rejects_unknown_variables() -> None:
    with pytest.raises(PromptTemplateError, match='Unknown variable "question"'):
        validate_template("{{question}}")


def test_validate_template_rejects_malformed_placeholders() -> None:
    with pytest.raises(PromptTemplateError, match="malformed placeholder"):
        validate_template("{{1input}}")

    with pytest.raises(PromptTemplateError, match="malformed placeholder"):
        validate_template("{{}}")


def test_validate_template_rejects_unbalanced_braces() -> None:
    with pytest.raises(PromptTemplateError, match="unbalanced"):
        validate_template("{{input}")


def test_validate_template_rejects_oversized_templates() -> None:
    with pytest.raises(PromptTemplateError, match="maximum length"):
        validate_template("x" * 100_000)


def test_validate_template_accepts_a_template_with_no_placeholders() -> None:
    validate_template("A completely static prompt with no variables.")


def test_render_does_not_execute_when_template_is_invalid() -> None:
    """A template error must surface before any generation is attempted —
    the runner relies on this to never call the LLM with a broken prompt."""
    with pytest.raises(PromptTemplateError):
        render_prompt("{{unknown}}", build_context("x"))


def test_render_rejects_oversized_rendered_output() -> None:
    with pytest.raises(PromptTemplateError, match="rendered prompt exceeds"):
        render_prompt("{{input}}", build_context("x" * 100_000))
