"""AT3-111 — isolated org identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.org_identity import PACKAGE_ID, compile_org_identity


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "org-identity" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_org_identity(_vault(tmp_path))
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["org_id"] is None
    assert report["org_identity_minted"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_declared_org_is_not_minted(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"org_id": "acme-portfolio"})
    report = compile_org_identity(vault)
    assert report["status"] == "derived"
    assert report["org_id"] == "acme-portfolio"
    assert report["org_identity_minted"] is False


def test_mint_claim_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"org_id": "acme", "minted": True})
    with pytest.raises(Atlas3Error) as exc:
        compile_org_identity(vault)
    assert exc.value.code == "ORG_IDENTITY_MINTED"


def test_cli_org_identity(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["org-identity", "--vault", str(vault)])
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
        parser.parse_args(["org-identity", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    collapsed = " ".join(help_text.split())
    assert "does not mint" in collapsed
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/org_identity.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "uuid4",
    ):
        assert name not in source
