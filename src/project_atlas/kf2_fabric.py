"""AS-KF2-NS-001 / AS-KF2-ENTITY-001 / AS-KF2-REL-001 — Knowledge Fabric Wave 1.

Derived fabric plane bound to the Atlas 1.0 compatibility anchor. Never Layer B
authority. Optional XPROJ global entity references remain derived-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

NS_PACKAGE = "AS-KF2-NS-001"
ENTITY_PACKAGE = "AS-KF2-ENTITY-001"
REL_PACKAGE = "AS-KF2-REL-001"

_NS_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

RelationType = Literal[
    "depends-on",
    "implements",
    "related-to",
    "supersedes",
    "member-of",
]


class Kf2Error(ValueError):
    """Fail-closed Knowledge Fabric error."""


@dataclass(frozen=True, slots=True)
class Kf2Namespace:
    namespace_id: str
    display_name: str
    notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": NS_PACKAGE,
            "namespace_id": self.namespace_id,
            "display_name": self.display_name,
            "compat_snapshot_id": SNAPSHOT_ID,
            "authority": {
                "level": "derived",
                "note": "KF2 namespace is fabric organization only",
            },
            "status": "active",
            "truth_boundary": "KF2 NAMESPACE ≠ AUTHORITY",
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class Kf2Entity:
    entity_id: str
    namespace_id: str
    display_name: str
    xproj_global_entity_id: str | None = None
    notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": ENTITY_PACKAGE,
            "entity_id": self.entity_id,
            "namespace_id": self.namespace_id,
            "display_name": self.display_name,
            "compat_snapshot_id": SNAPSHOT_ID,
            "authority": {
                "level": "derived",
                "note": "KF2 entity is derived fabric identity",
            },
            "status": "active",
            "truth_boundary": "KF2 ENTITY ≠ AUTHORITY",
        }
        if self.xproj_global_entity_id:
            payload["xproj_global_entity_id"] = self.xproj_global_entity_id
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class Kf2Relationship:
    relationship_id: str
    from_entity_id: str
    to_entity_id: str
    relation_type: RelationType
    notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": REL_PACKAGE,
            "relationship_id": self.relationship_id,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "relation_type": self.relation_type,
            "compat_snapshot_id": SNAPSHOT_ID,
            "authority": {
                "level": "derived",
                "note": "KF2 relationship is derived; Graph≠authority",
            },
            "status": "active",
            "truth_boundary": "KF2 RELATIONSHIP ≠ AUTHORITY",
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


def _validate_ns_id(namespace_id: str) -> str:
    token = namespace_id.strip()
    if not _NS_RE.fullmatch(token):
        raise Kf2Error("kf2-namespace-id-invalid")
    return token


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise Kf2Error(f"kf2-{label}-invalid")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def fabric_root(vault: Path) -> Path:
    return vault.resolve() / "generated" / "kf2"


def register_namespace(
    vault: Path,
    *,
    namespace_id: str,
    display_name: str,
    notes: str | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> Kf2Namespace:
    """Register a Knowledge Fabric namespace under the verified 1.0 pin."""
    _ = anchor or require_compatibility_anchor()
    ns = Kf2Namespace(
        namespace_id=_validate_ns_id(namespace_id),
        display_name=display_name.strip(),
        notes=notes.strip() if notes else None,
    )
    if not ns.display_name:
        raise Kf2Error("kf2-namespace-display-name-empty")
    try:
        validate_record(ns.as_dict(), "kf2-namespace")
    except SchemaValidationError as exc:
        raise Kf2Error(f"kf2-namespace-schema:{exc}") from exc
    path = fabric_root(vault) / "namespaces" / f"{ns.namespace_id}.json"
    if path.exists():
        raise Kf2Error(f"kf2-namespace-exists:{ns.namespace_id}")
    _atomic_write_json(path, ns.as_dict())
    return ns


def register_entity(
    vault: Path,
    *,
    entity_id: str,
    namespace_id: str,
    display_name: str,
    xproj_global_entity_id: str | None = None,
    notes: str | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> Kf2Entity:
    """Register a KF2 entity in an existing namespace."""
    _ = anchor or require_compatibility_anchor()
    ns_id = _validate_ns_id(namespace_id)
    ns_path = fabric_root(vault) / "namespaces" / f"{ns_id}.json"
    if not ns_path.is_file():
        raise Kf2Error(f"kf2-namespace-missing:{ns_id}")
    entity = Kf2Entity(
        entity_id=_validate_id(entity_id, label="entity-id"),
        namespace_id=ns_id,
        display_name=display_name.strip(),
        xproj_global_entity_id=(
            _validate_id(xproj_global_entity_id, label="xproj-global-entity-id")
            if xproj_global_entity_id
            else None
        ),
        notes=notes.strip() if notes else None,
    )
    if not entity.display_name:
        raise Kf2Error("kf2-entity-display-name-empty")
    try:
        validate_record(entity.as_dict(), "kf2-entity")
    except SchemaValidationError as exc:
        raise Kf2Error(f"kf2-entity-schema:{exc}") from exc
    path = fabric_root(vault) / "entities" / f"{entity.entity_id}.json"
    if path.exists():
        raise Kf2Error(f"kf2-entity-exists:{entity.entity_id}")
    _atomic_write_json(path, entity.as_dict())
    return entity


def register_relationship(
    vault: Path,
    *,
    relationship_id: str,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: RelationType,
    notes: str | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> Kf2Relationship:
    """Register a derived KF2 relationship between existing entities."""
    _ = anchor or require_compatibility_anchor()
    from_id = _validate_id(from_entity_id, label="from-entity-id")
    to_id = _validate_id(to_entity_id, label="to-entity-id")
    if from_id == to_id:
        raise Kf2Error("kf2-relationship-self-loop")
    root = fabric_root(vault)
    if not (root / "entities" / f"{from_id}.json").is_file():
        raise Kf2Error(f"kf2-from-entity-missing:{from_id}")
    if not (root / "entities" / f"{to_id}.json").is_file():
        raise Kf2Error(f"kf2-to-entity-missing:{to_id}")
    allowed: set[str] = {
        "depends-on",
        "implements",
        "related-to",
        "supersedes",
        "member-of",
    }
    if relation_type not in allowed:
        raise Kf2Error("kf2-relation-type-invalid")
    rel = Kf2Relationship(
        relationship_id=_validate_id(relationship_id, label="relationship-id"),
        from_entity_id=from_id,
        to_entity_id=to_id,
        relation_type=relation_type,
        notes=notes.strip() if notes else None,
    )
    try:
        validate_record(rel.as_dict(), "kf2-relationship")
    except SchemaValidationError as exc:
        raise Kf2Error(f"kf2-relationship-schema:{exc}") from exc
    path = root / "relationships" / f"{rel.relationship_id}.json"
    if path.exists():
        raise Kf2Error(f"kf2-relationship-exists:{rel.relationship_id}")
    _atomic_write_json(path, rel.as_dict())
    return rel
