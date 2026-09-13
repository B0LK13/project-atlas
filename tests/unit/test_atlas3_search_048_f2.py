"""AT3-048-F2 — persist_search must bind hits to the requested project."""

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


def test_foreign_hit_does_not_persist_under_requested_project(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        persist_search(
            vault,
            "harbor-api",
            {
                "hits": [
                    {"text": "foreign secret postgres 16", "project_id": "other-api"}
                ]
            },
        )
    assert exc.value.code == "PROJECT_MISMATCH"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert not path.exists()


def test_missing_hit_project_id_does_not_persist(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        persist_search(
            vault,
            "harbor-api",
            {"hits": [{"text": "unscoped postgres"}]},
        )
    assert exc.value.code == "PROJECT_MISMATCH"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert not path.exists()


def test_matching_hit_persists(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    result = persist_search(
        vault,
        "harbor-api",
        {"hits": [{"text": "harbor postgres 15", "project_id": "harbor-api"}]},
    )
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert path.is_file()
    assert result["hits"][0]["project_id"] == "harbor-api"
