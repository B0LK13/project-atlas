"""Structured logging for Project Atlas (backlog A-005).

Logs are emitted to stderr only, so generated vault output on stdout is
never interleaved with log records. Two formats are supported:

- ``console``: human-readable single-line records (default);
- ``json``: one JSON object per line, suitable for log aggregation.

NFR-004 / SEC-ADV-INT-002: formatters redact secret-shaped spans via
``project_atlas.secrets.redact_text`` before emission (defense in depth).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from project_atlas.secrets import redact_text

_LOGGER_NAME = "project_atlas"
_CONFIGURED = False


def _safe_text(value: object) -> str:
    """Stringify then redact secret-shaped content for log emission."""
    return redact_text(str(value))


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: _safe_text(value) for key, value in context.items()}


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": _safe_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = _safe_text(self.formatException(record.exc_info))
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            for key, value in _safe_context(context).items():
                payload[key] = value
        return json.dumps(payload, sort_keys=True, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable single-line format."""

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "context", None)
        suffix = ""
        if isinstance(context, dict) and context:
            rendered = " ".join(
                f"{key}={value}" for key, value in sorted(_safe_context(context).items())
            )
            suffix = f" [{rendered}]"
        return f"{record.levelname} {record.name}: {_safe_text(record.getMessage())}{suffix}"


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
