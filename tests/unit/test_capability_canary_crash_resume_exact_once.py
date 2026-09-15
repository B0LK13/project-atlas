"""Capability-canary crash/resume: file hash changes exactly once.

Models the disposable canary injected-crash contract (T003E remediation
Phase 2 item 6): a write intent applies at most once; a crash after the
first successful write and a fail-closed resume must not double-append or
re-apply the mutation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _apply_canary_edit_once(
    target: Path,
    *,
    intent_marker: Path,
    crash_after_write: bool = False,
) -> str:
    """Idempotent bounded edit: CANARY_VALUE 0→1 exactly once.

    The intent marker is the durable resume gate. If it already exists, the
    write is treated as completed and must not mutate the target again.
    """
    if intent_marker.exists():
        return "skipped_already_applied"
    text = target.read_text(encoding="utf-8")
    if "CANARY_VALUE = 0" not in text:
        raise AssertionError("expected CANARY_VALUE = 0 before first write")
    target.write_text(text.replace("CANARY_VALUE = 0", "CANARY_VALUE = 1", 1), encoding="utf-8")
    intent_marker.write_text(
        json.dumps({"applied": True, "path": str(target.name)}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if crash_after_write:
        raise RuntimeError("injected adapter crash after first write intent")
    return "applied"


def test_crash_after_write_then_resume_mutates_exactly_once(tmp_path: Path) -> None:
    target = tmp_path / "canary_target.py"
    target.write_text(
        '"""Isolated capability-canary target."""\n\nCANARY_VALUE = 0\n',
        encoding="utf-8",
    )
    marker = tmp_path / "write-intent.done"
    before = _sha256(target)

    with pytest.raises(RuntimeError, match="injected adapter crash"):
        _apply_canary_edit_once(target, intent_marker=marker, crash_after_write=True)

    mid = _sha256(target)
    assert mid != before
    assert "CANARY_VALUE = 1" in target.read_text(encoding="utf-8")
    assert marker.is_file()

    # Fail-closed resume: same intent must not rewrite / double-append.
    result = _apply_canary_edit_once(target, intent_marker=marker, crash_after_write=False)
    assert result == "skipped_already_applied"
    after = _sha256(target)
    assert after == mid
    assert target.read_text(encoding="utf-8").count("CANARY_VALUE = 1") == 1
    assert "CANARY_VALUE = 0" not in target.read_text(encoding="utf-8")


def test_append_style_double_write_is_rejected_by_exact_once_gate(tmp_path: Path) -> None:
    """Regression: naive resume that appends would change the hash twice."""
    target = tmp_path / "canary_target.py"
    target.write_text("CANARY_VALUE = 0\n", encoding="utf-8")
    marker = tmp_path / "write-intent.done"
    _apply_canary_edit_once(target, intent_marker=marker)
    once = _sha256(target)

    # Naive double-append (forbidden pattern) would alter bytes again.
    naive = target.read_text(encoding="utf-8") + "CANARY_VALUE = 1\n"
    assert hashlib.sha256(naive.encode()).hexdigest() != once

    # Exact-once gate prevents that class of mutation on resume.
    assert _apply_canary_edit_once(target, intent_marker=marker) == "skipped_already_applied"
    assert _sha256(target) == once
