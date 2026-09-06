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
#: The one stderr handler this module owns, kept so a later explicit
#: `configure_logging` can re-install its formatter without ever attaching a
#: second handler (which would duplicate every record).
_HANDLER: logging.Handler | None = None


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


def configure_logging(level: str = "INFO", log_format: str | None = None) -> None:
    """Configure the ``project_atlas`` root logger.

    Idempotent in *attachment*: the stderr handler is added exactly once, so
    repeated calls never duplicate records.

    The formatter is re-installed whenever ``log_format`` is given. That is
    what makes ``atlas --log-format json`` work at all: every module does
    ``_log = get_logger(...)`` at import, which configures logging with the
    console default long before the CLI has parsed its arguments. Choosing
    the formatter only on the first call therefore pinned every process to
    ``console``, and a deployment that asked for JSON silently got neither an
    error nor JSON.

    ``log_format=None`` means "keep whatever format is installed", defaulting
    to ``console`` on the first call. An implicit configuration can then
    never downgrade a format the caller explicitly asked for.

    The handler is never attached before it has a formatter. Attaching first
    would leave a window in which a record emitted from another thread is
    rendered by `logging`'s default formatter -- bare `%(message)s`, with no
    level, no logger name and, worse, none of this module's redaction.
    """
    global _CONFIGURED, _HANDLER
    logger = logging.getLogger(_LOGGER_NAME)
    formatter: logging.Formatter = (
        JsonFormatter() if log_format == "json" else ConsoleFormatter()
    )
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        _HANDLER = handler
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True
    elif log_format is not None and _HANDLER is not None:
        _HANDLER.setFormatter(formatter)
    logger.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``project_atlas`` namespace."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
