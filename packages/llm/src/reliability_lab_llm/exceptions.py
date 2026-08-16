"""Exceptions raised by LLM providers.

Kept provider-agnostic so callers can catch a stable set of errors
regardless of which provider raised them.
"""


class ProviderError(Exception):
    """Base class for all provider errors."""


class ProviderConnectionError(ProviderError):
    """The provider could not be reached (network error, timeout, DNS, ...)."""


class ModelNotFoundError(ProviderError):
    """The requested model is not available on this provider."""

    def __init__(self, model: str, provider: str) -> None:
        self.model = model
        self.provider = provider
        super().__init__(f"Model '{model}' was not found on provider '{provider}'")


class StructuredOutputError(ProviderError):
    """A structured generation's output didn't parse as JSON, or didn't
    match the requested schema.

    Carries the raw model output so callers can show it for debugging
    instead of silently discarding a failed generation.
    """

    def __init__(self, message: str, *, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__(message)
