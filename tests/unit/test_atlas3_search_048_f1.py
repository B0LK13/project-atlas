"""AT3-048-F1 — missing project_id is not an unscoped search hit."""

from __future__ import annotations

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.search import search_memory


def test_missing_item_project_id_fails_closed_without_requested_scope() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory(
            [
                {"text": "harbor postgres 15", "project_id": "harbor-api"},
                {"text": "foreign secret postgres 16"},
            ],
            "secret",
        )
    assert exc.value.code == "PROJECT_MISMATCH"


def test_blank_item_project_id_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory(
            [
                {"text": "harbor postgres 15", "project_id": "harbor-api"},
                {"text": "foreign secret postgres 16", "project_id": "   "},
            ],
            "secret",
        )
    assert exc.value.code == "PROJECT_MISMATCH"


def test_requested_scope_still_rejects_missing_item_project_id() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory(
            [
                {"text": "harbor postgres 15", "project_id": "harbor-api"},
                {"text": "foreign secret postgres 16"},
            ],
            "secret",
            project_id="harbor-api",
        )
    assert exc.value.code == "PROJECT_MISMATCH"


def test_scoped_hit_carries_output_project_id() -> None:
    result = search_memory(
        [
            {
                "text": "production uses PostgreSQL 15",
                "item_type": "claim_candidate",
                "provider": "chatgpt",
                "project_id": "harbor-api",
                "authority": "NON_CANONICAL",
            }
        ],
        "postgres",
        project_id="harbor-api",
    )
    assert result["hit_count"] == 1
    assert result["hits"][0]["project_id"] == "harbor-api"
