"""AT3-012 — isolated service / environment nodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.estate_nodes import PACKAGE_ID, compile_estate_nodes


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "estate-nodes" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_estate_nodes(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_estate_nodes(_vault(tmp_path), "harbor-api")
    assert report["package"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["authentic_estate"] is False
    assert report["estate_availability_is_owner_authority"] is False
    assert report["promoted_to_truth_core"] == 0


def test_declared_services_and_environments(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "services": [{"id": "api", "evidence_refs": ["doc:compose.yml#api"]}],
            "environments": [{"id": "local", "evidence_refs": ["doc:compose.yml#local"]}],
        },
    )
    report = compile_estate_nodes(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"services": 1, "environments": 1}
    assert report["authentic_estate"] is False


def test_cross_project_corrupt_and_authority_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign"})
    with pytest.raises(Atlas3Error) as cross:
        compile_estate_nodes(vault, "harbor-api")
    assert cross.value.code == "CROSS_PROJECT"
    path = vault / "generated" / "ops" / "atlas3" / "estate-nodes" / "harbor-api" / "declared.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(Atlas3Error) as corrupt:
        compile_estate_nodes(vault, "harbor-api")
    assert corrupt.value.code == "ESTATE_NODES_CORRUPT"
    _write_declared(vault, {"project_id": "harbor-api", "authentic_estate": True})
    with pytest.raises(Atlas3Error) as claimed:
        compile_estate_nodes(vault, "harbor-api")
    assert claimed.value.code == "ESTATE_NODES_AUTHORITY_CLAIMED"


def test_cli_estate_nodes_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["estate-nodes", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["estate-nodes", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "authentic estate" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_copy_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/estate_nodes.py").read_text(encoding="utf-8")
    for name in (
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "shutil",
        "write_text(",
        "write_json_atomic",
    ):
        assert name not in source
