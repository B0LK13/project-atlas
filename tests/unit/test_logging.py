"""Unit tests for structured logging (A-005 / SEC-ADV-INT-002)."""

from __future__ import annotations

import json
import logging

from project_atlas.logging import ConsoleFormatter, JsonFormatter, configure_logging, get_logger
from project_atlas.secrets import REDACTED_PLACEHOLDER


def test_json_formatter_emits_parseable_record() -> None:
    record = logging.LogRecord("project_atlas.test", logging.INFO, __file__, 1, "hello", (), None)
    record.context = {"path": "a.md"}  # type: ignore[attr-defined]
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["path"] == "a.md"


def test_configure_logging_is_idempotent() -> None:
    logger = logging.getLogger("project_atlas")
    before = len(logger.handlers)  # pytest's log plugin attaches its own handlers
    configure_logging(level="DEBUG")
    configure_logging(level="INFO")
    assert len(logger.handlers) <= before + 1
    assert logger.level == logging.INFO


def test_child_logger_namespaced() -> None:
    assert get_logger("scaffold").name == "project_atlas.scaffold"


def test_formatters_redact_secret_shaped_message_and_context() -> None:
    """SEC-ADV-INT-002: logging boundary redacts interpolated secret canaries."""
    synth = "sk_test_SYNTHETIC_ADV_INT_002_DO_NOT_USE_ABCDEF12"
    msg = f"api_key = '{synth}'"
    record = logging.LogRecord(
        "project_atlas.test", logging.INFO, __file__, 1, msg, (), None
    )
    record.context = {"detail": msg, "ok": "safe"}  # type: ignore[attr-defined]

    json_line = JsonFormatter().format(record)
    console_line = ConsoleFormatter().format(record)
    for blob in (json_line, console_line):
        assert synth not in blob
        assert REDACTED_PLACEHOLDER in blob
    payload = json.loads(json_line)
    assert payload["ok"] == "safe"
    assert synth not in payload["message"]
    assert synth not in str(payload.get("detail", ""))
