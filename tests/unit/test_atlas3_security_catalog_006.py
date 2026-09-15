"""AT3-006 — isolated program security catalog."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.security import THREATS
from project_atlas.atlas3.security_catalog import PACKAGE_ID, compile_security_catalog


def test_catalog_is_reviewed_not_certified() -> None:
    report = compile_security_catalog()
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "derived"
    assert report["reviewed"] is True
    assert report["catalog_is_scanner"] is False
    assert report["catalog_is_certification"] is False
    assert report["external_security_certification"] is False
    assert report["external_security_revalidation_required"] is True
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["new_cli_command"] is False
    assert report["threat_count"] == len(THREATS)
    assert "cross_project_contamination" in report["threats"]
    assert "authority_escalation" in report["threats"]


def test_certification_claim_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        compile_security_catalog({"external_security_certification": True})
    assert exc.value.code == "SECURITY_CERTIFICATION_CLAIMED"


def test_scanner_claim_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        compile_security_catalog({"catalog_is_scanner": True})
    assert exc.value.code == "CATALOG_IS_SCANNER"


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/security_catalog.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "add_parser",
    ):
        assert name not in source
