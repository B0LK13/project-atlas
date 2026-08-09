"""AS-XPROJ-001 — Global entity identity registry (fixture matrix + ADV-XP)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.schema import available_schemas, validate_record
from project_atlas.xproj_registry import (
    AUTHORITY_LEVEL,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    EvidenceRef,
    GlobalEntityRecord,
    JoinKeyRecord,
    QuarantineCandidate,
    XprojRegistryError,
    apply_registrations,
    inspect_registry,
    promote_registry_path_forbidden,
    register_global_entity,
    register_join,
    write_registry_outputs,
)

EVIDENCE = EvidenceRef(relative_path="sources/arch.md", sha256="a" * 64)


def test_xproj_001_schemas_registered() -> None:
    kinds = available_schemas()
    assert "xproj-global-entity" in kinds
    assert "xproj-join-key" in kinds
    assert "xproj-quarantine-candidate" in kinds


def test_xp_fx_001_same_string_distinct_until_dual_join() -> None:
    """Two projects, same technology string → distinct until dual explicit join."""
    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-tech-postgres-v1",
                "entity_class": "technology",
                "display_name": "Postgres",
            },
            {
                "kind": "join",
                "project_id": "proj-a",
                "project_local_entity_id": "proj-a:unknown:postgres",
                "global_entity_id": "ge-tech-postgres-v1",
                "evidence_refs": [EVIDENCE.as_dict()],
            },
            {
                "kind": "join",
                "project_id": "proj-b",
                "project_local_entity_id": "proj-b:unknown:postgres",
                "global_entity_id": "ge-tech-postgres-v1",
                "evidence_refs": [EVIDENCE.as_dict()],
            },
        ]
    )
    assert result.registered_count == 1
    assert result.joined_count == 2
    assert result.quarantined_count == 0
    # Without joins, same display name alone does not create a shared id.
    alone = register_global_entity(
        global_entity_id=None,
        entity_class="technology",
        display_name="Postgres",
        mint_from_name=True,
    )
    assert isinstance(alone, QuarantineCandidate)
    assert alone.category == "name-only-merge-forbidden"


def test_xp_fx_002_class_non_collapse() -> None:
    """Same string as technology vs service → different global IDs."""
    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-tech-billing",
                "entity_class": "technology",
                "display_name": "billing",
            },
            {
                "kind": "entity",
                "global_entity_id": "ge-svc-billing",
                "entity_class": "service",
                "display_name": "billing",
            },
        ]
    )
    assert result.registered_count == 2
    ids = {item.global_entity_id for item in result.entities}
    assert ids == {"ge-tech-billing", "ge-svc-billing"}
    classes = {item.entity_class for item in result.entities}
    assert classes == {"technology", "service"}


def test_xp_fx_003_ambiguous_join_quarantine() -> None:
    """One local joined to two globals → quarantine; no winner."""
    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-a",
                "entity_class": "technology",
                "display_name": "Alpha",
            },
            {
                "kind": "entity",
                "global_entity_id": "ge-b",
                "entity_class": "technology",
                "display_name": "Beta",
            },
            {
                "kind": "join",
                "project_id": "proj-a",
                "project_local_entity_id": "local-1",
                "global_entity_id": "ge-a",
                "evidence_refs": [EVIDENCE.as_dict()],
            },
            {
                "kind": "join",
                "project_id": "proj-a",
                "project_local_entity_id": "local-1",
                "global_entity_id": "ge-b",
                "evidence_refs": [EVIDENCE.as_dict()],
            },
        ]
    )
    assert result.joined_count == 1
    assert result.quarantined_count == 1
    candidate = result.quarantine[0]
    assert candidate.category == "ambiguous-join"
    assert "winning_choice" not in candidate.as_dict()
    validate_record(candidate.as_dict(), "xproj-quarantine-candidate")


def test_xp_fx_004_name_only_hard_reject() -> None:
    outcome = register_global_entity(
        global_entity_id=None,
        entity_class="technology",
        display_name="Redis",
        mint_from_name=True,
    )
    assert isinstance(outcome, QuarantineCandidate)
    assert outcome.category == "name-only-merge-forbidden"


def test_xp_fx_005_physical_resource_promotion_forbidden() -> None:
    outcome = register_global_entity(
        global_entity_id="ge-host-1",
        entity_class="technology",
        display_name="db-host-01",
        attributes={"hostname": "db-host-01.internal"},
    )
    assert isinstance(outcome, QuarantineCandidate)
    assert outcome.category == "physical-resource-promotion-forbidden"


def test_xp_fx_006_derived_authority_and_schema() -> None:
    record = register_global_entity(
        global_entity_id="ge-lib-requests",
        entity_class="library",
        display_name="requests",
    )
    assert isinstance(record, GlobalEntityRecord)
    payload = record.as_dict()
    assert payload["authority"]["level"] == AUTHORITY_LEVEL
    assert payload["package_id"] == PACKAGE_ID
    assert payload["truth_boundary"] == TRUTH_BOUNDARY
    validate_record(payload, "xproj-global-entity")


def test_xp_fx_007_determinism_replay() -> None:
    requests = [
        {
            "kind": "entity",
            "global_entity_id": "ge-tech-z",
            "entity_class": "technology",
            "display_name": "Zed",
        },
        {
            "kind": "entity",
            "global_entity_id": "ge-tech-a",
            "entity_class": "technology",
            "display_name": "Aye",
        },
        {
            "kind": "join",
            "project_id": "p2",
            "project_local_entity_id": "p2:a",
            "global_entity_id": "ge-tech-a",
            "evidence_refs": [EVIDENCE.as_dict()],
        },
        {
            "kind": "join",
            "project_id": "p1",
            "project_local_entity_id": "p1:z",
            "global_entity_id": "ge-tech-z",
            "evidence_refs": [EVIDENCE.as_dict()],
        },
    ]
    a = apply_registrations(requests)
    b = apply_registrations(list(reversed(requests)))
    assert [e.to_json() for e in a.entities] == [e.to_json() for e in b.entities]
    assert [j.to_json() for j in a.joins] == [j.to_json() for j in b.joins]


def test_xp_fx_008_path_policy_and_writes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "claims").mkdir()
    claim = vault / "claims" / "c1.json"
    claim.write_text('{"x":1}\n', encoding="utf-8")
    before = claim.read_bytes()

    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-env-prod",
                "entity_class": "environment",
                "display_name": "prod-eu",
            },
            {
                "kind": "join",
                "project_id": "proj-a",
                "project_local_entity_id": "local-env",
                "global_entity_id": "ge-env-prod",
                "evidence_refs": [EVIDENCE.as_dict()],
            },
        ]
    )
    written = write_registry_outputs(result, vault=vault)
    assert written
    assert all(path.startswith("state/global-entities/") for path in written)
    assert claim.read_bytes() == before

    with pytest.raises(XprojRegistryError, match="forbidden-write-prefix"):
        promote_registry_path_forbidden("claims/x.json")
    with pytest.raises(XprojRegistryError, match="forbidden-write-prefix"):
        promote_registry_path_forbidden("generated/graph/relationships/x.json")
    with pytest.raises(XprojRegistryError, match="forbidden-write-prefix"):
        promote_registry_path_forbidden("relationships/x.json")
    with pytest.raises(XprojRegistryError, match="path-escape"):
        promote_registry_path_forbidden("state/global-entities/../claims/x.json")


def test_xp_fx_009_missing_registration_join() -> None:
    outcome = register_join(
        project_id="proj-a",
        project_local_entity_id="local-1",
        global_entity_id="ge-missing",
        evidence_refs=[EVIDENCE],
        registry={},
    )
    assert isinstance(outcome, QuarantineCandidate)
    assert outcome.category == "missing-registration"


def test_xp_fx_010_fuzzy_forbidden() -> None:
    outcome = register_global_entity(
        global_entity_id="ge-fuzzy",
        entity_class="technology",
        display_name="AlmostPostgres",
        fuzzy=True,
    )
    assert isinstance(outcome, QuarantineCandidate)
    assert outcome.category == "fuzzy-identity-forbidden"


def test_xp_fx_011_colliding_registration_class() -> None:
    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-shared",
                "entity_class": "technology",
                "display_name": "X",
            },
            {
                "kind": "entity",
                "global_entity_id": "ge-shared",
                "entity_class": "service",
                "display_name": "X",
            },
        ]
    )
    assert result.registered_count == 1
    assert any(q.category == "colliding-registration" for q in result.quarantine)


def test_xp_fx_012_inspect_counts() -> None:
    result = apply_registrations(
        [
            {
                "kind": "entity",
                "global_entity_id": "ge-org-acme",
                "entity_class": "organization",
                "display_name": "Acme",
            }
        ]
    )
    summary = inspect_registry(result)
    assert summary["registered"] == 1
    assert summary["authority_level"] == "derived"
    assert summary == json.loads(json.dumps(summary, sort_keys=True))


def test_xp_fx_013_join_schema_valid() -> None:
    entity = register_global_entity(
        global_entity_id="ge-api-stripe",
        entity_class="external-api",
        display_name="Stripe",
    )
    assert isinstance(entity, GlobalEntityRecord)
    join = register_join(
        project_id="proj-a",
        project_local_entity_id="proj-a:api:stripe",
        global_entity_id="ge-api-stripe",
        evidence_refs=[EVIDENCE],
        registry={entity.global_entity_id: entity},
    )
    assert isinstance(join, JoinKeyRecord)
    validate_record(join.as_dict(), "xproj-join-key")
