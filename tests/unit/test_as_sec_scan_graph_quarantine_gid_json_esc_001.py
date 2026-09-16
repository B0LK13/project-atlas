"""AS-SEC-SCAN-GRAPH-QUARANTINE-GID-JSON-ESC-001 — decoded Graphify ids must not persist.

``write_quarantine_outputs`` wrote decoded Graphify ids to
``generated/graph/quarantine/<project>/gq-*.json``. A JSON ``\\u0041KI…``
escape does not match ``scan_text`` on raw bytes, but ``json.loads``
reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #983
(AS-SEC-SCAN-GRAPH-REL-GID-JSON-ESC-001), which only covers
``generated/graph/relationship-quarantine/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.graph_quarantine import (
    materialize_from_candidates,
    write_quarantine_outputs,
)
from project_atlas.graph_relationships import RelationshipQuarantine
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_json_unicode_escape_source_graphify_id_is_not_persisted(tmp_path: Path) -> None:
    raw = f'{{"source":"{ESC}","target":"node-b","type":"depends-on"}}'
    assert TOKEN not in raw
    assert scan_text(raw) == []
    decoded = json.loads(raw)
    assert decoded["source"] == TOKEN
    assert any(finding.pattern == "cloud-access-key" for finding in scan_text(decoded["source"]))

    vault = tmp_path / "vault"
    vault.mkdir()
    candidate = RelationshipQuarantine(
        project_id="demo",
        candidate_id="qrel-edge-index-0-orphaned-endpoint",
        category="orphaned-endpoint",
        reason="missing target",
        source_graphify_id=decoded["source"],
        target_graphify_id="node-b",
        graphify_edge_ids=("e1",),
    )
    result = materialize_from_candidates([candidate], project_id="demo")
    written = write_quarantine_outputs(result, vault=vault)
    assert written
    for relative in written:
        text = (vault / relative).read_text(encoding="utf-8")
        assert TOKEN not in text
        assert scan_text(text) == []
    record_paths = [
        relative
        for relative in written
        if "/quarantine/" in relative and not relative.endswith("/receipt.json")
    ]
    assert record_paths
    payload = json.loads((vault / record_paths[0]).read_text(encoding="utf-8"))
    assert payload["source_graphify_id"] != TOKEN
    assert payload["source_graphify_id"] == "UNKNOWN"


def test_safe_graphify_id_still_persists(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    candidate = RelationshipQuarantine(
        project_id="demo",
        candidate_id="qrel-edge-index-0-orphaned-endpoint",
        category="orphaned-endpoint",
        reason="missing target",
        source_graphify_id="api",
        target_graphify_id="missing",
        graphify_edge_ids=("orphan",),
    )
    result = materialize_from_candidates([candidate], project_id="demo")
    written = write_quarantine_outputs(result, vault=vault)
    record_paths = [
        relative
        for relative in written
        if "/quarantine/" in relative and not relative.endswith("/receipt.json")
    ]
    payload = json.loads((vault / record_paths[0]).read_text(encoding="utf-8"))
    assert payload["source_graphify_id"] == "api"
    assert payload["target_graphify_id"] == "missing"
    assert TOKEN not in json.dumps(payload)
