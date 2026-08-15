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
