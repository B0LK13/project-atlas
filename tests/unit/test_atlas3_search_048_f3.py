"""AT3-048-F3 — persist_search binds result.project_id to the persist target."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.search import persist_search


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "other-api").mkdir(parents=True)
    return vault


def test_foreign_result_project_id_does_not_persist(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        persist_search(
            vault,
            "harbor-api",
            {"extra": "payload", "project_id": "other-api"},
        )
    assert exc.value.code == "PROJECT_MISMATCH"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert not path.exists()


def test_matching_result_project_id_persists(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    persist_search(vault, "harbor-api", {"project_id": "harbor-api", "hits": []})
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert path.is_file()
