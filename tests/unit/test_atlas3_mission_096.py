"""AT3-096 — isolated Mission Command Center."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.mission import PACKAGE_ID, compile_mission


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "mission" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_mission(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["self_merge"] is False
    assert report["estate_is_authorization"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_declared_nodes_and_leases(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "nodes": [
                {
                    "node_id": "AT3-096",
                    "state": "READY",
                    "package_id": "AT3-096",
                    "evidence_refs": ["docs/atlas-3/EPICS.md"],
                }
            ],
            "leases": [
                {
                    "lease_id": "lease-1",
                    "holder": "agent-a",
                    "node_id": "AT3-096",
                    "evidence_refs": ["orch:lease-1"],
                }
            ],
        },
    )
    report = compile_mission(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"nodes": 1, "leases": 1}
    assert report["nodes"][0]["self_merge"] is False
    assert report["leases"][0]["grants_merge"] is False


def test_self_merge_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"project_id": "harbor-api", "self_merge": True, "nodes": [], "leases": []},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_mission(vault, "harbor-api")
    assert exc.value.code == "SELF_MERGE_FORBIDDEN"


def test_merge_claim_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "merge_authorization": "GRANTED",
            "nodes": [],
            "leases": [],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_mission(vault, "harbor-api")
    assert exc.value.code == "MERGE_CLAIMED"


def test_estate_authorization_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "estate_is_authorization": True,
            "nodes": [],
            "leases": [],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_mission(vault, "harbor-api")
    assert exc.value.code == "ESTATE_AUTHORIZATION_CLAIMED"


def test_cross_project_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign", "nodes": [], "leases": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_mission(vault, "harbor-api")
    assert exc.value.code == "CROSS_PROJECT"


def test_cli_mission(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["mission", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert payload["self_merge"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["mission", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    collapsed = " ".join(help_text.split())
    assert "must not self-merge" in collapsed
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/mission.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "from project_atlas.orchestration",
    ):
        assert name not in source
