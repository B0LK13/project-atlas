"""AS-GRAPH-005 adversarial probes (ADV-G5 band).

Truth boundary: GRAPH PROJECTION ≠ AUTOMATIC AUTHORITY.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from project_atlas.graph_projections import (
    TRUTH_BOUNDARY,
    GraphProjectionError,
    materialize_projections,
    promote_projection_path_forbidden,
    write_projection_outputs,
)
from project_atlas.graph_quarantine import GraphHealthSnapshot
from project_atlas.graph_relationships import RelationshipRecord


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relationship(relationship_id: str) -> RelationshipRecord:
    return RelationshipRecord(
        project_id="demo",
        relationship_id=relationship_id,
        relationship_type="depends-on",
        source_entity_id="demo:a",
        target_entity_id="demo:b",
        source_graphify_id="a",
        target_graphify_id="b",
        link_quality="inferred",
        relationship_fingerprint="f" * 64,
        provenance={},
    )


def _health() -> GraphHealthSnapshot:
    return GraphHealthSnapshot(
        project_id="demo",
        retained_count=1,
        quarantined_count=0,
        category_counts={},
        link_quality_histogram={"inferred": 1},
        health_state="healthy",
        input_content_hash="a" * 64,
    )


def _forbidden_census(vault: Path) -> dict[str, tuple[int, str]]:
    relatives = (
        "claims/claim.json",
        "state/current-state/demo.json",
        "state/authoritative-state/demo.json",
        "relationships/nodes.json",
        "generated/query/cache.json",
        "state/global-entities/registry.json",
        "generated/graph/relationships/demo/sentinel.json",
        "generated/graph/relationship-quarantine/demo/sentinel.json",
        "generated/graph/quarantine/demo/sentinel.json",
        "generated/graph/health/demo/health.json",
        "generated/graph/incremental/demo/state.json",
        "generated/graph/quarantine-candidates/demo/sentinel.json",
        "generated/graph/resolved/demo/sentinel.json",
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


def test_adv_g5_projection_never_mutates_certified_graph_stores(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _forbidden_census(vault)
    bundle = materialize_projections(
        project_id="demo",
        relationships=(_relationship("rel-1"),),
        health=_health(),
    )
    write_projection_outputs(bundle, vault=vault)
    _assert_census_stable(vault, before)
    assert (vault / "generated/graph/projections/demo/relationships.md").is_file()
    assert TRUTH_BOUNDARY in (
        vault / "generated/graph/projections/demo/relationships.md"
    ).read_text(encoding="utf-8")


def test_adv_g5_cp_relationships_path_forbidden() -> None:
    with pytest.raises(GraphProjectionError, match="forbidden-write-prefix"):
        promote_projection_path_forbidden("relationships/graph.md")


def test_adv_g5_duplicate_generated_markers_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bundle = materialize_projections(project_id="demo")
    write_projection_outputs(bundle, vault=vault)
    path = vault / "generated/graph/projections/demo/graph-health.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "\n<!-- atlas:generated:start -->\n", encoding="utf-8")
    with pytest.raises(GraphProjectionError, match="malformed-generated-markers"):
        write_projection_outputs(bundle, vault=vault)
