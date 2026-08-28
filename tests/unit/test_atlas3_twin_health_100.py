"""AT3-100 — isolated twin health."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.twin_health import PACKAGE_ID, compile_twin_health


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "twin-health" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_twin_health(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["health_is_authority"] is False
    assert report["estate_availability_is_authorization"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_declared_signals(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "estate_available": True,
            "signals": [
                {
                    "signal_id": "ledger-present",
                    "state": "CURRENT",
                    "evidence_refs": ["ops:atlas3/ledger/harbor-api"],
                }
            ],
        },
    )
    report = compile_twin_health(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["estate_available"] is True
    assert report["estate_availability_is_authorization"] is False
    assert report["signals"][0]["state"] == "CURRENT"
    assert report["health_is_authority"] is False


def test_health_authority_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "harbor-api", "health_is_authority": True})
    with pytest.raises(Atlas3Error) as exc:
        compile_twin_health(vault, "harbor-api")
    assert exc.value.code == "HEALTH_AUTHORITY_CLAIMED"


def test_estate_authorization_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "estate_availability_is_authorization": True,
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_twin_health(vault, "harbor-api")
    assert exc.value.code == "ESTATE_IS_NOT_AUTHORIZATION"


def test_cross_project_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign", "signals": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_twin_health(vault, "harbor-api")
    assert exc.value.code == "CROSS_PROJECT"


def test_cli_twin_health(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["twin-health", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert payload["health_is_authority"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["twin-health", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "not authority" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/twin_health.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
    ):
        assert name not in source
