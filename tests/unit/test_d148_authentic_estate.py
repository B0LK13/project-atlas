"""D-148 — authentic estate credential preflight."""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_atlas.orchestration.autonomy.authentic_estate import run_estate_preflight
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
