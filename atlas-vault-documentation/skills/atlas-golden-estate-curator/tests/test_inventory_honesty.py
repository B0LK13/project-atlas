"""ATLAS-GOLDEN-ESTATE-INVENTORY-HONESTY-001.

Mixed-estate paths must map to golden/challenge/excluded per QUALIFICATION.md.
stale_docs clears golden_candidate (closes the #513 dual-class leak).
DEFAULT_MODE stays DISCOVER_ONLY. source_mutations == 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SKILL = Path(__file__).resolve().parents[1]
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from curator import DEFAULT_MODE, curate  # noqa: E402
from estate import (  # noqa: E402
    build_content_only_secret_estate,
    build_malicious_build_sh_name_estate,
    build_stale_app_docs_estate,
    fingerprint,
)


def _qualification_class(project: dict[str, Any]) -> str:
    """Map inventory signals to QUALIFICATION.md buckets."""
    if (
        project.get("secret_findings")
        or project.get("malicious_build_script")
        or project.get("duplicate_identity")
        or project.get("nested_repo")
        or project.get("inspection_complete") is False
    ):
        return "excluded"
    if (
        project.get("dirty_worktree")
        or project.get("missing_readme")
        or project.get("stale_docs")
        or project.get("test_failure_signal")
        or project.get("build_failure_signal")
        or project.get("kind") == "non-git"
    ):
        return "challenge"
    if project.get("kind") == "git":
        return "golden"
    return "challenge"


def _row_class(row: dict[str, Any]) -> str:
    flags = (
        bool(row["golden_candidate"]),
        bool(row["challenge_candidate"]),
        bool(row["excluded"]),
    )
    assert flags.count(True) == 1, f"dual-class leak for {row.get('path')}: {flags}"
    if row["excluded"]:
        return "excluded"
    if row["challenge_candidate"]:
        return "challenge"
    return "golden"


def test_mixed_estate_qualification_mapping(
    tmp_path: Path, fixture_estate: Path
) -> None:
    source = fixture_estate
    before = fingerprint(source)
    dest = tmp_path / "honesty.json"
    report = curate(source, phase="RECOMMEND", output=dest)
    assert fingerprint(source) == before

    assert DEFAULT_MODE == "DISCOVER_ONLY"
    assert report["mode"] == "DISCOVER_ONLY"
    assert report["phase_reached"] == "RECOMMEND"
    assert report["source_mutations"] == 0
    assert report["files_moved"] == 0
    assert report["files_deleted"] == 0
    assert report["owner_gate"] == "STOP"
    assert report["copy"] is False
    assert report["goldenize"] is False
    rec = report["recommendation"]
    assert rec["copy_authorized"] is False
    assert rec["goldenize_authorized"] is False
    assert rec["owner_gate"] == "STOP"

    assert report["candidate_table"] == report["qualification"]
    disk = report["disk_estimate"]
    assert disk["bytes"] > 0
    assert disk["files"] > 0
    generated = {Path(item).as_posix() for item in report["generated_directories"]}
    assert any(path.endswith("node_modules") or "/node_modules" in path for path in generated)
    assert "generated-dir/node_modules" in generated

    windows = report["windows_d_drive"]
    assert windows["authentic_test"] == "LOCAL_WINDOWS_REQUIRED"
    assert windows["cloud_certified"] is False

    assert dest.is_file()
    assert source not in dest.parents
    payload = json.dumps(report)
    assert "NOT_A_REAL_SECRET_VALUE" not in payload
    assert dest.read_text(encoding="utf-8").find("NOT_A_REAL_SECRET_VALUE") == -1

    by_path = {item["path"]: item for item in report["inventory"]}
    qual_by_path = {item["path"]: item for item in report["qualification"]}
    assert set(by_path) == set(qual_by_path)

    expected = {path: _qualification_class(item) for path, item in by_path.items()}
    observed = {path: _row_class(qual_by_path[path]) for path in by_path}
    assert observed == expected

    stale = next(item for item in report["inventory"] if item["name"] == "stale-docs")
    stale_row = qual_by_path[stale["path"]]
    assert stale["stale_docs"] is True
    assert stale_row["golden_candidate"] is False
    assert stale_row["challenge_candidate"] is True
    assert stale_row["excluded"] is False
    assert stale["path"] in rec["recommended_challenge_set"]
    assert stale["path"] not in rec["recommended_golden_set"]

    healthy = next(item for item in report["inventory"] if item["name"] == "healthy-git")
    assert _row_class(qual_by_path[healthy["path"]]) == "golden"
    assert healthy["path"] in rec["recommended_golden_set"]


def test_stale_app_docs_is_challenge_not_golden(tmp_path: Path) -> None:
    source = build_stale_app_docs_estate(tmp_path / "stale-app")
    before = fingerprint(source)
    report = curate(source, phase="RECOMMEND", output=tmp_path / "stale-app.json")
    assert fingerprint(source) == before
    assert report["source_mutations"] == 0
    project = next(item for item in report["inventory"] if item["name"] == "stale-app-docs")
    row = next(item for item in report["qualification"] if item["path"] == project["path"])
    assert project["stale_docs"] is True
    assert row["challenge_candidate"] is True
    assert row["golden_candidate"] is False
    assert row["excluded"] is False
    assert project["path"] in report["recommendation"]["recommended_challenge_set"]
    assert project["path"] not in report["recommendation"]["recommended_golden_set"]


def test_malicious_build_sh_name_excludes_and_does_not_execute(tmp_path: Path) -> None:
    source = build_malicious_build_sh_name_estate(tmp_path / "named-malice")
    before = fingerprint(source)
    report = curate(source, phase="RECOMMEND", output=tmp_path / "named-malice.json")
    assert fingerprint(source) == before
    assert report["source_mutations"] == 0
    project = next(item for item in report["inventory"] if item["name"] == "named-malice")
    row = next(item for item in report["qualification"] if item["path"] == project["path"])
    assert project["malicious_build_script"] is True
    assert project["executed_build"] is False
    assert row["excluded"] is True
    assert row["golden_candidate"] is False
    assert "MALICIOUS_BUILD_SCRIPT" in row["blockers"]
    assert project["path"] in report["recommendation"]["security_exclusions"]
    assert not (source / "named-malice" / "EXECUTED").exists()


def test_content_only_secret_excludes_without_echo(tmp_path: Path) -> None:
    source = build_content_only_secret_estate(tmp_path / "content-secret")
    before = fingerprint(source)
    dest = tmp_path / "content-secret.json"
    report = curate(source, phase="RECOMMEND", output=dest)
    assert fingerprint(source) == before
    assert report["source_mutations"] == 0
    project = next(item for item in report["inventory"] if item["name"] == "content-secret")
    row = next(item for item in report["qualification"] if item["path"] == project["path"])
    assert project["secret_findings"]
    assert all(hit["kind"] == "content" for hit in project["secret_findings"])
    assert all("path" in hit and "pattern" in hit for hit in project["secret_findings"])
    assert row["excluded"] is True
    assert "SECRET_PRESENT" in row["blockers"]
    payload = json.dumps(report)
    assert "NOT_A_REAL_KEY_MATERIAL" not in payload
    assert dest.read_text(encoding="utf-8").find("NOT_A_REAL_KEY_MATERIAL") == -1
    assert report["recommendation"]["copy_authorized"] is False
    assert report["recommendation"]["goldenize_authorized"] is False
