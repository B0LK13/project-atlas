"""AT3-048-F4 — forged Truth Core authority is not a search hit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.search import persist_search, search_memory


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_forged_truth_core_authority_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        search_memory(
            [
                {
                    "project_id": "harbor-api",
                    "text": "postgres",
                    "item_type": "observation",
                    "authority": "TRUTH_CORE",
                }
            ],
            "postgres",
            project_id="harbor-api",
        )
    assert exc.value.code == "AUTHORITY_CLAIM_FORBIDDEN"


def test_owner_and_merge_authority_labels_fail_closed() -> None:
    for label in ("OWNER", "MERGE", "GOVERNOR", "derived"):
        with pytest.raises(Atlas3Error) as exc:
            search_memory(
                [
                    {
                        "project_id": "harbor-api",
                        "text": "postgres",
                        "item_type": "observation",
                        "authority": label,
                    }
                ],
                "postgres",
                project_id="harbor-api",
            )
        assert exc.value.code == "AUTHORITY_CLAIM_FORBIDDEN"


def test_missing_authority_defaults_to_non_canonical() -> None:
    result = search_memory(
        [
            {
                "project_id": "harbor-api",
                "text": "postgres",
                "item_type": "observation",
            }
        ],
        "postgres",
        project_id="harbor-api",
    )
    assert result["hit_count"] == 1
    assert result["hits"][0]["authority"] == "NON_CANONICAL"


def test_persist_search_rejects_forged_truth_core(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as exc:
        persist_search(
            vault,
            "harbor-api",
            {
                "package": "AT3-048",
                "hits": [{"text": "postgres", "authority": "TRUTH_CORE"}],
            },
        )
    assert exc.value.code == "AUTHORITY_CLAIM_FORBIDDEN"
    search_path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert not search_path.exists()


def test_persist_search_keeps_non_canonical(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    result = persist_search(
        vault,
        "harbor-api",
        {
            "package": "AT3-048",
            "hits": [{"text": "postgres", "authority": "NON_CANONICAL"}],
        },
    )
    search_path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    persisted = json.loads(search_path.read_text(encoding="utf-8"))
    assert result["hits"][0]["authority"] == "NON_CANONICAL"
    assert persisted["hits"][0]["authority"] == "NON_CANONICAL"
