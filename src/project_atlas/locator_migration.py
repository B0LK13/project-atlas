"""Locator refinement and alias handling (AS-EXT-001A, directive §7.10).

Claim Identity v2 is unchanged: parser-derived locator changes are LOCATOR
REFINEMENT, not a new identity algorithm. This module classifies old-to-new
locator migrations and feeds the existing v2 alias mechanism
(`claim-alias` schema, `project_atlas.migrations.claim_v2_migration`) — no
parallel migration subsystem.

Migration classes (§7.10):

- ONE OLD → ONE NEW: automatic alias candidate;
- ONE OLD → MANY NEW: ambiguity record; no automatic promotion;
- MANY OLD → ONE NEW: semantic collapse review (ambiguity record);
- MANY OLD → MANY NEW: manual or profile-specific migration (ambiguity record);
- NO STABLE OLD LOCATOR: new identity with explicit historical discontinuity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from project_atlas.schema import validate_record


class MigrationClass(StrEnum):
    """Old-to-new locator mapping classes (§7.10)."""

    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"
    NO_STABLE_OLD_LOCATOR = "no-stable-old-locator"


@dataclass(frozen=True)
class RefinedClaimIdentity:
    """One new-style identity derived from a refined parser locator."""

    claim_id: str
    project_identity: str
    source_lineage_id: str
    claim_type: str
    field: str
    stable_semantic_locator: str
    source_commit: str
    source_path: str


@dataclass(frozen=True)
class LocatorMigration:
    """Mapping from one historical identity to its refined identities."""

    old_claim_id: str | None
    old_locator: str | None
    new: tuple[RefinedClaimIdentity, ...]


@dataclass(frozen=True)
class DiscontinuityRecord:
    """Explicit historical discontinuity for NO STABLE OLD LOCATOR (§7.10)."""

    new_claim_id: str
    old_locator: str | None
    reason: str


def classify_mapping_set(
    migrations: tuple[LocatorMigration, ...] | list[LocatorMigration],
) -> dict[str, MigrationClass]:
    """Classify every migration, including set-level MANY-* relationships.

    Entries sharing one old claim id are aggregated first: the set-level
    truth is what that historical identity maps to overall (for example, two
    one-target entries for the same old id are ONE OLD → MANY NEW). Returns a
    mapping from old claim id (or the new claim id for the no-stable-old
    case) to its migration class. Deterministic: input order does not affect
    the result.
    """
    classes: dict[str, MigrationClass] = {}
    by_old: dict[str, list[LocatorMigration]] = {}
    for migration in migrations:
        if migration.old_claim_id is not None:
            by_old.setdefault(migration.old_claim_id, []).append(migration)
    new_to_olds: dict[str, set[str]] = {}
    for migration in migrations:
        for identity in migration.new:
            if migration.old_claim_id is not None:
                new_to_olds.setdefault(identity.claim_id, set()).add(migration.old_claim_id)
    for migration in migrations:
        old_id = migration.old_claim_id
        if old_id is None:
            key = migration.new[0].claim_id if migration.new else "<empty>"
            classes[key] = MigrationClass.NO_STABLE_OLD_LOCATOR
            continue
        if old_id in classes:
            continue
        aggregated = {
            identity.claim_id
            for entry in by_old[old_id]
            for identity in entry.new
        }
        new_count = len(aggregated)
        shared_new = any(len(new_to_olds[claim_id]) > 1 for claim_id in aggregated)
        if new_count == 1 and not shared_new:
            classes[old_id] = MigrationClass.ONE_TO_ONE
        elif new_count == 1:
            classes[old_id] = MigrationClass.MANY_TO_ONE
        elif not shared_new:
            classes[old_id] = MigrationClass.ONE_TO_MANY
        else:
            classes[old_id] = MigrationClass.MANY_TO_MANY
    return classes


def _alias_record(old_claim_id: str, identity: RefinedClaimIdentity) -> dict[str, Any]:
    """Shape one alias record for the existing claim-alias payload (§7.10).

    The historical claim id occupies the ``v1_claim_id`` slot of the existing
    schema; both ids are Claim Identity v2 outputs because the identity
    algorithm is unchanged (LOCATOR REFINEMENT only).
    """
    return {
        "v1_claim_id": old_claim_id,
        "v2_claim_id": identity.claim_id,
        "project_identity": identity.project_identity,
        "source_lineage_id": identity.source_lineage_id,
        "claim_type": identity.claim_type,
        "field": identity.field,
        "stable_semantic_locator": identity.stable_semantic_locator,
        "source_commit": identity.source_commit,
        "source_path": identity.source_path,
    }


def build_alias_map_payload(
    project_id: str,
    migrations: tuple[LocatorMigration, ...] | list[LocatorMigration],
    *,
    migrated_at: str,
    source_commits_scanned: int,
) -> tuple[dict[str, Any], tuple[DiscontinuityRecord, ...]]:
    """Build a claim-alias payload from locator migrations (§7.10).

    Only provable ONE OLD → ONE NEW mappings become aliases. Ambiguous
    mappings are recorded with their candidate records and never promoted.
    Returns the validated payload plus explicit discontinuity records for
    NO STABLE OLD LOCATOR cases. Output is deterministic (sorted, no
    wall-clock; ``migrated_at`` is caller-supplied evidence metadata).
    """
    classes = classify_mapping_set(migrations)
    aliases: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    discontinuities: list[DiscontinuityRecord] = []

    reasons = {
        MigrationClass.ONE_TO_MANY: (
            "one-to-many locator refinement: several refined identities; "
            "no automatic promotion"
        ),
        MigrationClass.MANY_TO_ONE: (
            "many-to-one locator refinement: semantic collapse requires review"
        ),
        MigrationClass.MANY_TO_MANY: (
            "many-to-many locator refinement: manual or profile-specific "
            "migration required"
        ),
    }

    # Aggregate entries per historical id, mirroring classify_mapping_set:
    # one old id yields one alias-or-ambiguity decision, never two entries.
    grouped: dict[str, dict[str, RefinedClaimIdentity]] = {}
    for migration in migrations:
        old_id = migration.old_claim_id
        if old_id is None:
            for identity in migration.new:
                discontinuities.append(
                    DiscontinuityRecord(
                        new_claim_id=identity.claim_id,
                        old_locator=migration.old_locator,
                        reason=(
                            "no stable old locator: new identity with explicit "
                            "historical discontinuity"
                        ),
                    )
                )
            continue
        bucket = grouped.setdefault(old_id, {})
        for identity in migration.new:
            bucket.setdefault(identity.claim_id, identity)

    for old_id, identities in grouped.items():
        migration_class = classes[old_id]
        records = [
            _alias_record(old_id, identity)
            for identity in sorted(identities.values(), key=lambda item: item.claim_id)
        ]
        if migration_class is MigrationClass.ONE_TO_ONE:
            aliases.extend(records)
        else:
            ambiguous.append(
                {
                    "v1_claim_id": old_id,
                    "reason": reasons[migration_class],
                    "records": records,
                }
            )

    aliases.sort(key=lambda item: str(item["v1_claim_id"]))
    ambiguous.sort(key=lambda item: str(item["v1_claim_id"]))
    resolved = {str(item["v1_claim_id"]) for item in aliases}
    unresolved = {str(item["v1_claim_id"]) for item in ambiguous}
    overlap = resolved & unresolved
    if overlap:
        raise ValueError(
            "locator refinement contains resolved/ambiguous overlap: "
            + ", ".join(sorted(overlap))
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "project_id": project_id,
        "aliases": aliases,
        "ambiguous": ambiguous,
        "audit": {
            "migrated_at": migrated_at,
            "source_commits_scanned": source_commits_scanned,
            "input_claims": len(grouped),
            "output_aliases": len(aliases),
        },
    }
    # Reuse the existing alias contract; no parallel migration subsystem.
    validate_record(payload, "claim-alias")
    return payload, tuple(
        sorted(discontinuities, key=lambda item: item.new_claim_id)
    )
