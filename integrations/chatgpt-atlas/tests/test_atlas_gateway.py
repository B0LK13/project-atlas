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


def test_evidence_fetch_bounds_oversized_provenance_lineages(tmp_path: Path) -> None:
    """VAL-269-A B1: evidence fetch must not dump unbounded vault-wide lineages."""
    vault = tmp_path / "vault"
    idx = vault / "generated" / "indexes"
    idx.mkdir(parents=True)
    huge = {
        "by_source_lineage_id": {f"lin-{i:05d}": ["harbor-api"] for i in range(5000)},
        "ids": ["e1"],
    }
    (idx / "provenance.json").write_text(json.dumps(huge), encoding="utf-8")

    result = gw.fetch(vault, "evidence:e1")
    sc = result.structured_content
    lineages = sc.get("provenance_lineages") or []
    assert sc["found"] is True
    assert len(lineages) <= gw.MAX_RESULTS
    # Must not leak the vault-wide lineage catalog for a single evidence id.
    assert set(lineages).isdisjoint({f"lin-{i:05d}" for i in range(5000)})
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
