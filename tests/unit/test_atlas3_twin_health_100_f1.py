"""AT3-100-F1 — twin health must not treat stale signals as current."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.twin_health import compile_twin_health


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "twin-health" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_stale_freshness_with_current_state_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "signals": [
                {
                    "signal_id": "datastore",
                    "state": "CURRENT",
                    "freshness": "STALE",
                    "status": "verified",
                    "stale_as_current": True,
                    "unverified": True,
                    "evidence_refs": ["ev-1"],
                }
            ]
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_twin_health(vault, "harbor-api")
    assert exc.value.code == "STALE_AS_CURRENT"


def test_current_signal_without_stale_flags_still_derives(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "signals": [
                {
                    "signal_id": "datastore",
                    "state": "CURRENT",
                    "evidence_refs": ["ev-1"],
                }
            ]
        },
    )
    report = compile_twin_health(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["signals"][0]["state"] == "CURRENT"
    assert report["signals"][0]["is_authority"] is False
