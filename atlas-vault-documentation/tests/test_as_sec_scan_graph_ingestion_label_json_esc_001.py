"""AS-SEC-SCAN-GRAPH-INGESTION-LABEL-JSON-ESC-001 — decoded labels must not persist.

Graphify ``json.loads`` decodes node labels; ``GraphNode.as_dict`` is
written to ``relationships/state/<project>.json`` and
``relationships/nodes/<project>.jsonl``. A JSON ``\\u0041KI…`` escape
does not match ``scan_text`` on raw bytes, but decode reveals
``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #953 / #983 / #991 (Core graph ids).
"""

from __future__ import annotations

import json

from internal.graph_node import GraphNode
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_as_dict_omits_json_escaped_label() -> None:
    raw = '{"label":"' + ESC + '"}'
    assert TOKEN not in raw
    assert scan_text(raw) == []
    decoded = json.loads(raw)["label"]
    assert decoded == TOKEN
    node = GraphNode(
        node_id="n1",
        project_id="demo",
        source_artifact_id="art-1",
        artifact_sha256="a" * 64,
        record_index=0,
        entity_type="component",
        label=decoded,
        atlas_entity_id="demo:n1",
        resolution_status="resolved",
        resolution_method="graphify_stable",
        confidence="high",
    )
    payload = node.as_dict()
    written = json.dumps(payload)
    assert TOKEN not in written
    assert scan_text(written) == []
    assert payload["entity"]["label"] == "UNKNOWN"


def test_as_dict_omits_json_escaped_attribute() -> None:
    raw = '{"description":"' + ESC + '"}'
    assert scan_text(raw) == []
    decoded = json.loads(raw)["description"]
    node = GraphNode(
        node_id="n1",
        project_id="demo",
        source_artifact_id="art-1",
        artifact_sha256="a" * 64,
        record_index=0,
        entity_type="component",
        label="api",
        atlas_entity_id="demo:n1",
        resolution_status="resolved",
        resolution_method="graphify_stable",
        confidence="high",
        attributes={"description": decoded},
    )
    written = json.dumps(node.as_dict())
    assert TOKEN not in written
    assert node.as_dict()["attributes"]["description"] == "UNKNOWN"


def test_quarantine_record_omits_json_escaped_note() -> None:
    from internal import graph_quarantine

    raw = '{"note":"' + ESC + '"}'
    assert scan_text(raw) == []
    payload = graph_quarantine.record(
        "demo",
        "orphaned",
        json.loads(raw),
        artifact_id="art-1",
        message="edge endpoint cannot be resolved",
    )
    written = json.dumps(payload)
    assert TOKEN not in written
    assert payload["record"]["note"] == "UNKNOWN"


def test_state_object_key_omits_json_escaped_node_id() -> None:
    from internal.graph_node import safe_persist

    raw = '{"id":"' + ESC + '"}'
    assert scan_text(raw) == []
    node_id = json.loads(raw)["id"]
    assert node_id == TOKEN
    state = safe_persist({"nodes": {node_id: {"label": "api"}}})
    written = json.dumps(state)
    assert TOKEN not in written
    assert "UNKNOWN" in state["nodes"]


def test_safe_label_still_serializes() -> None:
    node = GraphNode(
        node_id="n1",
        project_id="demo",
        source_artifact_id="art-1",
        artifact_sha256="a" * 64,
        record_index=0,
        entity_type="component",
        label="api",
        atlas_entity_id="demo:n1",
        resolution_status="resolved",
        resolution_method="graphify_stable",
        confidence="high",
    )
    payload = node.as_dict()
    assert payload["entity"]["label"] == "api"
    assert TOKEN not in json.dumps(payload)
    assert scan_text(json.dumps(payload)) == []
