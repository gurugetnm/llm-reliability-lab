"""Application-level exceptions and their FastAPI handlers.

Route/service code raises these instead of building `HTTPException`s
inline, so error shape and status codes stay consistent across the API.

`LLMProvider` errors (`packages/llm`) are handled centrally here too —
routes that call a provider don't need their own try/except for
"Ollama is down" or "model not found"; the handlers below translate
those into the same consistent JSON shape as everything else.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from reliability_lab_llm import ModelNotFoundError as ProviderModelNotFoundError
from reliability_lab_llm import ProviderConnectionError, StructuredOutputError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application errors that map to an HTTP response.

    `**context` is merged into the JSON body alongside `detail` — used
    e.g. to attach the raw model output to a structured-output error
    without every error type needing its own response schema.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None, **context: object) -> None:
        if detail is not None:
            self.detail = detail
        self.context = context
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Validation failed"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so every error response has a consistent JSON shape."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail, **exc.context}
        )

    @app.exception_handler(ProviderConnectionError)
    async def handle_provider_connection_error(
        _: Request, exc: ProviderConnectionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)}
        )

    @app.exception_handler(ProviderModelNotFoundError)
    async def handle_provider_model_not_found(
        _: Request, exc: ProviderModelNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(StructuredOutputError)
    async def handle_structured_output_error(
        _: Request, exc: StructuredOutputError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc), "raw_response": exc.raw_text},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )
