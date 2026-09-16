"""AS-SEC-SCAN-ROUTING-STATE-TITLE-JSON-ESC-001 — decoded titles must not persist.

``load_state`` decodes ``routing/state/<project>.json`` via ``json.loads``
and ``serialize_state`` (used by ``atlas_router.route``) rewrites it.
A JSON ``\\u0041KI…`` escape does not match ``scan_text`` on raw bytes,
but decode reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #932 (failure-root confinement).
"""

from __future__ import annotations

import json
from pathlib import Path

from internal import routing_state
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_serialize_omits_json_escaped_title(tmp_path: Path) -> None:
    planted = json.dumps(
        {
            "schema_version": 1,
            "routed_events": {
                "e1": {
                    "normalized_sha256": "a" * 64,
                    "route_receipt": "r",
                    "routed_at": "t",
                    "work_package_id": "w",
                    "event_kind": "k",
                    "occurred_at": "t",
                    "title": "PLACEHOLDER",
                    "agent": "a",
                    "raw_sha256": "b" * 64,
                    "normalized_path": "n",
                    "raw_path": "p",
                    "status": "ok",
                }
            },
            "work_packages": {},
            "last_successful_transaction": None,
            "current_projection_hash": None,
        }
    ).replace("PLACEHOLDER", ESC)
    path = routing_state.state_path(tmp_path, "demo")
    path.write_text(planted + "\n", encoding="utf-8")
    assert TOKEN not in planted
    assert scan_text(planted) == []
    assert json.loads(planted)["routed_events"]["e1"]["title"] == TOKEN

    state = routing_state.load_state(tmp_path, "demo")
    written = routing_state.serialize_state(state)
    assert TOKEN not in written
    assert scan_text(written) == []
    assert json.loads(written)["routed_events"]["e1"]["title"] == "UNKNOWN"


def test_safe_title_still_serializes(tmp_path: Path) -> None:
    state = routing_state.ProjectRoutingState(project_id="demo")
    state.routed_events["e1"] = routing_state.RoutedEventRecord(
        event_id="e1",
        normalized_sha256="a" * 64,
        route_receipt="r",
        routed_at="t",
        work_package_id="w",
        event_kind="k",
        occurred_at="t",
        title="safe-title",
        agent="a",
        raw_sha256="b" * 64,
        normalized_path="n",
        raw_path="p",
        status="ok",
    )
    written = routing_state.serialize_state(state)
    assert json.loads(written)["routed_events"]["e1"]["title"] == "safe-title"
    assert TOKEN not in written
    assert scan_text(written) == []
