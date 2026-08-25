"""AS-CODER-ALPHA-INTELLIGENCE-READ-001 -- vault-scoped intelligence REPORT READ.

Zero-arg status index of existing ``/v1/intelligence/{evidence,conflicts,
explain,query}`` derived views. This module never computes those answers,
never writes Layer B, and never treats graph or derived intelligence as
Truth Core.

Honesty:
- INTELLIGENCE != AUTHORITY
- GRAPH != AUTHORITY
- DERIVED != TRUTH CORE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INTELLIGENCE-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-intelligence-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.intelligence-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-API-001",)
TRUTH_BOUNDARY: Final[str] = (
    "INTELLIGENCE != AUTHORITY / GRAPH != AUTHORITY / DERIVED != TRUTH CORE / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

PROJECTS_REL: Final[Path] = Path("projects")

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "INTELLIGENCE != AUTHORITY",
    "GRAPH != AUTHORITY",
    "DERIVED != TRUTH CORE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

INTELLIGENCE_ROUTES: Final[tuple[dict[str, Any], ...]] = (
    {
        "path": "/v1/intelligence/evidence",
        "kind": "evidence",
        "method": "GET",
        "scope": "project",
        "writes_layer_b": False,
        "is_authority": False,
        "graph_is_authority": False,
        "derived_is_truth_core": False,
    },
    {
        "path": "/v1/intelligence/conflicts",
        "kind": "conflicts",
        "method": "GET",
        "scope": "project",
        "writes_layer_b": False,
        "is_authority": False,
        "graph_is_authority": False,
        "derived_is_truth_core": False,
    },
    {
        "path": "/v1/intelligence/explain",
        "kind": "explain",
        "method": "GET",
        "scope": "project",
        "writes_layer_b": False,
        "is_authority": False,
        "graph_is_authority": False,
        "derived_is_truth_core": False,
    },
    {
        "path": "/v1/intelligence/query",
        "kind": "query",
        "method": "GET",
        "scope": "project",
        "writes_layer_b": False,
        "is_authority": False,
        "graph_is_authority": False,
        "derived_is_truth_core": False,
    },
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "INDEXED"]


class WebIntelligenceReadError(ValueError):
    """Fail-closed intelligence REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "intelligence_is_authority": False,
        "graph_is_authority": False,
        "derived_is_truth_core": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "layer_b_written": False,
        "answers_computed": False,
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
        raise WebIntelligenceReadError(f"intel-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebIntelligenceReadError("intel-read-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebIntelligenceReadError(f"intel-read-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebIntelligenceReadError("intel-read-path-escape")
    return resolved


def _list_projects(vault: Path) -> tuple[ProjectionStatus, list[str]]:
    raw = vault / PROJECTS_REL
    if not raw.exists():
        return "MISSING", []
    if raw.is_symlink() or not raw.is_dir():
        raise WebIntelligenceReadError("intel-read-projects-not-directory")
    root = _inside(vault, raw)
    project_ids: list[str] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink() or not entry.is_dir():
            if entry.is_symlink():
                raise WebIntelligenceReadError(f"intel-read-not-regular-dir:{entry.name}")
            continue
        _inside(vault, entry)
        project_ids.append(entry.name)
    if project_ids:
        return "PRESENT", project_ids
    return "EMPTY", []


def _rollup(
    projects_status: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    if projects_status == "PRESENT":
        return (
            "INDEXED",
            (
                "intelligence route index is visible; INTELLIGENCE != AUTHORITY; "
                "GRAPH != AUTHORITY; DERIVED != TRUTH CORE"
            ),
            "ROUTES_INDEXED",
            True,
        )
    if projects_status == "MISSING":
        return (
            "UNKNOWN",
            "projects tree is absent; absence is not healthy and is not authority",
            "PROJECTS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "projects tree exists but holds no project ids; EMPTY != HEALTHY",
        "PROJECTS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    projects_status: ProjectionStatus,
    project_ids: list[str],
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
        "routes": [dict(route) for route in INTELLIGENCE_ROUTES],
        "projects": {
            "status": projects_status,
            "path": PROJECTS_REL.as_posix(),
            "count": len(project_ids),
            "project_ids": project_ids,
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_intelligence_index(vault: Path) -> dict[str, Any]:
    """Read-only intelligence route index. Never writes Layer B or computes answers."""
    root = _resolve_vault(vault)
    projects_status, project_ids = _list_projects(root)
    status, reason, reason_code, available = _rollup(projects_status)
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        projects_status=projects_status,
        project_ids=project_ids,
    )


def render_intelligence_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    projects: dict[str, Any] = {}
    raw_projects = view.get("projects")
    if isinstance(raw_projects, dict):
        projects = raw_projects
    routes = view.get("routes")
    kinds: list[str] = []
    if isinstance(routes, list):
        for row in routes:
            if isinstance(row, dict) and isinstance(row.get("kind"), str):
                kinds.append(row["kind"])
    lines = [
        f"atlas intelligence report [{view.get('status', 'UNKNOWN')}]",
        f"  available:      {view.get('available')}",
        f"  reason:         {view.get('reason_code')}",
        f"  routes:         {','.join(kinds) if kinds else 'none'}",
        (
            "  projects:       "
            f"{projects.get('status', 'MISSING')} "
            f"count={projects.get('count', 0)}"
        ),
        (
            "  honesty:        INTELLIGENCE != AUTHORITY; GRAPH != AUTHORITY; "
            "DERIVED != TRUTH CORE; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
