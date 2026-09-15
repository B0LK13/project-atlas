"""AS-ADV-RELEASE-002 — clean-clone RC hardening (RELEASE CERTIFIED = NO)."""

from __future__ import annotations

from pathlib import Path

from project_atlas.adv_release_cert import (
    MATRIX_CASE_IDS,
    run_fixture_adv_release_certification,
)
from project_atlas.schema import validate_record


def test_as_adv_release_002_clean_clone_replay_passes(tmp_path: Path) -> None:
    report = run_fixture_adv_release_certification(
        tmp_path / "work",
        case_ids=("clean_clone_replay",),
    )
    validate_record(report, "adv-release-cert-report")
    assert report["release_certified"] is False
    assert report["estate_pilot_passed"] is False
    assert report["web_application_accepted"] is False
    assert report["package"] == "AS-ADV-RELEASE-001"
    assert "at" not in report["generated"]
    assert len(report["cases"]) == 1
    row = report["cases"][0]
    assert row["case_id"] == "clean_clone_replay"
    assert row["result"] == "pass", row
    assert report["status"] == "certified"


def test_as_adv_release_002_matrix_includes_clean_clone() -> None:
    assert "clean_clone_replay" in MATRIX_CASE_IDS


def test_as_adv_release_002_docs_describe_procedure() -> None:
    """Docs-as-spec: clean-clone prep procedure without RELEASE claim."""
    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs" / "AS-ADV-RELEASE-002-clean-clone.md").read_text(encoding="utf-8")
    assert "clean_clone_replay" in doc
    assert "identical" in doc.lower() or "shared" in doc.lower()
    assert "stable" in doc.lower()
    assert "RELEASE CERTIFIED = **NO**" in doc
    assert "release_certified: false" in doc
    assert "atlas adv certify" in doc
