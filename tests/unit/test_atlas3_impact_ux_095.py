"""AT3-095 — isolated Impact Explorer UX composer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.impact_ux import PACKAGE_ID, UX_SURFACE, compile_impact_ux


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "impact" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_impact_ux(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["data_package_id"] == "AT3-080"
    assert report["ux_surface"] == UX_SURFACE
    assert report["status"] == "UNKNOWN"
    assert report["graph_is_authority"] is False
    assert report["new_cli_command"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_composes_declared_impacts(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "impacts": [
                {
                    "impact_kind": "blocks",
                    "from_id": "conflict-1",
                    "to_id": "release-1",
                    "evidence_refs": ["doc:conflicts.md#pg"],
                }
            ],
        },
    )
    report = compile_impact_ux(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"impacts": 1}
    assert report["impacts"][0]["impact_kind"] == "blocks"
    assert report["trust_score_used"] is False


def test_trust_score_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "harbor-api", "trust_score": 0.9, "impacts": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_impact_ux(vault, "harbor-api")
    assert exc.value.code == "TRUST_SCORE_FORBIDDEN"


def test_cross_project_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign", "impacts": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_impact_ux(vault, "harbor-api")
    assert exc.value.code == "CROSS_PROJECT"


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/impact_ux.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "add_parser",
    ):
        assert name not in source
