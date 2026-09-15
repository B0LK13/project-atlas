"""AT3-110 — isolated multi-project twin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.multi_project import PACKAGE_ID, compile_multi_project_twin


def _vault(tmp_path: Path, *projects: str) -> Path:
    vault = tmp_path / "vault"
    names = projects or ("harbor-api",)
    for name in names:
        (vault / "projects" / name).mkdir(parents=True, exist_ok=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "multi-project" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_multi_project_twin(_vault(tmp_path))
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["federation_is_authority"] is False
    assert report["org_identity_minted"] is False
    assert report["counts"]["cross_project_leak"] == 0
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_declared_siblings(tmp_path: Path) -> None:
    vault = _vault(tmp_path, "harbor-api", "lighthouse")
    _write_declared(
        vault,
        {
            "projects": [
                {"project_id": "harbor-api", "evidence_refs": ["marker:harbor"]},
                {"project_id": "lighthouse", "evidence_refs": ["marker:light"]},
            ]
        },
    )
    report = compile_multi_project_twin(vault, requested_project_id="harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"projects": 2, "cross_project_leak": 0}
    assert [row["project_id"] for row in report["projects"]] == ["harbor-api", "lighthouse"]


def test_undeclared_request_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path, "harbor-api", "foreign")
    _write_declared(
        vault,
        {"projects": [{"project_id": "harbor-api", "evidence_refs": ["marker:harbor"]}]},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_multi_project_twin(vault, requested_project_id="foreign")
    assert exc.value.code == "CROSS_PROJECT"


def test_federation_authority_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"federation_is_authority": True, "projects": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_multi_project_twin(vault)
    assert exc.value.code == "FEDERATION_AUTHORITY_CLAIMED"


def test_cli_multi_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["multi-project-twin", "--vault", str(vault)])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert payload["org_identity_minted"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["multi-project-twin", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    collapsed = " ".join(help_text.split())
    assert "federation is not authority" in collapsed
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/multi_project.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "from project_atlas.federation",
    ):
        assert name not in source
