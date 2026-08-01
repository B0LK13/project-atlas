"""Integration tests for the atlas CLI (A-007, FR-001)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas import __version__
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main

pytestmark = pytest.mark.integration


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == EXIT_OK
    assert "init" in capsys.readouterr().out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == EXIT_OK
    assert capsys.readouterr().out.strip() == f"project-atlas {__version__}"


def test_init_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "vault"
    assert main(["init", "--output", str(root), "--dry-run"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "would create" in out
    assert "index.md" in out
    assert not root.exists()


def test_init_creates_scaffold(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    assert main(["init", "--output", str(root)]) == EXIT_OK
    assert (root / "index.md").is_file()
    assert (root / "00-system" / "vault-charter.md").is_file()
    assert (root / "templates" / "project.md").is_file()


def test_init_rejects_non_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    assert main(["init", "--output", str(root)]) == EXIT_OK
    assert main(["init", "--output", str(root)]) == EXIT_ERROR


def test_init_rejects_unsafe_path(tmp_path: Path) -> None:
    target = tmp_path / "occupied.md"
    target.write_text("x", encoding="utf-8")
    assert main(["init", "--output", str(target)]) == EXIT_ERROR


def test_usage_error_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["init"])  # missing required --output
    assert excinfo.value.code == 2


def test_entry_point_installed(tmp_path: Path) -> None:
    """The console script works end to end when the package is installed."""
    script = Path(sys.prefix) / "bin" / "atlas"
    if not script.exists():
        pytest.skip("package not installed in this environment")
    result = subprocess.run(
        [str(script), "init", "--output", str(tmp_path / "vault"), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_OK
    assert "would create" in result.stdout
