"""Derived Obsidian UX / workspace writers must not leak raw OSError.

AS-2.0-OBS-UX write boundary: ``build_obsidian_lens_registry`` and
``build_obsidian_workspace_binding`` write under ``generated/ops/obsidian/``.
On current main a file where a path component must be a directory leaked
``NotADirectoryError`` past ``ObsidianUxError`` / ``ObsidianWorkspaceError``.
Same class as F6/F11/F14, different writers -- do not mix into those PRs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.obsidian_ux import ObsidianUxError, build_obsidian_lens_registry
from project_atlas.obsidian_workspace import (
    ObsidianWorkspaceError,
    build_obsidian_workspace_binding,
)


def _blocked_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "generated").write_text("not-a-directory", encoding="utf-8")
    return vault


def test_lens_registry_blocked_parent_is_domain_error(tmp_path: Path) -> None:
    vault = _blocked_vault(tmp_path)
    with pytest.raises(ObsidianUxError, match="unwritable-derived-registry:") as caught:
        build_obsidian_lens_registry(vault, registry_id="demo-reg")
    assert not isinstance(caught.value, OSError)
    assert type(caught.value) is ObsidianUxError


def test_workspace_binding_blocked_parent_is_domain_error(tmp_path: Path) -> None:
    vault = _blocked_vault(tmp_path)
    with pytest.raises(
        ObsidianWorkspaceError, match="unwritable-derived-binding:"
    ) as caught:
        build_obsidian_workspace_binding(vault, record_id="demo-bind")
    assert not isinstance(caught.value, OSError)
    assert type(caught.value) is ObsidianWorkspaceError


def test_lens_registry_happy_path_still_writes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_obsidian_lens_registry(vault, registry_id="default")
    assert report["plugin_shipped"] is False
    assert (
        vault / "generated" / "ops" / "obsidian" / "default-lens-registry.json"
    ).is_file()


def test_workspace_binding_happy_path_still_writes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_obsidian_workspace_binding(vault, record_id="bind-a")
    assert report["plugin_shipped"] is False
    assert (vault / "generated" / "ops" / "obsidian" / "bind-a.json").is_file()
