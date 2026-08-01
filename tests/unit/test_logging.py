"""Unit tests for structured logging (A-005)."""

from __future__ import annotations

import json
import logging

from project_atlas.logging import JsonFormatter, configure_logging, get_logger


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
