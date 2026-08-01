"""Structured logging for Project Atlas (backlog A-005).

Logs are emitted to stderr only, so generated vault output on stdout is
never interleaved with log records. Two formats are supported:

- ``console``: human-readable single-line records (default);
- ``json``: one JSON object per line, suitable for log aggregation.

Secret redaction hooks into ingestion (NFR-004) will live in later work
packages; this module only establishes the logging conventions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_LOGGER_NAME = "project_atlas"
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "context", {}).items():
            payload[key] = value
        return json.dumps(payload, sort_keys=True, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable single-line format."""

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "context", None)
        suffix = ""
        if context:
            rendered = " ".join(f"{key}={value}" for key, value in sorted(context.items()))
            suffix = f" [{rendered}]"
        return f"{record.levelname} {record.name}: {record.getMessage()}{suffix}"


def configure_logging(level: str = "INFO", log_format: str = "console") -> None:
    """Configure the ``project_atlas`` root logger.

    Idempotent: repeated calls update the level but attach the stderr
    handler only once.
    """
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter() if log_format == "json" else ConsoleFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True
    logger.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``project_atlas`` namespace."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
