"""Provider-agnostic LLM abstraction.

The rest of the platform talks to :class:`LLMProvider`, never to a specific
vendor SDK. New providers (OpenAI, Anthropic, HuggingFace, ...) are added by
implementing this interface, not by threading vendor-specific calls through
the application.
"""

from reliability_lab_llm.base import LLMProvider
from reliability_lab_llm.exceptions import (
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    StructuredOutputError,
)
from reliability_lab_llm.ollama import OllamaProvider
from reliability_lab_llm.types import (
    GenerationOptions,
    GenerationResult,
    Message,
    ModelInfo,
    ModelSummary,
    StreamChunk,
    StructuredGenerationResult,
)

__version__ = "0.1.0"

__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "GenerationOptions",
    "GenerationResult",
    "ModelInfo",
    "ModelSummary",
    "Message",
    "StreamChunk",
    "StructuredGenerationResult",
    "ProviderError",
    "ProviderConnectionError",
    "ModelNotFoundError",
    "StructuredOutputError",
]
