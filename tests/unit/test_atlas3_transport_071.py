"""AT3-071 — isolated transport != authority prover."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.transport import PACKAGE_ID, prove_transport_is_not_authority


def test_http_200_is_not_authority() -> None:
    report = prove_transport_is_not_authority(surface="api", transport_status="200")
    assert report["package_id"] == PACKAGE_ID
    assert report["transport_reported_success"] is True
    assert report["transport_is_authority"] is False
    assert report["transport_success_is_authority"] is False
    assert report["certified_for_merge"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["write_applied"] is False


@pytest.mark.parametrize("status", ["0", "ok", "success", "ack", "PASS"])
def test_cli_mcp_a2a_success_is_not_authority(status: str) -> None:
    report = prove_transport_is_not_authority(surface="mcp", transport_status=status)
    assert report["transport_reported_success"] is True
    assert report["is_authority"] is False


def test_authority_claim_from_transport_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        prove_transport_is_not_authority(
            surface="cli",
            transport_status="0",
            authority_claim="authority",
        )
    assert exc.value.code == "TRANSPORT_IS_NOT_AUTHORITY"


@pytest.mark.parametrize(
    "claim",
    ["truth_core", "merge", "owner", "security", "release", "governor", "signoff"],
)
def test_owner_power_from_transport_fails_closed(claim: str) -> None:
    with pytest.raises(Atlas3Error) as exc:
        prove_transport_is_not_authority(
            surface="web",
            transport_status="200",
            authority_claim=claim,
        )
    assert exc.value.code == "TRANSPORT_IS_NOT_AUTHORITY"


def test_unknown_surface_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        prove_transport_is_not_authority(surface="slack", transport_status="200")
    assert exc.value.code == "SURFACE_UNKNOWN"


def test_missing_status_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        prove_transport_is_not_authority(surface="tui", transport_status="  ")
    assert exc.value.code == "TRANSPORT_STATUS_REQUIRED"


def test_cli_transport_authority(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(
        ["transport-authority", "--surface", "a2a", "--transport-status", "ack"]
    )
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["transport_is_authority"] is False
    assert payload["merge_authorization"] == "NOT_GRANTED"
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["transport-authority", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "not authority" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/transport.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "from project_atlas.api_server",
        "from project_atlas.mcp_server",
    ):
        assert name not in source
