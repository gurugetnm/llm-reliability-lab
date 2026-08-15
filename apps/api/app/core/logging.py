"""Structured logging configuration.

Emits one JSON object per log line — easy to grep locally and to ship to
a log aggregator later without changing how the app logs.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Anything passed via `extra={...}` is merged in verbatim.
        reserved = logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys() | {
            "message",
            "asctime",
        }
        for key, value in record.__dict__.items():
            if key not in reserved and key not in payload:
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON to stdout.

    Called once at startup. Uvicorn's own loggers are routed through the
    same handler so access logs use the same format.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False
