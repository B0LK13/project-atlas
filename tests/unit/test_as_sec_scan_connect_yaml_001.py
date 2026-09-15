"""AS-SEC-SCAN-CONNECT-YAML-001 — scan decoded YAML marker ids before bind persist."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import _marker_project_id, _write_bind
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"  # AKIA + 16 A — matches cloud-access-key


def _project_with_id(tmp_path: Path, raw_id_line: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".atlas-project.yaml").write_text(
        "schema_version: 1\n"
        "project:\n"
        f"  id: {raw_id_line}\n",
        encoding="utf-8",
    )
    return root


def test_quoted_unicode_escape_akia_is_not_bound(tmp_path: Path) -> None:
    raw_id = '"\\u0041KIAAAAAAAAAAAAAAAAA"'
    root = _project_with_id(tmp_path, raw_id)
    raw = (root / ".atlas-project.yaml").read_text(encoding="utf-8")
    assert scan_text(raw) == []
    assert TOKEN not in raw
    assert _marker_project_id(root) is None

    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write_bind(
        root,
        vault,
        "vault-1",
        project_ids=[TOKEN],
        primary_project_id=TOKEN,
    )
    persisted = path.read_text(encoding="utf-8")
    loaded = json.loads(persisted)
    assert TOKEN not in persisted
    assert loaded["project_id"] is None
    assert loaded["project_ids"] == []


def test_quoted_hex_escape_akia_is_not_bound(tmp_path: Path) -> None:
    raw_id = '"\\x41KIAAAAAAAAAAAAAAAAA"'
    root = _project_with_id(tmp_path, raw_id)
    raw = (root / ".atlas-project.yaml").read_text(encoding="utf-8")
    assert scan_text(raw) == []
    assert _marker_project_id(root) is None


def test_clean_marker_id_still_binds(tmp_path: Path) -> None:
    root = _project_with_id(tmp_path, "sample-estate")
    assert _marker_project_id(root) == "sample-estate"
    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write_bind(
        root,
        vault,
        "vault-1",
        project_ids=["sample-estate"],
        primary_project_id="sample-estate",
    )
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["project_id"] == "sample-estate"
    assert loaded["project_ids"] == ["sample-estate"]
    assert TOKEN not in json.dumps(loaded)
