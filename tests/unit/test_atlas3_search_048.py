"""AT3-048 — Unified LLM memory search."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.search import (
    PACKAGE_ID,
    search_capability,
    search_memory,
)


def test_capability_is_not_transcript_dump() -> None:
    cap = search_capability()
    assert cap["package"] == PACKAGE_ID
    assert cap["transcript_dump"] is False
    assert cap["provenance_preserved"] is True
    assert cap["cross_project_search"] is False


def test_search_hits_extracted_items_only() -> None:
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
    assert result["transcript_dump"] is False
    assert result["hits"][0]["authority"] == "NON_CANONICAL"


def test_cross_project_search_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory(
            [
                {"text": "a", "project_id": "harbor-api"},
                {"text": "b", "project_id": "other-api"},
            ],
            "a",
        )
    assert exc.value.code == "PROJECT_MISMATCH"


def test_mixed_valid_and_corrupt_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory([{"text": "ok", "project_id": "harbor-api"}, "corrupt"], "ok")  # type: ignore[list-item]
    assert exc.value.code == "SEARCH_INVALID"


def test_module_does_not_touch_2x_bridges() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/memory/search.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.chatgpt_bridge",
        "from project_atlas.knowledge_compiler",
    ):
        assert name not in source
