"""AS-SEC-SCAN-INGESTION-STATE-JSON-ESC-001 — decoded document scalars must not persist.

``load_state`` + ``save_state`` rewrite ``ingestion/state/<project>.json``.
A JSON ``\\u0041KI…`` escape does not match ``scan_text`` on raw bytes,
but decode reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from listed P2 F5-B Core ``ingestion.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from internal import ingestion_state
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_save_state_omits_json_escaped_relative_path(tmp_path: Path) -> None:
    planted = json.dumps(
        {
            "schema_version": 1,
            "project_id": "demo",
            "documents": {
                "doc-1": {
                    "document_id": "doc-1",
                    "relative_path": "PLACEHOLDER",
                    "sha256": "a" * 64,
                    "state": "unchanged",
                }
            },
            "last_inventory_sha256": "b" * 64,
        }
    ).replace("PLACEHOLDER", ESC)
    path = tmp_path / "demo.json"
    path.write_text(planted + "\n", encoding="utf-8")
    assert TOKEN not in planted
    assert scan_text(planted) == []
    state = ingestion_state.load_state(path, "demo")
    assert state["documents"]["doc-1"]["relative_path"] == TOKEN
    ingestion_state.save_state(path, state)
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
    assert json.loads(written)["documents"]["doc-1"]["relative_path"] == "UNKNOWN"


def test_safe_relative_path_still_persists(tmp_path: Path) -> None:
    state = {
        "schema_version": 1,
        "project_id": "demo",
        "documents": {
            "doc-1": {
                "document_id": "doc-1",
                "relative_path": "docs/plan.md",
                "sha256": "a" * 64,
                "state": "unchanged",
            }
        },
        "last_inventory_sha256": "b" * 64,
    }
    path = tmp_path / "demo.json"
    ingestion_state.save_state(path, state)
    written = path.read_text(encoding="utf-8")
    assert json.loads(written)["documents"]["doc-1"]["relative_path"] == "docs/plan.md"
    assert TOKEN not in written
    assert scan_text(written) == []
