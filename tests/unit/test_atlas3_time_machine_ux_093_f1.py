"""AT3-093-F1 — Time Machine must not compose a stale snapshot as current."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.time_machine_ux import compile_time_machine_ux


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "time-machine" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_stale_snapshot_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "snapshots": [
                {
                    "valid_time": "2026-01-01T00:00:00Z",
                    "freshness": "STALE",
                    "status": "derived",
                }
            ]
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_time_machine_ux(vault, "harbor-api")
    assert exc.value.code == "STALE_AS_CURRENT"


def test_fresh_snapshot_still_composes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"snapshots": [{"valid_time": "2026-01-01T00:00:00Z"}]},
    )
    report = compile_time_machine_ux(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"]["snapshots"] == 1
    assert report["snapshots"][0]["as_of_is_authority"] is False
