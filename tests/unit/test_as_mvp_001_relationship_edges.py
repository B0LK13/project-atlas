"""AS-MVP-001-R1 relationship and capability edge-case hardening.

Focused unit tests against ``project_atlas.portfolio``'s existing pure,
read-only projection functions (``dependency_report``, ``capability_report``),
exercised directly over hand-built ``state/concepts/*.json`` and
``state/claims/*.json`` fixtures (the same on-disk shape ``knowledge_compiler``
already writes). No new canonical models, CLI surface, or schema are
introduced; this module only probes edge-case behavior of the existing
AS-MVP-001 projections per ADR-005
(docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md).

Selected edge-case tests informed by prototype review (AS-MVP-001-R1);
no Prototype B implementation or API is reused here.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.portfolio import capability_report, dependency_report


def _write_concepts(vault: Path, project_id: str, concepts: list[dict]) -> None:
    """Write ``state/concepts/<project_id>.json``.

    ``knowledge_compiler.compile_project`` always writes
    ``state/claims/<project>.json`` and ``state/concepts/<project>.json``
    together for every ingested project (same call, same result dict), so
    an empty claims file is written here too if one does not already
    exist -- mirroring that real invariant rather than exercising an
    on-disk shape the actual pipeline never produces.
    """
    root = vault / "state" / "concepts"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{project_id}.json").write_text(
        json.dumps({"concepts": concepts}, sort_keys=True), encoding="utf-8"
    )
    claims_path = vault / "state" / "claims" / f"{project_id}.json"
    if not claims_path.is_file():
        _write_claims(vault, project_id, [])


def _write_claims(vault: Path, project_id: str, claims: list[dict]) -> None:
    root = vault / "state" / "claims"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{project_id}.json").write_text(
        json.dumps({"claims": claims}, sort_keys=True), encoding="utf-8"
    )


def _relationship_concept(concept_id: str, target: str, rel_type: str = "depends_on") -> dict:
    return {
        "concept_id": concept_id,
        "type": "Component",
        "title": concept_id,
        "relationships": [{"type": rel_type, "target": target}],
    }


# ---------------------------------------------------------------------------
# 1. Circular dependency: A -> B -> A
# ---------------------------------------------------------------------------


def test_circular_dependency_does_not_crash_and_is_deterministic(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_concepts(vault, "a", [_relationship_concept("a", "b")])
    _write_concepts(vault, "b", [_relationship_concept("b", "a")])

    first = dependency_report(vault)
    second = dependency_report(vault)

    assert first == second
    assert first["projects"]["a"][0]["target"] == "b"
    assert first["projects"]["b"][0]["target"] == "a"


# ---------------------------------------------------------------------------
# 2. Self-reference: A -> A
# ---------------------------------------------------------------------------


def test_self_reference_is_reported_explicitly_and_deterministically(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_concepts(vault, "a", [_relationship_concept("a", "a")])

    first = dependency_report(vault)
    second = dependency_report(vault)

    assert first == second
    entries = first["projects"]["a"]
    assert len(entries) == 1
    # ADR-005 does not define a distinct self-reference status; the
    # projection surfaces the declared relationship as-is (target == the
    # concept's own id), citing the concept it came from, rather than
    # silently dropping or misrepresenting it.
    assert entries[0]["target"] == "a"
    assert entries[0]["concept_id"] == "a"


# ---------------------------------------------------------------------------
# 3. Duplicate identical relationship
# ---------------------------------------------------------------------------


def test_duplicate_identical_relationship_is_not_reported_twice(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_concepts(
        vault,
        "a",
        [
            {
                "concept_id": "a",
                "type": "Component",
                "title": "a",
                "relationships": [
                    {"type": "depends_on", "target": "x"},
                    {"type": "depends_on", "target": "x"},
                ],
            }
        ],
    )

    report = dependency_report(vault)
    entries = report["projects"]["a"]
    assert entries == [
        {"claim_id": None, "concept_id": "a", "target": "x", "relationship_type": "depends_on"}
    ]


# ---------------------------------------------------------------------------
# 4. Duplicate relation with distinct provenance (via claims)
# ---------------------------------------------------------------------------


def test_duplicate_target_with_distinct_provenance_is_preserved(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_claims(
        vault,
        "a",
        [
            {
                "claim_id": "c1",
                "claim_type": "runtime-dependency",
                "value": "shared-service",
                "provenance": [{"source_id": "s1", "source_lineage_id": "lin1"}],
            },
            {
                "claim_id": "c2",
                "claim_type": "runtime-dependency",
                "value": "shared-service",
                "provenance": [{"source_id": "s2", "source_lineage_id": "lin2"}],
            },
        ],
    )

    report = dependency_report(vault)
    entries = report["projects"]["a"]
    assert len(entries) == 2
    claim_ids = {entry["claim_id"] for entry in entries}
    assert claim_ids == {"c1", "c2"}
    for entry in entries:
        assert entry["target"] == "shared-service"
        assert entry["provenance"]


# ---------------------------------------------------------------------------
# 5. Missing/invalid target (no project of that id exists anywhere)
# ---------------------------------------------------------------------------


def test_dependency_on_missing_target_project_is_reported_not_fabricated(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_concepts(vault, "a", [_relationship_concept("a", "ghost-project")])

    report = dependency_report(vault)
    entries = report["projects"]["a"]
    assert len(entries) == 1
    assert entries[0]["target"] == "ghost-project"
    # The projection never asserts or implies "ghost-project" is a real,
    # resolvable project; it is carried through as an opaque, cited
    # target string (per ADR-005: "target" is "a vault-relative path or
    # concept ID", not guaranteed to resolve). No exception is raised.
    assert "ghost-project" not in report["projects"]


# ---------------------------------------------------------------------------
# 6. Shuffled relationship/concept input -> deterministic dependency output
# ---------------------------------------------------------------------------


def test_dependency_report_is_order_independent_under_tied_sort_keys(tmp_path: Path) -> None:
    concepts_forward = [
        _relationship_concept("c1", "shared-target"),
        _relationship_concept("c2", "shared-target"),
    ]
    concepts_reversed = list(reversed(concepts_forward))

    vault_a = Path(str(_mk(tmp_path, "vault_a")))
    vault_b = Path(str(_mk(tmp_path, "vault_b")))
    _write_concepts(vault_a, "p", concepts_forward)
    _write_concepts(vault_b, "p", concepts_reversed)

    report_a = dependency_report(vault_a)
    report_b = dependency_report(vault_b)

    assert report_a["projects"]["p"] == report_b["projects"]["p"]


def _mk(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# 7. Shared explicitly declared capability provider (two projects, same target)
# ---------------------------------------------------------------------------


def test_shared_capability_provider_across_projects_is_independent_per_project(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _write_concepts(
        vault,
        "a",
        [
            {
                "concept_id": "a-auth",
                "type": "Component",
                "title": "a-auth",
                "relationships": [{"type": "provides", "target": "shared-auth-service"}],
            }
        ],
    )
    _write_concepts(
        vault,
        "b",
        [
            {
                "concept_id": "b-auth",
                "type": "Component",
                "title": "b-auth",
                "relationships": [{"type": "provides", "target": "shared-auth-service"}],
            }
        ],
    )

    report = capability_report(vault)
    # Both projects independently and correctly cite their own provides
    # relationship; AS-MVP-001 does not infer or merge a cross-project
    # "shared provider" concept from target-string equality alone (no
    # canonical model exists for that), per ADR-005's explicit rejection
    # of prose/name-based inference.
    assert report["projects"]["a"]["provides"] == [
        {"concept_id": "a-auth", "target": "shared-auth-service"}
    ]
    assert report["projects"]["b"]["provides"] == [
        {"concept_id": "b-auth", "target": "shared-auth-service"}
    ]


# ---------------------------------------------------------------------------
# 8. Duplicate capability concepts
# ---------------------------------------------------------------------------


def test_duplicate_capability_concepts_are_not_reported_twice(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    capability = {
        "concept_id": "auth-capability",
        "type": "Capability",
        "title": "Auth capability",
        "tags": ["security"],
    }
    _write_concepts(vault, "a", [dict(capability), dict(capability)])

    report = capability_report(vault)
    capabilities = report["projects"]["a"]["capabilities"]
    assert capabilities == [
        {"concept_id": "auth-capability", "title": "Auth capability", "tags": ["security"]}
    ]


# ---------------------------------------------------------------------------
# 9. Shuffled capability input -> deterministic "provides" output
# ---------------------------------------------------------------------------


def test_capability_report_provides_is_order_independent_under_tied_sort_keys(
    tmp_path: Path,
) -> None:
    concepts_forward = [
        {
            "concept_id": "c1",
            "type": "Component",
            "title": "c1",
            "relationships": [{"type": "provides", "target": "shared-capability"}],
        },
        {
            "concept_id": "c2",
            "type": "Component",
            "title": "c2",
            "relationships": [{"type": "provides", "target": "shared-capability"}],
        },
    ]
    concepts_reversed = list(reversed(concepts_forward))

    vault_a = _mk(tmp_path, "vault_a")
    vault_b = _mk(tmp_path, "vault_b")
    _write_concepts(vault_a, "p", concepts_forward)
    _write_concepts(vault_b, "p", concepts_reversed)

    report_a = capability_report(vault_a)
    report_b = capability_report(vault_b)

    assert report_a["projects"]["p"] == report_b["projects"]["p"]


# ---------------------------------------------------------------------------
# 10. Empty relationship / capability collections
# ---------------------------------------------------------------------------


def test_project_with_no_relationships_or_capabilities_is_omitted_not_fabricated(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _write_concepts(
        vault,
        "a",
        [{"concept_id": "a", "type": "Component", "title": "a", "relationships": []}],
    )

    dep_report = dependency_report(vault)
    cap_report = capability_report(vault)

    # No dependency/capability evidence exists for "a"; ADR-005 requires
    # "an empty list, not an inferred one" for relationship kinds with no
    # declared evidence -- the existing projection expresses that as
    # project-key omission (never a fabricated entry), which this test
    # pins down explicitly.
    assert "a" not in dep_report["projects"]
    assert "a" not in cap_report["projects"]


def test_no_state_at_all_produces_empty_projects_dict(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    assert dependency_report(vault) == {"schema_version": 1, "projects": {}}
    assert capability_report(vault) == {"schema_version": 1, "projects": {}}
