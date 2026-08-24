"""D-148 — authentic estate credential preflight."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.authentic_estate import (
    d148_evidence_applies,
    estate_fingerprint,
    run_estate_preflight,
)
from project_atlas.orchestration.autonomy.exact_main_closure import reject_mixed_head_tree_packet


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "estate"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: sample\n  name: Sample\nproject_uuid: "
        "00000000-0000-4000-8000-000000000001\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_estate_preflight_passes_clean_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    preflight = run_estate_preflight(repo)
    assert preflight.preflight_pass
    assert preflight.project_id == "sample"


def test_estate_preflight_fails_malformed_marker(tmp_path: Path) -> None:
    repo = tmp_path / "estate"
    repo.mkdir()
    (repo / ".atlas-project.yaml").write_text("not: valid: yaml: [[", encoding="utf-8")
    preflight = run_estate_preflight(repo)
    assert not preflight.preflight_pass
    assert preflight.project_id is None


def test_reject_malformed_hash(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert reject_mixed_head_tree_packet("short", "also-short", repo)


def test_estate_fingerprint_changes_when_document_changes(tmp_path: Path) -> None:
    """Marker-only hashes must not survive a corpus edit (D-148/D-150)."""
    repo = _init_repo(tmp_path)
    before = estate_fingerprint(repo)
    (repo / "README.md").write_text("hello — edited corpus\n", encoding="utf-8")
    after = estate_fingerprint(repo)
    assert before
    assert before != after
    marker = (repo / ".atlas-project.yaml").read_text(encoding="utf-8")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    assert estate_fingerprint(repo) == before
    (repo / ".atlas-project.yaml").write_text(marker, encoding="utf-8")
    assert estate_fingerprint(repo) == before


def _bound_evidence(estate: Path, *, head: str, fingerprint: str | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "live_main_head": head,
        "AUTHENTIC_ESTATE_ROOT": str(estate.resolve()),
        "AUTHENTIC_INGEST_SATISFIED": True,
    }
    if fingerprint is not None:
        payload["estate_fingerprint"] = fingerprint
    return payload


def test_d148_evidence_requires_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-149R2/R3: cert without estate_fingerprint cannot stay current."""
    estate = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estate,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))
    evidence = _bound_evidence(estate, head=head, fingerprint=None)
    assert d148_evidence_applies(evidence, head, estate) is False


def test_d148_evidence_rejects_empty_current_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marker removed → current fingerprint empty → stale cert rejected."""
    estate = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estate,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fingerprint = estate_fingerprint(estate)
    assert fingerprint
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))
    (estate / ".atlas-project.yaml").unlink()
    evidence = _bound_evidence(estate, head=head, fingerprint=fingerprint)
    assert d148_evidence_applies(evidence, head, estate) is False


def test_d148_evidence_rejects_fingerprint_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estate,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))
    evidence = _bound_evidence(estate, head=head, fingerprint="0" * 64)
    assert d148_evidence_applies(evidence, head, estate) is False


def test_d148_evidence_rejects_missing_estate_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estate,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))
    evidence = {
        "live_main_head": head,
        "estate_fingerprint": estate_fingerprint(estate),
        "AUTHENTIC_INGEST_SATISFIED": True,
    }
    assert d148_evidence_applies(evidence, head, estate) is False


def test_d148_evidence_accepts_bound_current_estate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=estate,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))
    evidence = _bound_evidence(estate, head=head, fingerprint=estate_fingerprint(estate))
    assert d148_evidence_applies(evidence, head, estate) is True
