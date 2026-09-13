"""AT3-081-F1 — mixed valid + non-object memory items fail closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.stale_conflict import compile_stale_conflict_intel


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_mixed_valid_and_corrupt_items_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_json(
        vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "reconcile.json",
        {
            "reconciliation": {
                "items": [
                    {
                        "project_id": "harbor-api",
                        "provider": "chatgpt",
                        "text": "PostgreSQL 15 is deployed",
                    },
                    "corrupt-row",
                ]
            }
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_stale_conflict_intel(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"


def test_mixed_valid_and_corrupt_stale_memories_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_json(
        vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "reconcile.json",
        {
            "reconciliation": {
                "items": [
                    {
                        "project_id": "harbor-api",
                        "provider": "chatgpt",
                        "text": "old",
                    }
                ],
                "stale_memories": [
                    {
                        "project_id": "harbor-api",
                        "provider": "chatgpt",
                        "text": "old",
                        "freshness": "STALE",
                    },
                    ["not-an-object"],
                ],
            }
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_stale_conflict_intel(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
