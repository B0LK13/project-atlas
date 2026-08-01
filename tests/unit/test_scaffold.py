"""Unit tests for vault scaffold generation (FR-001, AT-001, AT-013 posture)."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.scaffold import (
    DIRECTORIES,
    ScaffoldError,
    build_plan,
    create_scaffold,
    validate_output_path,
)

EXPECTED_TOP_LEVEL = {
    "00-system",
    "01-portfolio",
    "projects",
    "capabilities",
    "infrastructure",
    "technologies",
    "decisions",
    "standards",
    "sources",
    "generated",
    "templates",
}


def test_plan_is_deterministic(tmp_path: Path) -> None:
    assert build_plan(tmp_path / "a") == build_plan(tmp_path / "a")


def test_scaffold_creates_expected_contract(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    plan = create_scaffold(root)

    top_level = {entry.name for entry in root.iterdir() if entry.is_dir()}
    assert top_level >= EXPECTED_TOP_LEVEL
    for directory in DIRECTORIES:
        assert (root / directory).is_dir(), directory
    for relative, _ in plan.files:
        assert (root / relative).is_file(), relative
    # AT-001: root structure and system notes
    assert (root / "index.md").is_file()
    assert (root / "00-system" / "vault-charter.md").is_file()
    assert (root / "00-system" / "taxonomy.md").is_file()


def test_scaffold_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    """NFR-001: scaffold generation is fully deterministic."""
    first = tmp_path / "vault-a"
    second = tmp_path / "vault-b"
    plan_a = create_scaffold(first)
    plan_b = create_scaffold(second)
    assert [rel for rel, _ in plan_a.files] == [rel for rel, _ in plan_b.files]
    for relative, _ in plan_a.files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes(), relative


def test_scaffold_files_carry_generation_metadata(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    create_scaffold(root)
    index = (root / "index.md").read_text(encoding="utf-8")
    assert "generated:" in index
    assert "by: agent:atlas-init" in index


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    plan = create_scaffold(root, dry_run=True)
    assert plan.files
    assert not root.exists()


def test_rejects_existing_non_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "existing.md").write_text("keep me", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="not empty"):
        create_scaffold(root)
    assert (root / "existing.md").read_text(encoding="utf-8") == "keep me"


def test_rejects_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "file.md"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="not a directory"):
        validate_output_path(target)


def test_rejects_home_directory() -> None:
    with pytest.raises(ScaffoldError, match="home"):
        validate_output_path(Path.home())


def test_rejects_filesystem_root() -> None:
    with pytest.raises(ScaffoldError, match="root"):
        validate_output_path(Path("/"))


def test_allows_empty_existing_directory(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    plan = create_scaffold(root)
    assert (root / "index.md").is_file()
    assert plan.root == root.resolve()
