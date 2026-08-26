"""AT3-070 — isolated surface contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.surface import (
    PACKAGE_ID,
    SURFACES,
    compile_surface_contract,
    evaluate_surface_claim,
)


def test_catalog_lists_six_non_authoritative_surfaces() -> None:
    report = compile_surface_contract()
    assert report["package_id"] == PACKAGE_ID
    ids = {item["surface_id"] for item in report["surfaces"]}
    assert ids == set(SURFACES)
    assert report["surface_count"] == 6
    assert report["surface_is_authority"] is False
    assert report["transport_success_is_authority"] is False
    assert report["availability_is_authorization"] is False
    assert report["certified_for_merge"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["write_applied"] is False
    for item in report["surfaces"]:
        assert item["is_authority"] is False
        assert item["writes_truth_core"] is False
        assert item["availability_is_authorization"] is False


def test_projection_claim_is_accepted() -> None:
    report = evaluate_surface_claim(surface="cli", claim="projection")
    assert report["accepted"] is True
    assert report["is_authority"] is False
    assert report["surface_id"] == "cli"


def test_live_api_alias_maps_to_api() -> None:
    report = evaluate_surface_claim(surface="live_api", claim="transport")
    assert report["surface_id"] == "api"


def test_unknown_surface_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        evaluate_surface_claim(surface="slack", claim="projection")
    assert exc.value.code == "SURFACE_UNKNOWN"


def test_authority_claim_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        evaluate_surface_claim(surface="mcp", claim="authority")
    assert exc.value.code == "SURFACE_CLAIM_FORBIDDEN"


@pytest.mark.parametrize(
    "claim",
    ["truth_core", "merge", "owner", "security", "release", "governor", "signoff"],
)
def test_owner_power_claims_fail_closed(claim: str) -> None:
    with pytest.raises(Atlas3Error) as exc:
        evaluate_surface_claim(surface="web", claim=claim)
    assert exc.value.code == "SURFACE_CLAIM_FORBIDDEN"


def test_unknown_claim_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        evaluate_surface_claim(surface="tui", claim="canonical")
    assert exc.value.code == "SURFACE_CLAIM_UNKNOWN"


def test_http_200_does_not_become_authority() -> None:
    report = evaluate_surface_claim(
        surface="api",
        claim="transport",
        transport_status="200",
    )
    assert report["accepted"] is True
    assert report["transport_reported_success"] is True
    assert report["transport_success_is_authority"] is False
    assert report["certified_for_merge"] is False


def test_cli_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["surface-contract"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["surface_count"] == 6
    assert payload["merge_authorization"] == "NOT_GRANTED"
    assert all(ord(char) < 128 for char in rendered)


def test_cli_evaluate_claim(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(
        [
            "surface-contract",
            "--surface",
            "a2a",
            "--claim",
            "derived",
            "--transport-status",
            "ok",
        ]
    )
    assert dispatch_atlas3(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["surface_id"] == "a2a"
    assert payload["accepted"] is True
    assert payload["is_authority"] is False


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["surface-contract", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "not authority" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/surface.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "from project_atlas.api_server",
        "from project_atlas.mcp_server",
    ):
        assert name not in source
