"""AS-SEC-SCAN-ATLAS3-MEMORY-PERSIST-JSON-ESC-001 — decoded item text must not persist.

``persist_search`` / ``run_memory_vertical`` wrote decoded item scalars to
``generated/ops/atlas3/memory/<project>/*.json``. A JSON ``\\u0041KI…``
escape does not match ``scan_text`` on raw bytes, but ``json.loads``
reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #836/#837 (project bind), #870
(forged authority), #988 (conversation-capture review rewrite), and
#985 (pulse/start answer persist).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.pipeline import run_memory_vertical
from project_atlas.atlas3.memory.search import persist_search, search_memory
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _escaped_item() -> dict[str, object]:
    raw = (
        '{"item_type":"claim_candidate","provider":"chatgpt",'
        '"conversation_id":"c1","freshness":"CURRENT",'
        f'"project_id":"harbor-api","text":"{ESC}"}}'
    )
    assert TOKEN not in raw
    assert scan_text(raw) == []
    item = json.loads(raw)
    assert item["text"] == TOKEN
    assert any(finding.pattern == "cloud-access-key" for finding in scan_text(item["text"]))
    return item


def test_persist_search_rejects_json_escaped_item_text(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    item = _escaped_item()
    result = search_memory([item], "claim", project_id="harbor-api")
    with pytest.raises(Atlas3Error) as exc:
        persist_search(vault, "harbor-api", result)
    assert exc.value.code == "SECRET_CONTENT"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "search.json"
    assert not path.exists()


def test_run_memory_vertical_rejects_json_escaped_item_text(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    item = _escaped_item()
    with pytest.raises(Atlas3Error) as exc:
        run_memory_vertical(
            vault,
            "harbor-api",
            provider_items=[item],
            stronger_evidence=[],
            current_state_text="PostgreSQL 15",
            query="claim",
        )
    assert exc.value.code == "SECRET_CONTENT"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "reconcile.json"
    assert not path.exists()


def test_safe_item_still_persists(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    items = [
        {
            "item_type": "claim_candidate",
            "text": "Project uses PostgreSQL 16",
            "provider": "chatgpt",
            "conversation_id": "c1",
            "message_id": "m1",
            "source_content_hash": "sha256:" + "a" * 64,
            "project_id": "harbor-api",
        }
    ]
    report = run_memory_vertical(
        vault,
        "harbor-api",
        provider_items=items,
        stronger_evidence=[],
        current_state_text="PostgreSQL 15",
        query="database",
    )
    assert report["project_id"] == "harbor-api"
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "reconcile.json"
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
