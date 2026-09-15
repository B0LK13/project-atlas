"""AS-GRAPH-003 adversarial probes (ADV-G3 band).

Truth boundary: GRAPH RELATIONSHIP ≠ AUTOMATIC AUTHORITY.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import main
from project_atlas.graph_relationships import (
    AUTHORITY_LEVEL,
    TRUTH_BOUNDARY,
    ArtifactRef,
    GraphRelationshipError,
    normalize_edges,
    promote_relationship_path_forbidden,
    write_relationship_outputs,
)
from project_atlas.graph_resolution import ResolvedNode
from project_atlas.schema import validate_record

REF = ArtifactRef(relative_path="graphify-out/graph.json", sha256="a" * 64)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolved(graphify_id: str, entity_id: str) -> ResolvedNode:
    return ResolvedNode(
        project_id="demo",
        graphify_node_id=graphify_id,
        entity_class="unknown",
        resolution_step="graphify_stable",
        status="resolved",
        source_artifact_refs=({"relative_path": "n.jsonl", "sha256": "a" * 64},),
        resolved_entity_id=entity_id,
    )


def _quarantined(graphify_id: str, category: str) -> ResolvedNode:
    return ResolvedNode(
        project_id="demo",
        graphify_node_id=graphify_id,
        entity_class="unknown",
        resolution_step="none",
        status="quarantine_candidate",
        source_artifact_refs=({"relative_path": "n.jsonl", "sha256": "a" * 64},),
        quarantine_category=category,  # type: ignore[arg-type]
    )


def _forbidden_census(vault: Path) -> dict[str, tuple[int, str]]:
    relatives = (
        "claims/claim.json",
        "state/current-state/demo.json",
        "state/authoritative-state/demo.json",
        "relationships/nodes.json",
        "generated/query/cache.json",
        "state/global-entities/registry.json",
    )
    census: dict[str, tuple[int, str]] = {}
    for relative in relatives:
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text('{"sentinel":true}\n', encoding="utf-8")
        census[relative] = (path.stat().st_mtime_ns, _sha256(path))
    return census


def _assert_census_stable(vault: Path, before: dict[str, tuple[int, str]]) -> None:
    for relative, (mtime_ns, digest) in before.items():
        path = vault / relative
        assert path.stat().st_mtime_ns == mtime_ns
        assert _sha256(path) == digest


def test_adv_g3_030_edge_fanout_bomb_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _forbidden_census(vault)
    nodes = [_resolved("api", "demo:api"), _resolved("db", "demo:db")]
    edges = [
        {
            "id": f"e-{i}",
            "type": "depends-on",
            "source": "api",
            "target": "db",
            "_atlas_artifact_ref": REF.as_dict(),
        }
        for i in range(100)
    ]
    with pytest.raises(GraphRelationshipError, match="edge-capacity-exceeded"):
        normalize_edges(
            edges,
            project_id="demo",
            resolution=nodes,
            artifact_refs=[REF],
            max_edges=10,
        )
    assert not (vault / "generated" / "graph" / "relationships").exists()
    _assert_census_stable(vault, before)


def test_adv_g3_090_quarantine_endpoint_never_promoted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _forbidden_census(vault)
    nodes = [
        _resolved("api", "demo:api"),
        _quarantined("qnode", "unresolved-identity"),
    ]
    edges = [
        {
            "id": "leak",
            "type": "depends-on",
            "source": "api",
            "target": "qnode",
            "_atlas_artifact_ref": REF.as_dict(),
        }
    ]
    result = normalize_edges(edges, project_id="demo", resolution=nodes, artifact_refs=[REF])
    assert result.retained_count == 0
    assert result.quarantine[0].category == "quarantined-endpoint"
    written = write_relationship_outputs(result, vault=vault)
    assert all("relationship-quarantine" in rel for rel in written)
    assert not list((vault / "generated/graph/relationships").rglob("*.json"))
    _assert_census_stable(vault, before)


def test_adv_g3_091_cross_project_mixed_no_half_edge() -> None:
    nodes = [
        _resolved("local", "demo:local"),
        _quarantined("foreign", "cross-project-resolution-forbidden"),
    ]
    edges = [
        {
            "id": "x",
            "type": "depends-on",
            "source": "local",
            "target": "foreign",
            "_atlas_artifact_ref": REF.as_dict(),
        }
    ]
    result = normalize_edges(edges, project_id="demo", resolution=nodes, artifact_refs=[REF])
    assert result.retained_count == 0
    assert result.quarantine[0].category == "cross-project-endpoint"


def test_adv_g3_092_quarantine_jsonl_not_projected_as_edges(tmp_path: Path) -> None:
    """Quarantine emits are not retained relationships (projection contract)."""
    vault = tmp_path / "vault"
    vault.mkdir()
    nodes = [_resolved("api", "demo:api")]
    edges = [
        {
            "id": "orphan",
            "type": "depends-on",
            "source": "api",
            "target": "missing",
            "_atlas_artifact_ref": REF.as_dict(),
        }
    ]
    result = normalize_edges(edges, project_id="demo", resolution=nodes, artifact_refs=[REF])
    written = write_relationship_outputs(result, vault=vault)
    for rel in written:
        payload = json.loads((vault / rel).read_text(encoding="utf-8"))
        assert payload["status"] == "quarantine_candidate"
        assert payload.get("status") != "retained"
        validate_record(payload, "graph-relationship-quarantine")


def test_adv_g3_093_secret_reason_redacted() -> None:
    nodes = [_resolved("api", "demo:api")]
    edges = [
        {
            "id": "bad",
            "type": "depends-on",
            "source": "api",
            "target": "missing",
            "reason": "password=super-secret",
            "_atlas_artifact_ref": REF.as_dict(),
        }
    ]
    result = normalize_edges(edges, project_id="demo", resolution=nodes, artifact_refs=[REF])
    assert result.quarantined_count == 1
    reason = result.quarantine[0].reason
    assert reason == "redacted-sensitive-reason"
    assert "password=" not in reason.lower()
    assert "super-secret" not in reason


def test_adv_g3_authority_elevation_ignored() -> None:
    nodes = [_resolved("a", "demo:a"), _resolved("b", "demo:b")]
    edges = [
        {
            "id": "e",
            "type": "depends-on",
            "source": "a",
            "target": "b",
            "authority": {"level": "primary"},
            "confidence": "high",
            "source_documents": ["doc.md"],
            "_atlas_artifact_ref": REF.as_dict(),
        }
    ]
    result = normalize_edges(edges, project_id="demo", resolution=nodes, artifact_refs=[REF])
    payload = result.relationships[0].as_dict()
    assert payload["authority"]["level"] == AUTHORITY_LEVEL
    assert payload["link_quality"] == "verified"
    assert payload["truth_boundary"] == TRUTH_BOUNDARY
    # verified link quality must not be confused with domain authority.
    assert payload["authority"]["level"] != "primary"


def test_adv_g3_forbidden_write_prefixes() -> None:
    for relative in (
        "relationships/edge.json",
        "claims/x.json",
        "state/authoritative-state/x.json",
        "generated/query/cache.json",
        "generated/graph/resolved/demo/x.json",
        "state/global-entities/x.json",
    ):
        with pytest.raises(GraphRelationshipError, match="forbidden-write-prefix"):
            promote_relationship_path_forbidden(relative)


def test_adv_g3_cli_store_graph_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["store-graph", "--help"])
    assert exc.value.code == 0
