"""AT3-081-F3 — corrupt pulse/reconcile artifacts fail closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import OPS_RELATIVE, Atlas3Error
from project_atlas.atlas3.ledger import append_event
from project_atlas.atlas3.stale_conflict import compile_stale_conflict_intel


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_corrupt_pulse_json_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / OPS_RELATIVE / "pulse" / "harbor-api.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_stale_conflict_intel(vault, "harbor-api")
    assert exc.value.code == "PULSE_CORRUPT"


def test_array_pulse_fails_closed_even_with_ledger(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        kind="claim",
        summary="invalidated",
        payload={"freshness": "STALE"},
    )
    path = vault / OPS_RELATIVE / "pulse" / "harbor-api.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_stale_conflict_intel(vault, "harbor-api")
    assert exc.value.code == "PULSE_CORRUPT"


def test_corrupt_reconcile_json_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / OPS_RELATIVE / "memory" / "harbor-api" / "reconcile.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_stale_conflict_intel(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"


def test_missing_pulse_still_unknown(tmp_path: Path) -> None:
    report = compile_stale_conflict_intel(_vault(tmp_path), "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["reason"] == "NO_STALE_OR_CONFLICT_EVIDENCE"
