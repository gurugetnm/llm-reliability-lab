"""Classifies an exception raised while processing one `RunItem` into a
`RunItemErrorType` — lets the UI (and Phase 4) distinguish "the model
was unreachable" from "our prompt was broken" without parsing free-text
error messages.
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError
from reliability_lab_llm import ModelNotFoundError, ProviderConnectionError, ProviderError
from reliability_lab_llm.exceptions import StructuredOutputError

from app.experiments.prompt_template import PromptTemplateError
from app.models.enums import RunItemErrorType


def classify_exception(exc: Exception) -> RunItemErrorType:
    # Order matters: PromptTemplateError subclasses ValueError, so it
    # must be checked before the generic ValueError/PydanticValidationError case.
    if isinstance(exc, TimeoutError):
        return RunItemErrorType.TIMEOUT
    if isinstance(exc, StructuredOutputError):
        return RunItemErrorType.STRUCTURED_OUTPUT_ERROR
    if isinstance(exc, PromptTemplateError):
        return RunItemErrorType.PROMPT_RENDER_ERROR
    if isinstance(exc, ModelNotFoundError | ProviderConnectionError | ProviderError):
        return RunItemErrorType.PROVIDER_ERROR
    if isinstance(exc, PydanticValidationError | ValueError):
        return RunItemErrorType.VALIDATION_ERROR
    return RunItemErrorType.UNKNOWN_ERROR
