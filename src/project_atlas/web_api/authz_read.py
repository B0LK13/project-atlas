"""AS-CODER-ALPHA-AUTHZ-READ-001 -- vault-scoped authz REPORT READ.

Read-only wrap of the existing ``GET /v1/authz`` operator profile
projection (AS-2.1-AUTHZ-001). This module never grants write, never
mints sessions, never elevates, and never invents OWNER / MERGE /
SECURITY authority.

Honesty:
- AUTHZ != AUTHORITY
- PROFILE != GRANT
- CAPABILITY_LIST != OWNER_GATE
- WRITE_ENABLED=false
- MCP != AUTHORITY
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.authz import (
    DEFAULT_OPERATOR_CAPS,
    PRIVILEGED_CAPABILITIES,
    OperatorProfile,
    default_operator,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-AUTHZ-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-authz-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.authz-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.1-AUTHZ-001",)
SOURCE_ROUTE: Final[str] = "/v1/authz"
TRUTH_BOUNDARY: Final[str] = (
    "AUTHZ != AUTHORITY / PROFILE != GRANT / CAPABILITY_LIST != OWNER_GATE / "
    "WRITE_ENABLED=false / MCP != AUTHORITY / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "AUTHZ != AUTHORITY",
    "PROFILE != GRANT",
    "CAPABILITY_LIST != OWNER_GATE",
    "WRITE_ENABLED=false",
    "MCP != AUTHORITY",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

class WebAuthzReadError(ValueError):
    """Fail-closed authz REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "authz_is_authority": False,
        "profile_is_grant": False,
        "capability_list_is_owner_gate": False,
        "write_enabled": False,
        "WRITE_ENABLED": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "owner_authority_invented": False,
        "merge_authority_invented": False,
        "security_authority_invented": False,
        "owner_gate": False,
        "merge_authorized": False,
        "security_authority_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebAuthzReadError(f"authz-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebAuthzReadError("authz-read-vault-missing")
    return root


def _existing_authz_projection(operator: OperatorProfile) -> dict[str, Any]:
    """Byte-stable projection of existing GET /v1/authz. Never grants write."""
    return {
        "package_id": "AS-2.1-AUTHZ-001",
        "operator_id": operator.operator_id,
        "capabilities": sorted(operator.capabilities),
        "authority": False,
        "write_enabled": False,
    }


def _envelope(
    *,
    operator: OperatorProfile,
) -> dict[str, Any]:
    profile = _existing_authz_projection(operator)
    privileged_listed = sorted(
        cap for cap in operator.capabilities if cap in PRIVILEGED_CAPABILITIES
    )
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_route": SOURCE_ROUTE,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": True,
        "status": "PRESENT",
        "reason": (
            "existing GET /v1/authz operator profile is projected; "
            "AUTHZ != AUTHORITY; PROFILE != GRANT; "
            "CAPABILITY_LIST != OWNER_GATE; WRITE_ENABLED=false"
        ),
        "reason_code": "PROFILE_PROJECTED",
        "profile": profile,
        "privileged_capabilities_listed": privileged_listed,
        "privileged_capabilities_granted": [],
        "default_read_capabilities": sorted(DEFAULT_OPERATOR_CAPS),
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_authz_profile(
    vault: Path,
    *,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Read-only wrap of GET /v1/authz. Never writes. Never grants."""
    _resolve_vault(vault)
    op = operator or default_operator()
    return _envelope(operator=op)


def render_authz_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    profile: dict[str, Any] = {}
    raw_profile = view.get("profile")
    if isinstance(raw_profile, dict):
        profile = raw_profile
    caps = profile.get("capabilities")
    cap_count = len(caps) if isinstance(caps, list) else 0
    lines = [
        f"atlas authz report [{view.get('status', 'UNKNOWN')}]",
        f"  available:      {view.get('available')}",
        f"  reason:         {view.get('reason_code')}",
        f"  source_route:   {view.get('source_route', SOURCE_ROUTE)}",
        f"  operator_id:    {profile.get('operator_id', 'UNKNOWN')}",
        f"  capabilities:   {cap_count}",
        f"  authority:      {profile.get('authority')}",
        f"  write_enabled:  {profile.get('write_enabled')}",
        (
            "  honesty:        AUTHZ != AUTHORITY; PROFILE != GRANT; "
            "CAPABILITY_LIST != OWNER_GATE; WRITE_ENABLED=false; "
            "MCP != AUTHORITY"
        ),
    ]
    return "\n".join(lines) + "\n"
