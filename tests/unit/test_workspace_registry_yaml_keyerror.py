"""Contain yaml.safe_load constructor KeyError in workspace-registry markers.

``_read_marker`` had no handler. ``atlas: !!bool nope`` leaked a bare
``KeyError`` out of ``build_dry_run_registry``. Corrupt markers must
quarantine, never mint a project UUID.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.workspace_registry import _read_marker, build_dry_run_registry

MALFORMED = "atlas: !!bool nope\n"


def test_read_marker_constructor_tag_returns_empty(tmp_path: Path) -> None:
    (tmp_path / ".atlas-project.yaml").write_text(MALFORMED, encoding="utf-8")
    assert _read_marker(tmp_path) == {}


def test_dry_run_quarantines_constructor_tag_marker(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".atlas-project.yaml").write_text(MALFORMED, encoding="utf-8")
    doc = build_dry_run_registry(explicit_roots=[root], vault_identity="fixture-vault")
    assert doc["projects"] == []
    assert doc["quarantine"][0]["reason"] == "missing_or_invalid_project_uuid"
