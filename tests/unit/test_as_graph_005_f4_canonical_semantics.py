"""AS-OBSIDIAN-CAPTURE-001-F4 — graph projections use canonical HUMAN-region semantics.

The graph projection regeneration path must not drift from the canonical
protected-region core: identity by structural scope path, fail-closed
ambiguity, transactional preservation. One graph-specific contract is
retained deliberately (no-HUMAN prior notes keep text outside the generated
span) and is pinned here as disclosed behavior.

Truth boundary: GRAPH PROJECTION ≠ AUTOMATIC AUTHORITY.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

import project_atlas.graph_projections as gp
from project_atlas.graph_projections import (
    GraphProjectionError,
    materialize_projections,
    write_projection_outputs,
)
from project_atlas.graph_quarantine import GraphHealthSnapshot
from project_atlas.graph_relationships import RelationshipRecord
from project_atlas.protected_regions import (
    ProtectedRegionError,
    extract_human_regions,
    merge_protected_regions,
)


def _human(name: str, inner: str) -> str:
    return f"<!-- BEGIN HUMAN: {name} -->\n{inner}\n<!-- END HUMAN: {name} -->"


_GENERATED_V1 = "<!-- atlas:generated:start -->\ngen v1\n<!-- atlas:generated:end -->"
_GENERATED_V2 = "<!-- atlas:generated:start -->\ngen v2\n<!-- atlas:generated:end -->"


def _note(human: str, *, generated: str = _GENERATED_V1) -> str:
    return f"---\ntype: GraphProjection\n---\n{generated}\n{human}\ntail-notes\n"


def _gp_merge(existing: str | None, rendered: str) -> str:
    return gp._merge_protected_regions(existing=existing, rendered=rendered, path="p.md")


def _build_nested_note(
    structure: dict[str, list[str]], order: list[str], *, generated: str, tag: str, trial: int
) -> str:
    parts = []
    for top in order:
        inner = "\n".join(
            _human(leaf, f"PAYLOAD-{tag}-{trial}-{top}-{leaf}") for leaf in structure[top]
        )
        parts.append(_human(top, inner))
    return _note("\n".join(parts), generated=generated)


# --- F4-01 … F4-10 directed acceptance matrix ---------------------------------


def test_f4_01_same_leaf_cross_scope_preserved_independently() -> None:
    existing = _note(
        _human("a", _human("x", "PAYLOAD-AX")) + "\n" + _human("b", _human("x", "PAYLOAD-BX"))
    )
    rendered = _note(
        _human("a", _human("x", "")) + "\n" + _human("b", _human("x", "")),
        generated=_GENERATED_V2,
    )
    merged = _gp_merge(existing, rendered)
    assert "PAYLOAD-AX" in merged
    assert "PAYLOAD-BX" in merged
    regions = extract_human_regions(merged)
    assert regions[("a", "x")].strip() == _human("x", "PAYLOAD-AX")
    assert regions[("b", "x")].strip() == _human("x", "PAYLOAD-BX")


def test_f4_02_same_scope_duplicate_root_refused() -> None:
    existing = _note(_human("x", "PAYLOAD-D1") + "\n" + _human("x", "PAYLOAD-D2"))
    rendered = _note(_human("x", ""), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError):
        _gp_merge(existing, rendered)


def test_f4_03_same_scope_duplicate_nested_refused() -> None:
    existing = _note(_human("a", _human("x", "PAYLOAD-N1") + "\n" + _human("x", "PAYLOAD-N2")))
    rendered = _note(_human("a", _human("x", "") + "\n" + _human("x", "")), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError):
        _gp_merge(existing, rendered)


def test_f4_04_self_nesting_refused() -> None:
    existing = _note(_human("a", _human("a", "PAYLOAD-SN")))
    rendered = _note(_human("a", _human("a", "")), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError):
        _gp_merge(existing, rendered)


def test_f4_05_crossed_markers_refused() -> None:
    crossed = (
        "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: b -->\nPAYLOAD-X\n"
        "<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->"
    )
    existing = _note(crossed)
    rendered = _note(_human("a", _human("b", "")), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError):
        _gp_merge(existing, rendered)


def test_f4_06_unclosed_begin_refused() -> None:
    existing = _note("<!-- BEGIN HUMAN: a -->\nPAYLOAD-UC")
    rendered = _note(_human("a", ""), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError):
        _gp_merge(existing, rendered)


def test_f4_07_reordered_siblings_no_identity_transfer() -> None:
    existing = _note(
        _human("a", _human("x", "PAYLOAD-RO-A")) + "\n" + _human("b", _human("x", "PAYLOAD-RO-B"))
    )
    rendered = _note(
        _human("b", _human("x", "")) + "\n" + _human("a", _human("x", "")),
        generated=_GENERATED_V2,
    )
    merged = _gp_merge(existing, rendered)
    regions = extract_human_regions(merged)
    assert regions[("a", "x")].strip() == _human("x", "PAYLOAD-RO-A")
    assert regions[("b", "x")].strip() == _human("x", "PAYLOAD-RO-B")


def test_f4_08_nested_distinct_names_no_top_level_duplicate() -> None:
    existing = _note(_human("outer", _human("inner", "PAYLOAD-ND")))
    rendered = _note(_human("outer", _human("inner", "")), generated=_GENERATED_V2)
    merged = _gp_merge(existing, rendered)
    assert merged == existing.replace(_GENERATED_V1, _GENERATED_V2)
    regions = extract_human_regions(merged)
    assert ("inner",) not in regions
    assert regions[("outer", "inner")].strip() == _human("inner", "PAYLOAD-ND")


def test_f4_09_orphan_prior_region_appended_not_dropped() -> None:
    existing = _note(_human("keep", "PAYLOAD-KP") + "\n" + _human("gone", "PAYLOAD-OR"))
    rendered = _note(_human("keep", ""), generated=_GENERATED_V2)
    merged = _gp_merge(existing, rendered)
    assert "PAYLOAD-OR" in merged
    assert "PAYLOAD-KP" in merged


def test_f4_10_repeat_refresh_is_stable() -> None:
    existing = _note(_human("a", _human("x", "PAYLOAD-RR")))
    rendered = _note(_human("a", _human("x", "")), generated=_GENERATED_V2)
    once = _gp_merge(existing, rendered)
    twice = _gp_merge(once, rendered)
    assert once == twice


# --- Retained graph-specific contract + error translation ----------------------


def test_f4_no_human_prior_preserves_text_outside_generated_span() -> None:
    existing = "manual preamble\n" + _GENERATED_V1 + "\nmanual postamble\n"
    rendered = _note(_human("notes", ""), generated=_GENERATED_V2)
    merged = _gp_merge(existing, rendered)
    assert "manual preamble" in merged
    assert "manual postamble" in merged
    assert "gen v2" in merged


def test_f4_refusal_surfaces_as_graph_projection_error_not_canonical() -> None:
    existing = _note(_human("x", "PAYLOAD-1") + "\n" + _human("x", "PAYLOAD-2"))
    rendered = _note(_human("x", ""), generated=_GENERATED_V2)
    with pytest.raises(GraphProjectionError) as excinfo:
        _gp_merge(existing, rendered)
    assert not isinstance(excinfo.value, ProtectedRegionError)


def test_f4_existing_none_validates_rendered() -> None:
    rendered = _note(_human("notes", ""), generated=_GENERATED_V2)
    assert _gp_merge(None, rendered) == rendered
    with pytest.raises(GraphProjectionError):
        _gp_merge(None, rendered + "<!-- BEGIN HUMAN: broken -->\n")


# --- Real generated surface (§17): human annotations survive regeneration ------


def _relationship(rel_id: str, source: str, target: str) -> RelationshipRecord:
    return RelationshipRecord(
        project_id="demo",
        relationship_id=rel_id,
        relationship_type="depends-on",
        source_entity_id=source,
        target_entity_id=target,
        source_graphify_id=source.split(":", 1)[1],
        target_graphify_id=target.split(":", 1)[1],
        link_quality="inferred",
        relationship_fingerprint="c" * 64,
        provenance={
            "graphify_artifact_refs": [{"relative_path": "g/graph.json", "sha256": "a" * 64}]
        },
    )


def test_f4_real_projection_surface_human_annotations_survive(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    health = GraphHealthSnapshot(
        project_id="demo",
        retained_count=1,
        quarantined_count=0,
        category_counts={},
        link_quality_histogram={"inferred": 1},
        health_state="healthy",
        input_content_hash="d" * 64,
    )
    bundle = materialize_projections(
        project_id="demo",
        relationships=(_relationship("rel-1", "demo:a", "demo:b"),),
        health=health,
    )
    write_projection_outputs(bundle, vault=vault)
    rel_path = vault / "generated/graph/projections/demo/relationships.md"
    health_path = vault / "generated/graph/projections/demo/graph-health.md"

    note = "Operator graph note: survives regeneration.\n"
    text = rel_path.read_text(encoding="utf-8")
    rel_path.write_text(
        text.replace(
            "<!-- BEGIN HUMAN: notes -->\n<!-- END HUMAN: notes -->\n", _human("notes", note)
        ),
        encoding="utf-8",
    )
    health_text = health_path.read_text(encoding="utf-8")
    health_path.write_text(
        health_text.replace(
            "<!-- BEGIN HUMAN: notes -->\n<!-- END HUMAN: notes -->\n", _human("notes", note)
        ),
        encoding="utf-8",
    )

    updated = materialize_projections(
        project_id="demo",
        relationships=(
            _relationship("rel-1", "demo:a", "demo:b"),
            _relationship("rel-2", "demo:c", "demo:d"),
        ),
        health=health,
    )
    write_projection_outputs(updated, vault=vault)
    assert note.strip() in rel_path.read_text(encoding="utf-8")
    assert note.strip() in health_path.read_text(encoding="utf-8")
    assert "rel-2" in rel_path.read_text(encoding="utf-8")


# --- Randomized differential vs canonical core (§18), seeded -------------------


def test_f4_differential_randomized_matches_canonical_core() -> None:
    rng = random.Random(20260907)
    for trial in range(500):
        containers = rng.sample(["a", "b", "c"], k=rng.randint(1, 3))
        structure: dict[str, list[str]] = {}
        for top in containers:
            structure[top] = rng.sample(["x", "y"], k=rng.randint(1, 2))

        existing = _build_nested_note(
            structure, containers, generated=_GENERATED_V1, tag="E", trial=trial
        )
        shuffled = rng.sample(containers, k=len(containers))
        rendered = _build_nested_note(
            structure, shuffled, generated=_GENERATED_V2, tag="R", trial=trial
        )
        try:
            canonical = merge_protected_regions(existing=existing, rendered=rendered, path="p.md")
            canonical_exc: Exception | None = None
        except ProtectedRegionError as exc:
            canonical = ""
            canonical_exc = exc
        try:
            graph = _gp_merge(existing, rendered)
            graph_exc: Exception | None = None
        except GraphProjectionError as exc:
            graph = ""
            graph_exc = exc

        if canonical_exc is not None:
            assert graph_exc is not None, f"trial {trial}: canonical refused, graph accepted"
            continue
        assert graph_exc is None, f"trial {trial}: canonical accepted, graph refused"
        assert graph == canonical, f"trial {trial}: graph output diverged from canonical core"
        regions = extract_human_regions(graph)
        for top, leaves in structure.items():
            for leaf in leaves:
                want = f"PAYLOAD-E-{trial}-{top}-{leaf}"
                assert want in regions[(top, leaf)], f"trial {trial}: lost {want}"
