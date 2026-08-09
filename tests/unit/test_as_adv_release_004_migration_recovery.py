"""AS-ADV-RELEASE-004 migration/recovery RC tests (RELEASE = NO)."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.adv_release_cert import (
    MATRIX_CASE_IDS,
    run_fixture_adv_release_certification,
)
from project_atlas.schema import validate_record


def test_as_adv_release_004_migration_recovery_replay_passes(
    tmp_path: Path,
) -> None:
    report = run_fixture_adv_release_certification(
        tmp_path / "work", case_ids=("migration_recovery_replay",)
    )
    validate_record(report, "adv-release-cert-report")
    assert report["release_certified"] is False
    assert report["estate_pilot_passed"] is False
    assert report["web_application_accepted"] is False
    row = report["cases"][0]
    assert row["case_id"] == "migration_recovery_replay"
    assert row["result"] == "pass", row
    observed = json.loads(row["observed"])
    assert observed["orphan_count"] == 1
    assert observed["transactions_recovered"] == 1
    assert observed["stage_removed"] is True
    assert observed["canonical_preserved"] is True
    assert observed["second_orphan_count"] == 0
    assert observed["drift"] == []
    assert observed["baseline"] == observed["replayed"]


def test_as_adv_release_004_recovery_signals_repeat_exactly(
    tmp_path: Path,
) -> None:
    first = run_fixture_adv_release_certification(
        tmp_path / "first", case_ids=("migration_recovery_replay",)
    )
    second = run_fixture_adv_release_certification(
        tmp_path / "second", case_ids=("migration_recovery_replay",)
    )
    assert first["cases"][0]["observed"] == second["cases"][0]["observed"]
    assert first["release_certified"] is False
    assert second["release_certified"] is False


def test_as_adv_release_004_matrix_and_docs_keep_release_no() -> None:
    assert "migration_recovery_replay" in MATRIX_CASE_IDS
    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs" / "AS-ADV-RELEASE-004-migration-recovery.md").read_text(
        encoding="utf-8"
    )
    assert "migration_recovery_replay" in doc
    assert "RELEASE = **NO**" in doc
    assert "RELEASE CERTIFIED = **NO**" in doc
    assert "release_certified: false" in doc
    assert "recover_promote_orphans" in doc
