"""AS-CODER-ALPHA-XPROJ-READ-001 — vault-scoped REPORT READ lens.

Projects persisted AS-XPROJ-001/002/003 registry, edges, and duplicate
candidate artifacts so humans and agents can inspect derived
cross-project state. This module never writes edges, never registers
or joins identities, never merges identities, and never invents
cross-project facts.

Honesty:
- XPROJ != AUTHORITY
- GRAPH != AUTHORITY
- LENS != TRUTH CORE
- MISSING != NO_EDGES / != HEALTHY
- EMPTY != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-XPROJ-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-xproj-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.xproj-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = (
    "AS-XPROJ-001",
    "AS-XPROJ-002",
    "AS-XPROJ-003",
)
TRUTH_BOUNDARY: Final[str] = (
    "XPROJ != AUTHORITY / GRAPH != AUTHORITY / LENS != TRUTH CORE / "
    "MISSING != NO_EDGES / MISSING != HEALTHY / EMPTY != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

REGISTRY_REL: Final[Path] = Path("state") / "global-entities"
JOINS_REL: Final[Path] = REGISTRY_REL / "joins"
EDGES_REL: Final[Path] = REGISTRY_REL / "edges"
DUPLICATES_REL: Final[Path] = Path("generated") / "xproj" / "duplicate-candidates"

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "XPROJ != AUTHORITY",
    "GRAPH != AUTHORITY",
    "LENS != TRUTH CORE",
    "MISSING != NO_EDGES",
    "MISSING != HEALTHY",
    "EMPTY != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebXprojError(ValueError):
    """Fail-closed xproj REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "xproj_is_authority": False,
        "graph_is_authority": False,
        "lens_is_authority": False,
        "lens_is_truth_core": False,
        "missing_is_no_edges": False,
        "missing_is_healthy": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "identities_merged": False,
        "edges_written": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebXprojError(f"xproj-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebXprojError("xproj-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebXprojError(f"xproj-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebXprojError("xproj-path-escape")
    return resolved


def _projection_root(vault: Path, relative: Path) -> tuple[ProjectionStatus, Path | None]:
    raw = vault / relative
    if not raw.exists():
        return "MISSING", None
    if raw.is_symlink() or not raw.is_dir():
        raise WebXprojError(f"xproj-projection-not-directory:{relative.as_posix()}")
    return "EMPTY", _inside(vault, raw)


def _read_json_object(vault: Path, path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WebXprojError(f"xproj-not-regular-file:{path.name}")
    resolved = _inside(vault, path)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebXprojError(f"xproj-malformed-json:{path.name}") from exc
    except OSError as exc:
        raise WebXprojError(f"xproj-unreadable:{path.name}") from exc
    if not isinstance(loaded, dict):
        raise WebXprojError(f"xproj-json-not-object:{path.name}")
    return loaded


def _list_records(
    vault: Path,
    relative: Path,
    *,
    schema_kind: str,
) -> tuple[ProjectionStatus, list[dict[str, Any]]]:
    status, root = _projection_root(vault, relative)
    if root is None:
        return status, []
    records: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.name.endswith(".json"):
            continue
        payload = _read_json_object(vault, path)
        try:
            validate_record(payload, schema_kind)
        except SchemaValidationError as exc:
            raise WebXprojError(f"xproj-malformed-record:{path.name}") from exc
        records.append(payload)
    if records:
        return "PRESENT", records
    return "EMPTY", []


def _ids(records: list[dict[str, Any]], key: str) -> list[str]:
    values = [str(item[key]) for item in records if key in item]
    values.sort(key=str.casefold)
    return values


def _join_ids(records: list[dict[str, Any]]) -> list[str]:
    values = [
        (
            f"{item.get('project_id')}:"
            f"{item.get('project_local_entity_id')}:"
            f"{item.get('global_entity_id')}"
        )
        for item in records
    ]
    values.sort(key=str.casefold)
    return values


def _rollup(
    registry: ProjectionStatus,
    edges: ProjectionStatus,
    duplicates: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    states = (registry, edges, duplicates)
    if any(state == "PRESENT" for state in states):
        return (
            "PRESENT",
            "persisted xproj projections are visible; XPROJ != AUTHORITY",
            "PROJECTIONS_PRESENT",
            True,
        )
    if all(state == "MISSING" for state in states):
        return (
            "UNKNOWN",
            (
                "xproj projections are absent; absence is not no-edges "
                "and is not healthy"
            ),
            "PROJECTIONS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "xproj projection directories exist but hold no records; EMPTY != HEALTHY",
        "PROJECTIONS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    registry_status: ProjectionStatus,
    entities: list[dict[str, Any]],
    joins: list[dict[str, Any]],
    edges_status: ProjectionStatus,
    edges: list[dict[str, Any]],
    duplicates_status: ProjectionStatus,
    duplicates: list[dict[str, Any]],
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
        "projections": {
            "registry": {
                "status": registry_status,
                "path": REGISTRY_REL.as_posix(),
                "entity_count": len(entities),
                "join_count": len(joins),
                "entity_ids": _ids(entities, "global_entity_id"),
                "join_ids": _join_ids(joins),
            },
            "edges": {
                "status": edges_status,
                "path": EDGES_REL.as_posix(),
                "edge_count": len(edges),
                "edge_ids": _ids(edges, "edge_id"),
            },
            "duplicates": {
                "status": duplicates_status,
                "path": DUPLICATES_REL.as_posix(),
                "candidate_count": len(duplicates),
                "candidate_ids": _ids(duplicates, "candidate_id"),
            },
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_xproj(vault: Path) -> dict[str, Any]:
    """Read-only xproj projection. Never writes, joins, or merges identities."""
    root = _resolve_vault(vault)
    entity_status, entities = _list_records(
        root, REGISTRY_REL, schema_kind="xproj-global-entity"
    )
    join_status, joins = _list_records(root, JOINS_REL, schema_kind="xproj-join-key")
    if entity_status == "PRESENT" or join_status == "PRESENT":
        registry_status: ProjectionStatus = "PRESENT"
    elif entity_status == "EMPTY" or join_status == "EMPTY":
        registry_status = "EMPTY"
    else:
        registry_status = "MISSING"
    edges_status, edges = _list_records(root, EDGES_REL, schema_kind="xproj-global-edge")
    duplicates_status, duplicates = _list_records(
        root, DUPLICATES_REL, schema_kind="xproj-duplicate-candidate"
    )
    status, reason, reason_code, available = _rollup(
        registry_status, edges_status, duplicates_status
    )
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        registry_status=registry_status,
        entities=entities,
        joins=joins,
        edges_status=edges_status,
        edges=edges,
        duplicates_status=duplicates_status,
        duplicates=duplicates,
    )


def render_xproj_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    projections = view.get("projections")
    registry: dict[str, Any] = {}
    edges: dict[str, Any] = {}
    duplicates: dict[str, Any] = {}
    if isinstance(projections, dict):
        raw_registry = projections.get("registry")
        raw_edges = projections.get("edges")
        raw_duplicates = projections.get("duplicates")
        if isinstance(raw_registry, dict):
            registry = raw_registry
        if isinstance(raw_edges, dict):
            edges = raw_edges
        if isinstance(raw_duplicates, dict):
            duplicates = raw_duplicates
    lines = [
        f"atlas xproj report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        (
            "  registry:     "
            f"{registry.get('status', 'MISSING')} "
            f"entities={registry.get('entity_count', 0)} "
            f"joins={registry.get('join_count', 0)}"
        ),
        (
            "  edges:        "
            f"{edges.get('status', 'MISSING')} "
            f"count={edges.get('edge_count', 0)}"
        ),
        (
            "  duplicates:   "
            f"{duplicates.get('status', 'MISSING')} "
            f"count={duplicates.get('candidate_count', 0)}"
        ),
        (
            "  honesty:      XPROJ != AUTHORITY; GRAPH != AUTHORITY; "
            "LENS != TRUTH CORE; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
