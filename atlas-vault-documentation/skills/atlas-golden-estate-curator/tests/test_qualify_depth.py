"""QUALIFY depth for cases the mixed estate does not assert.

Isolated fixtures cover name-based duplicate identity, lib/ stale docs,
and apps/ monorepo. DEFAULT_MODE stays DISCOVER_ONLY. No source mutations.
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from curator import DEFAULT_MODE, curate  # noqa: E402
from estate import (  # noqa: E402
    build_apps_monorepo_estate,
    build_name_duplicate_estate,
    build_stale_lib_docs_estate,
    fingerprint,
)


def _by_name(report: dict, name: str) -> dict:
    return next(item for item in report["inventory"] if item["name"] == name)


def _qualify(report: dict, path: str) -> dict:
    return next(item for item in report["qualification"] if item["path"] == path)


def test_default_mode_remains_discover_only() -> None:
    assert DEFAULT_MODE == "DISCOVER_ONLY"


def test_name_duplicate_identity_excludes_second(tmp_path: Path) -> None:
    source = build_name_duplicate_estate(tmp_path / "name-dup")
    before = fingerprint(source)
    report = curate(source, phase="RECOMMEND", output=tmp_path / "name-dup.json")
    assert fingerprint(source) == before
    assert report["mode"] == "DISCOVER_ONLY"
    assert report["source_mutations"] == 0
    widgets = [item for item in report["inventory"] if item["identity"] == "widget"]
    assert len(widgets) == 2
    assert {item["path"] for item in widgets} == {"group-a/widget", "group-b/widget"}
    flagged = [item for item in widgets if item["duplicate_identity"]]
    kept = [item for item in widgets if not item["duplicate_identity"]]
    assert len(flagged) == 1
    assert len(kept) == 1
    assert flagged[0]["duplicate_of"] == kept[0]["path"]
    excluded = _qualify(report, flagged[0]["path"])
    golden = _qualify(report, kept[0]["path"])
    assert excluded["excluded"] is True
    assert "DUPLICATE_IDENTITY" in excluded["blockers"]
    assert excluded["golden_candidate"] is False
    assert golden["golden_candidate"] is True
    assert kept[0]["path"] in report["recommendation"]["recommended_golden_set"]
    assert flagged[0]["path"] in report["recommendation"]["security_exclusions"]
    assert report["recommendation"]["copy_authorized"] is False
    assert report["recommendation"]["goldenize_authorized"] is False


def test_stale_lib_docs_is_challenge_not_excluded(tmp_path: Path) -> None:
    source = build_stale_lib_docs_estate(tmp_path / "stale-lib")
    before = fingerprint(source)
    report = curate(source, phase="QUALIFY", output=tmp_path / "stale-lib.json")
    assert fingerprint(source) == before
    assert report["mode"] == "DISCOVER_ONLY"
    assert report["source_mutations"] == 0
    project = _by_name(report, "stale-lib-docs")
    assert project["stale_docs"] is True
    assert project["dirty_worktree"] is False
    assert project["missing_readme"] is False
    row = _qualify(report, project["path"])
    assert row["signals"]["stale_docs"] is True
    assert row["challenge_candidate"] is True
    assert row["golden_candidate"] is False
    assert row["excluded"] is False
    # ATLAS-GOLDEN-ESTATE-INVENTORY-HONESTY-001: stale_docs clears
    # golden_candidate (QUALIFICATION.md; closes the #513 dual-class leak).
    assert project["path"] in report["recommendation"]["recommended_challenge_set"]
    assert project["path"] not in report["recommendation"]["recommended_golden_set"]
    assert project["path"] not in report["recommendation"]["security_exclusions"]


def test_apps_monorepo_is_recorded_not_excluded(tmp_path: Path) -> None:
    source = build_apps_monorepo_estate(tmp_path / "apps-mono")
    before = fingerprint(source)
    report = curate(source, phase="RECOMMEND", output=tmp_path / "apps-mono.json")
    assert fingerprint(source) == before
    assert report["mode"] == "DISCOVER_ONLY"
    assert report["source_mutations"] == 0
    project = _by_name(report, "apps-monorepo")
    assert project["monorepo"] is True
    assert project["kind"] == "git"
    assert project["nested_repo"] is False
    row = _qualify(report, project["path"])
    assert row["signals"]["monorepo"] is True
    assert row["excluded"] is False
    assert row["golden_candidate"] is True
    assert project["path"] in report["recommendation"]["recommended_golden_set"]
    assert project["path"] not in report["recommendation"]["security_exclusions"]
    assert report["recommendation"]["copy_authorized"] is False
    assert report["owner_gate"] == "STOP"
