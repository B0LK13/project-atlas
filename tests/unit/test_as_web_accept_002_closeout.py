"""AS-WEB-ACCEPT-002 knowledge/graph read adapters + fixture E2E gates.

Does NOT claim WEB APPLICATION ACCEPTED.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.web_api import (
    impact_graph_summary,
    list_knowledge_answers,
    list_projects,
    read_impact_graph,
    read_status,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_as_web_accept_002_knowledge_empty_is_honest(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert list_knowledge_answers(vault) == []


def test_as_web_accept_002_knowledge_lists_answers(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "answers" / "a1.json",
        {"answer_id": "ans-1", "subject": "proj", "field": "status", "value": "active"},
    )
    rows = list_knowledge_answers(vault)
    assert len(rows) == 1
    assert rows[0]["answer_id"] == "ans-1"
    assert rows[0]["has_value"] is True


def test_as_web_accept_002_graph_absent_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert read_impact_graph(vault) is None
    summary = impact_graph_summary(vault)
    assert summary["available"] is False
    assert summary["graph_authority"] is False


def test_as_web_accept_002_graph_summary_derived_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "indexes" / "impact-graph.json",
        {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"from": "a", "to": "b"}],
            "authority_plane": "derived",
            "note": "IMPACT GRAPH ≠ AUTOMATIC AUTHORITY",
        },
    )
    summary = impact_graph_summary(vault)
    assert summary["available"] is True
    assert summary["node_count"] == 2
    assert summary["edge_count"] == 1
    assert summary["graph_authority"] is False


def test_as_web_accept_002_fixture_e2e_read_bundle(tmp_path: Path) -> None:
    """Fixture E2E: projects + knowledge + graph + health read path (no browser)."""
    vault = tmp_path / "vault"
    (vault / "projects" / "fixture-a").mkdir(parents=True)
    (vault / "projects" / "fixture-a" / "project.md").write_text("# A\n", encoding="utf-8")
    _write(
        vault / ".atlas" / "vault.json",
        {"vault_id": "fixture-web", "vault_uuid": "fixture-uuid"},
    )
    _write(
        vault / "generated" / "answers" / "q1.json",
        {"answer_id": "q1", "subject": "fixture-a", "field": "title", "value": "A"},
    )
    _write(
        vault / "generated" / "indexes" / "impact-graph.json",
        {"nodes": [], "edges": [], "authority_plane": "derived"},
    )
    status = read_status(vault)
    assert status["ui_canonical"] is False
    assert status["graph_authority"] is False
    assert status["unknown_equals_healthy"] is False
    assert [p["project_id"] for p in list_projects(vault)] == ["fixture-a"]
    assert list_knowledge_answers(vault)[0]["answer_id"] == "q1"
    assert impact_graph_summary(vault)["graph_authority"] is False
