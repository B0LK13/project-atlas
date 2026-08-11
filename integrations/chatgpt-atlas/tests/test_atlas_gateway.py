"""ATLAS-FOR-CHATGPT-READONLY-001 gateway tests (journeys per directive S40).

Proves the read-only tools return genuine DEMO_FIXTURE data, preserve the Atlas
trust invariants, and never fabricate absent evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import atlas_gateway as gw
import pytest

EXPECTED_PROJECTS = {"harbor-api", "harbor-ops", "harbor-portal"}


def _invariants_ok(structured: dict) -> None:
    assert structured["source_class"] == "DEMO_FIXTURE"
    assert structured["authentic_pilot"] is False
    assert structured["graph_authority"] is False
    assert structured["llm_output_authority"] is False
    assert structured["unknown_equals_healthy"] is False


def test_search_lists_real_projects(demo_vault: Path) -> None:
    # Journey: "What projects does Atlas know about?"
    result = gw.search(demo_vault, "harbor")
    ids = {r["id"] for r in result.structured_content["results"] if r["type"] == "project"}
    assert ids >= EXPECTED_PROJECTS
    _invariants_ok(result.structured_content)
    assert result.structured_content["search_result_is_proven_claim"] is False


def test_project_status_is_real_and_bounded(demo_vault: Path) -> None:
    # Journey: "What does Atlas know about <project>?"
    result = gw.atlas_project_status(demo_vault, "harbor-api")
    sc = result.structured_content
    assert sc["project"] == "harbor-api"
    assert sc["concept_count"] >= 1
    assert sc["evidence_count"] >= 1
    assert isinstance(sc["dependencies"], list)
    assert isinstance(sc["dependents"], list)
    _invariants_ok(sc)


def test_graph_neighbors_real_relationship(demo_vault: Path) -> None:
    # Journey: "What depends on harbor-api?" -> harbor-portal (real derived edge).
    api = gw.atlas_graph_neighbors(demo_vault, "harbor-api")
    assert "harbor-portal" in api.structured_content["dependents"]
    portal = gw.atlas_graph_neighbors(demo_vault, "harbor-portal")
    assert "harbor-api" in portal.structured_content["dependencies"]
    _invariants_ok(api.structured_content)
    assert "AUTHORITY" in api.structured_content["note"]


def test_conflicts_and_unknowns_are_honest(demo_vault: Path) -> None:
    # Journey: "What conflicts?" / "What don't we know?" -> honest, never fabricated.
    result = gw.atlas_project_status(demo_vault, "harbor-api")
    sc = result.structured_content
    # This corpus has no compiler-detected conflicts: report 0 + explicit unknown.
    assert sc["conflict_count"] == 0
    assert "no_detected_conflicts" in sc["unknowns"]
    assert "no_compiled_answers" in sc["unknowns"]


def test_unknown_project_is_not_fabricated(demo_vault: Path) -> None:
    result = gw.atlas_project_status(demo_vault, "does-not-exist")
    assert result.structured_content["found"] is False
    assert "UNKNOWN" in result.content


def test_fetch_project_and_unknown_ref(demo_vault: Path) -> None:
    ok = gw.fetch(demo_vault, "project:harbor-ops")
    assert ok.structured_content["project"] == "harbor-ops"
    unknown = gw.fetch(demo_vault, "claim:claim-does-not-exist")
    assert unknown.structured_content["found"] is False


def test_fetch_rejects_malformed_ref(demo_vault: Path) -> None:
    with pytest.raises(gw.GatewayError):
        gw.fetch(demo_vault, "not-a-ref")


def test_all_tools_are_read_only() -> None:
    assert set(gw.TOOL_SPECS) == {"search", "fetch", "atlas_project_status", "atlas_graph_neighbors"}
    for name, spec in gw.TOOL_SPECS.items():
        ann = spec["annotations"]
        assert ann["readOnlyHint"] is True, name
        assert ann["destructiveHint"] is False, name
        assert ann["openWorldHint"] is False, name
        assert spec["outputTemplate"].startswith("ui://widget/"), name
    # No write/mutation verbs registered.
    forbidden = ("write", "ingest", "delete", "mutate", "create", "update", "run", "execute")
    for name in gw.TOOL_SPECS:
        assert not any(bad in name for bad in forbidden), name


def test_call_tool_dispatch_and_unknown(demo_vault: Path) -> None:
    r = gw.call_tool(demo_vault, "search", {"query": "harbor-ops"})
    assert any(x["id"] == "harbor-ops" for x in r.structured_content["results"])
    with pytest.raises(gw.GatewayError):
        gw.call_tool(demo_vault, "atlas_write", {})


def test_search_limit_is_bounded(demo_vault: Path) -> None:
    result = gw.search(demo_vault, "", limit=2)
    assert result.structured_content["result_count"] <= 2


def test_evidence_present_via_lineage_key(tmp_path: Path) -> None:
    """Evidence presence uses by_source_lineage_id (production provenance has no ids)."""
    vault = tmp_path / "vault"
    idx = vault / "generated" / "indexes"
    idx.mkdir(parents=True)
    (idx / "provenance.json").write_text(
        json.dumps(
            {
                "by_source_lineage_id": {"lin-abc": ["claim-1"]},
                "by_receipt_id": {"rcpt-1": ["claim-1"]},
            }
        ),
        encoding="utf-8",
    )
    ok = gw.fetch(vault, "evidence:lin-abc")
    assert ok.structured_content["found"] is True
    assert ok.structured_content["provenance_lineages"] == ["lin-abc"]
    missing = gw.fetch(vault, "evidence:lin-missing")
    assert missing.structured_content["found"] is False


def test_receipt_uses_provenance_by_receipt_id(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    idx = vault / "generated" / "indexes"
    idx.mkdir(parents=True)
    (idx / "provenance.json").write_text(
        json.dumps(
            {
                "by_source_lineage_id": {},
                "by_receipt_id": {"rcpt-xyz": ["claim-9"]},
            }
        ),
        encoding="utf-8",
    )
    ok = gw.fetch(vault, "receipt:rcpt-xyz")
    assert ok.structured_content["found"] is True
    assert "claim-9" in ok.structured_content["linked_record_ids"]


def test_knowledge_count_scoped_to_project(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    answers = vault / "generated" / "answers"
    answers.mkdir(parents=True)
    (vault / "projects").mkdir(parents=True)
    # Create two answer files; only one matches harbor-api.
    (answers / "a1.json").write_text(
        json.dumps(
            {
                "answer_id": "a1",
                "subject": "harbor-api status",
                "field": "state",
                "value": "active",
                "provenance": [{"source_lineage_id": "lin-1"}],
            }
        ),
        encoding="utf-8",
    )
    (answers / "a2.json").write_text(
        json.dumps(
            {
                "answer_id": "a2",
                "subject": "harbor-ops runbook",
                "field": "owner",
                "value": "ops",
            }
        ),
        encoding="utf-8",
    )
    # Project presence via projects/<id>/project.md pattern used by list_projects.
    for pid in ("harbor-api", "harbor-ops"):
        pdir = vault / "projects" / pid
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "project.md").write_text(f"# {pid}\n", encoding="utf-8")

    api = gw.atlas_project_status(vault, "harbor-api")
    ops = gw.atlas_project_status(vault, "harbor-ops")
    assert api.structured_content["knowledge_count"] == 1
    assert ops.structured_content["knowledge_count"] == 1
    # Projects with no matching answers must keep the honest unknown.
    alone = vault / "projects" / "harbor-alone"
    alone.mkdir(parents=True, exist_ok=True)
    (alone / "project.md").write_text("# harbor-alone\n", encoding="utf-8")
    lonely = gw.atlas_project_status(vault, "harbor-alone")
    assert lonely.structured_content["knowledge_count"] == 0
    assert "no_compiled_answers" in lonely.structured_content["unknowns"]


def test_fetch_knowledge_loads_document_value(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    answers = vault / "generated" / "answers"
    answers.mkdir(parents=True)
    (answers / "k1.json").write_text(
        json.dumps(
            {
                "answer_id": "k1",
                "subject": "harbor-api",
                "field": "purpose",
                "value": "serves API",
                "provenance": [{"source_lineage_id": "lin-k"}],
            }
        ),
        encoding="utf-8",
    )
    # list_knowledge_answers discovers the file; fetch should return value+provenance.
    result = gw.fetch(vault, "knowledge:k1")
    assert result.structured_content["found"] is True
    answer = result.structured_content["answer"]
    assert answer["value"] == "serves API"
    assert answer["provenance"][0]["source_lineage_id"] == "lin-k"


def test_evidence_fetch_bounds_oversized_provenance_lineages(tmp_path: Path) -> None:
    """VAL-269-A B1: evidence fetch must not dump unbounded vault-wide lineages."""
    vault = tmp_path / "vault"
    idx = vault / "generated" / "indexes"
    idx.mkdir(parents=True)
    huge = {
        "by_source_lineage_id": {f"lin-{i:05d}": ["harbor-api"] for i in range(5000)},
        "by_receipt_id": {},
    }
    (idx / "provenance.json").write_text(json.dumps(huge), encoding="utf-8")

    result = gw.fetch(vault, "evidence:lin-00001")
    sc = result.structured_content
    lineages = sc.get("provenance_lineages") or []
    assert sc["found"] is True
    assert lineages == ["lin-00001"]
    assert len(lineages) <= gw.MAX_RESULTS
    # Must not leak the vault-wide lineage catalog for a single evidence id.
    assert set(lineages).isdisjoint({f"lin-{i:05d}" for i in range(5000) if i != 1})
    payload = json.dumps(sc, sort_keys=True).encode("utf-8")
    assert len(payload) <= gw.MAX_RESPONSE_BYTES
    assert sc.get("error") != "response_too_large"


def test_seal_fail_closed_on_oversized_structured_content() -> None:
    """Hard byte budget replaces oversized payloads (no mid-object leak)."""
    oversized = {
        "blob": "x" * (gw.MAX_RESPONSE_BYTES + 1024),
        **gw.INVARIANTS,
    }
    sealed = gw._seal(oversized, "should not leak")
    sc = sealed.structured_content
    assert sc["error"] == "response_too_large"
    assert sc["truncated"] is True
    assert "blob" not in sc
    assert "xxxx" not in sealed.content
    assert len(json.dumps(sc, sort_keys=True).encode("utf-8")) <= gw.MAX_RESPONSE_BYTES
