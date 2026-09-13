"""AT3-015-F2 — Pulse must not compose stale or empty answers as current truth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.pulse import compile_pulse


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_changed(vault: Path, payload: object) -> None:
    answers = vault / "generated" / "answers"
    answers.mkdir(parents=True)
    (answers / "ans-changed-harbor-api.json").write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )


def test_stale_verified_answer_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_changed(
        vault,
        {"freshness": "STALE", "status": "verified", "summary": "stale claim"},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_pulse(vault, "harbor-api")
    assert exc.value.code == "STALE_AS_CURRENT"


def test_stale_current_answer_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_changed(
        vault,
        {"freshness": "STALE", "status": "CURRENT", "summary": "stale claim"},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_pulse(vault, "harbor-api")
    assert exc.value.code == "STALE_AS_CURRENT"


def test_empty_object_answer_stays_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_changed(vault, {})
    report = compile_pulse(vault, "harbor-api")
    changed = report["questions"]["what_changed"]
    assert changed["status"] == "UNKNOWN"
    assert changed["items"] == []
    assert changed["reason"] == "changed lens not materialized"


def test_stale_without_verified_status_is_stale_not_derived(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_changed(vault, {"freshness": "STALE", "summary": "historical note"})
    report = compile_pulse(vault, "harbor-api")
    changed = report["questions"]["what_changed"]
    assert changed["status"] == "STALE"
    assert changed["status"] != "derived"
    assert changed["status"] != "verified"
