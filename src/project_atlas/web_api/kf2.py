"""AS-CODER-ALPHA-KF2-READ-001 -- vault-scoped Knowledge Fabric REPORT READ.

Inspects persisted AS-KF2-NS-001 / AS-KF2-ENTITY-001 / AS-KF2-REL-001
projections under ``generated/kf2/{namespaces,entities,relationships}/``.
This module never registers a namespace, entity, or relationship, never
writes inventory, and never promotes Layer B authority.

Honesty:
- KF2 != AUTHORITY
- NAME != IDENTITY
- MISSING != REGISTERED
- EMPTY != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-KF2-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-kf2-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.kf2-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = (
    "AS-KF2-NS-001",
    "AS-KF2-ENTITY-001",
    "AS-KF2-REL-001",
)
TRUTH_BOUNDARY: Final[str] = (
    "KF2 != AUTHORITY / NAME != IDENTITY / MISSING != REGISTERED / "
    "EMPTY != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "D149_TOUCHED = NO / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)

FABRIC_REL: Final[Path] = Path("generated") / "kf2"
NS_REL: Final[Path] = FABRIC_REL / "namespaces"
ENTITY_REL: Final[Path] = FABRIC_REL / "entities"
REL_REL: Final[Path] = FABRIC_REL / "relationships"

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "KF2 != AUTHORITY",
    "NAME != IDENTITY",
    "MISSING != REGISTERED",
    "EMPTY != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebKf2Error(ValueError):
    """Fail-closed Knowledge Fabric REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "kf2_is_authority": False,
        "name_is_identity": False,
        "missing_is_registered": False,
        "missing_is_healthy": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "register_dispatched": False,
        "namespace_registered": False,
        "entity_registered": False,
        "relationship_registered": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebKf2Error(f"kf2-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebKf2Error("kf2-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebKf2Error(f"kf2-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebKf2Error("kf2-path-escape")
    return resolved


def _projection_root(
    vault: Path, relative: Path
) -> tuple[ProjectionStatus, Path | None]:
    raw = vault / relative
    if not raw.exists():
        return "MISSING", None
    if raw.is_symlink() or not raw.is_dir():
        raise WebKf2Error(f"kf2-projection-not-directory:{relative.as_posix()}")
    return "EMPTY", _inside(vault, raw)


def _read_json_object(vault: Path, path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WebKf2Error(f"kf2-not-regular-file:{path.name}")
    resolved = _inside(vault, path)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebKf2Error(f"kf2-malformed-json:{path.name}") from exc
    except OSError as exc:
        raise WebKf2Error(f"kf2-unreadable:{path.name}") from exc
    if not isinstance(loaded, dict):
        raise WebKf2Error(f"kf2-json-not-object:{path.name}")
    return loaded


def _relative_posix(vault: Path, path: Path) -> str:
    return _inside(vault, path).relative_to(vault).as_posix()


def _validate(payload: dict[str, Any], schema_kind: str, name: str) -> None:
    try:
        validate_record(payload, schema_kind)
    except SchemaValidationError as exc:
        raise WebKf2Error(f"kf2-malformed-record:{name}") from exc


def _namespace_summary(
    vault: Path, path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "namespace",
        "path": _relative_posix(vault, path),
        "namespace_id": str(payload["namespace_id"]),
        "display_name": str(payload["display_name"]),
        "status": payload.get("status"),
    }


def _entity_summary(
    vault: Path, path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": "entity",
        "path": _relative_posix(vault, path),
        "entity_id": str(payload["entity_id"]),
        "namespace_id": str(payload["namespace_id"]),
        "display_name": str(payload["display_name"]),
        "status": payload.get("status"),
    }
    xproj = payload.get("xproj_global_entity_id")
    if isinstance(xproj, str) and xproj:
        row["xproj_global_entity_id"] = xproj
    return row


def _relationship_summary(
    vault: Path, path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "relationship",
        "path": _relative_posix(vault, path),
        "relationship_id": str(payload["relationship_id"]),
        "from_entity_id": str(payload["from_entity_id"]),
        "to_entity_id": str(payload["to_entity_id"]),
        "relation_type": payload.get("relation_type"),
        "status": payload.get("status"),
    }


def _list_kind(
    vault: Path,
    relative: Path,
    *,
    schema_kind: str,
    summarize: Callable[[Path, Path, dict[str, Any]], dict[str, Any]],
) -> tuple[ProjectionStatus, list[dict[str, Any]]]:
    _, root = _projection_root(vault, relative)
    if root is None:
        return "MISSING", []
    records: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.name.endswith(".json"):
            continue
        payload = _read_json_object(vault, path)
        _validate(payload, schema_kind, path.name)
        records.append(summarize(vault, path, payload))
    if records:
        return "PRESENT", records
    return "EMPTY", []


def _ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = [str(item[key]) for item in rows if key in item]
    values.sort(key=str.casefold)
    return values


def _rollup(
    namespaces: ProjectionStatus,
    entities: ProjectionStatus,
    relationships: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    states = (namespaces, entities, relationships)
    if any(state == "PRESENT" for state in states):
        return (
            "PRESENT",
            "persisted kf2 projections are visible; KF2 != AUTHORITY; NAME != IDENTITY",
            "ARTIFACTS_PRESENT",
            True,
        )
    if all(state == "MISSING" for state in states):
        return (
            "UNKNOWN",
            "kf2 projections are absent; absence is not registered and is not healthy",
            "ARTIFACTS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "kf2 projection directories exist but hold no records; EMPTY != HEALTHY",
        "ARTIFACTS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    namespace_status: ProjectionStatus,
    namespaces: list[dict[str, Any]],
    entity_status: ProjectionStatus,
    entities: list[dict[str, Any]],
    relationship_status: ProjectionStatus,
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "artifacts": {
            "namespaces": {
                "status": namespace_status,
                "path": NS_REL.as_posix(),
                "count": len(namespaces),
                "namespace_ids": _ids(namespaces, "namespace_id"),
                "records": namespaces,
            },
            "entities": {
                "status": entity_status,
                "path": ENTITY_REL.as_posix(),
                "count": len(entities),
                "entity_ids": _ids(entities, "entity_id"),
                "records": entities,
            },
            "relationships": {
                "status": relationship_status,
                "path": REL_REL.as_posix(),
                "count": len(relationships),
                "relationship_ids": _ids(relationships, "relationship_id"),
                "records": relationships,
            },
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_kf2(vault: Path) -> dict[str, Any]:
    """Read-only KF2 projection inspect. Never registers or writes."""
    root = _resolve_vault(vault)
    namespace_status, namespaces = _list_kind(
        root, NS_REL, schema_kind="kf2-namespace", summarize=_namespace_summary
    )
    entity_status, entities = _list_kind(
        root, ENTITY_REL, schema_kind="kf2-entity", summarize=_entity_summary
    )
    relationship_status, relationships = _list_kind(
        root,
        REL_REL,
        schema_kind="kf2-relationship",
        summarize=_relationship_summary,
    )
    status, reason, reason_code, available = _rollup(
        namespace_status, entity_status, relationship_status
    )
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        namespace_status=namespace_status,
        namespaces=namespaces,
        entity_status=entity_status,
        entities=entities,
        relationship_status=relationship_status,
        relationships=relationships,
    )


def render_kf2_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    artifacts = view.get("artifacts")
    namespaces: dict[str, Any] = {}
    entities: dict[str, Any] = {}
    relationships: dict[str, Any] = {}
    if isinstance(artifacts, dict):
        raw_ns = artifacts.get("namespaces")
        raw_entities = artifacts.get("entities")
        raw_rels = artifacts.get("relationships")
        if isinstance(raw_ns, dict):
            namespaces = raw_ns
        if isinstance(raw_entities, dict):
            entities = raw_entities
        if isinstance(raw_rels, dict):
            relationships = raw_rels
    lines = [
        f"atlas kf2 report [{view.get('status', 'UNKNOWN')}]",
        f"  available:      {view.get('available')}",
        f"  reason:         {view.get('reason_code')}",
        (
            "  namespaces:     "
            f"{namespaces.get('status', 'MISSING')} "
            f"count={namespaces.get('count', 0)}"
        ),
        (
            "  entities:       "
            f"{entities.get('status', 'MISSING')} "
            f"count={entities.get('count', 0)}"
        ),
        (
            "  relationships:  "
            f"{relationships.get('status', 'MISSING')} "
            f"count={relationships.get('count', 0)}"
        ),
        (
            "  honesty:        KF2 != AUTHORITY; NAME != IDENTITY; "
            "MISSING != REGISTERED; EMPTY != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
