"""C-002 encoding-safe human terminal output (SHADOW-C-002 remediation)."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.terminal_io import adapt_human_text, human_print

_ATTENTION_REPORT = {
    "rollup": "ATTENTION",
    "care_about": [
        {
            "level": "WARN",
            "reason_code": "TEST",
            "why_seeing_this": "sample reason",
            "what_to_do": "sample action",
        }
    ],
    "level_counts": {"WARN": 1},
}

_ATTENTION_REPORT_CLEAR = {
    "rollup": "CLEAR",
    "care_about": [],
    "level_counts": {},
}

_ATTENTION_REPORT_NONASCII = {
    "rollup": "ATTENTION",
    "care_about": [
        {
            "level": "WARN",
            "reason_code": "TEST",
            "why_seeing_this": "café résumé",
            "what_to_do": "naïve fix",
        }
    ],
    "level_counts": {"WARN": 1},
}


def _run_attention(
    *,
    encoding: str,
    report: dict,
    as_json: bool = False,
    tty: bool = False,
) -> tuple[int, str]:
    buf = io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict", line_buffering=True)
    buf.isatty = lambda: tty  # type: ignore[method-assign]
    argv = ["atlas", "attention", "--vault", "v", "--project", "p"]
    if as_json:
        argv.append("--json")
    with patch("sys.argv", argv), patch(
        "project_atlas.cli.classify_attention", return_value=report
    ), patch("sys.stdout", buf):
        code = main()
    buf.seek(0)
    return code, buf.read()


@pytest.mark.parametrize("encoding", ["cp1252", "cp850"])
def test_attention_tty_actionable_no_crash(encoding: str) -> None:
    """A/B: cp1252/cp850 TTY + non-empty care_about => PASS."""
    code, out = _run_attention(encoding=encoding, report=_ATTENTION_REPORT, tty=True)
    assert code == EXIT_OK
    assert "TEST" in out
    assert "\u2192" not in out or "->" in out


def test_attention_utf8_tty_preserves_unicode() -> None:
    """C: UTF-8 TTY => Unicode arrow preserved."""
    code, out = _run_attention(encoding="utf-8", report=_ATTENTION_REPORT, tty=True)
    assert code == EXIT_OK
    assert "\u2192" in out


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_attention_redirected_stdout(encoding: str) -> None:
    """D/E: redirected stdout => PASS (no UnicodeEncodeError)."""
    code, out = _run_attention(encoding=encoding, report=_ATTENTION_REPORT, tty=False)
    assert code == EXIT_OK
    assert "sample reason" in out
    assert "sample action" in out


def test_attention_json_cp1252_schema_unchanged() -> None:
    """F: --json under cp1252 => schema unchanged, arrow not substituted."""
    code, out = _run_attention(
        encoding="cp1252", report=_ATTENTION_REPORT, as_json=True, tty=False
    )
    assert code == EXIT_OK
    payload = json.loads(out)
    assert payload["rollup"] == "ATTENTION"
    assert payload["care_about"][0]["reason_code"] == "TEST"
    assert "why_seeing_this" in payload["care_about"][0]


def test_attention_empty_clear() -> None:
    """G: empty CLEAR result => PASS."""
    code, out = _run_attention(encoding="cp1252", report=_ATTENTION_REPORT_CLEAR, tty=True)
    assert code == EXIT_OK
    assert "CLEAR" in out
    assert "care_about (0)" in out


def test_attention_nonascii_project_text_cp1252() -> None:
    """H: non-ASCII project/source text => no crash; content preserved when encodable."""
    code, out = _run_attention(
        encoding="cp1252", report=_ATTENTION_REPORT_NONASCII, tty=True
    )
    assert code == EXIT_OK
    assert "caf" in out


def test_adapt_human_text_decorative_fallback() -> None:
    assert adapt_human_text("a \u2192 b", encoding="cp1252") == "a -> b"


def test_adapt_human_text_utf8_preserved() -> None:
    text = "a \u2192 b"
    assert adapt_human_text(text, encoding="utf-8") == text


def test_human_print_cp1252_redirect() -> None:
    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    human_print("x \u2192 y", file=buf)
    buf.seek(0)
    assert buf.read() == "x -> y\n"
