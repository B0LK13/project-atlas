"""AT3-070 — Isolated surface contract (CLI/API/Web/TUI/MCP/A2A).

Surfaces are transports and projections, not authority.
SURFACE != TRUTH CORE. TRANSPORT SUCCESS != AUTHORITY.
Surface availability != owner authorization.
Never writes Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block

PACKAGE_ID: Final[str] = "AT3-070"
GENERATOR_ID: Final[str] = "atlas3-surface-contract-070"
SURFACES: Final[frozenset[str]] = frozenset({"cli", "api", "web", "tui", "mcp", "a2a"})
_SURFACE_ALIASES: Final[dict[str, str]] = {
    "live_api": "api",
    "live-api": "api",
    "liveapi": "api",
}
ALLOWED_CLAIMS: Final[frozenset[str]] = frozenset(
    {"projection", "derived", "read", "transport"}
)
FORBIDDEN_CLAIMS: Final[frozenset[str]] = frozenset(
    {
        "authority",
        "truth_core",
        "truth-core",
        "merge",
        "owner",
        "security",
        "human",
        "release",
        "governor",
        "signoff",
    }
)
_SUCCESS_TRANSPORT: Final[frozenset[str]] = frozenset(
    {"0", "200", "ok", "success", "pass", "true"}
)


def _normalize_surface(surface: str) -> str:
    token = surface.strip().lower().replace(" ", "_")
    return _SURFACE_ALIASES.get(token, token)


def _surface_record(surface_id: str) -> dict[str, Any]:
    return {
        "surface_id": surface_id,
        "kind": "transport",
        "is_authority": False,
        "writes_truth_core": False,
        "availability_is_authorization": False,
        "transport_success_is_authority": False,
        "owner_gate_required_for_mutation": True,
    }


def compile_surface_contract() -> dict[str, Any]:
    """Return the isolated CLI/API/Web/TUI/MCP/A2A surface contract."""
    catalog = [_surface_record(name) for name in sorted(SURFACES)]
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "surfaces": catalog,
        "surface_count": len(catalog),
        "surface_is_authority": False,
        "transport_success_is_authority": False,
        "availability_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def evaluate_surface_claim(
    *,
    surface: str,
    claim: str,
    transport_status: str | None = None,
) -> dict[str, Any]:
    """Prove one surface claim. Authority and unknown surfaces fail closed."""
    surface_id = _normalize_surface(surface)
    if not surface_id:
        raise Atlas3Error("SURFACE_REQUIRED", "surface is required")
    if surface_id not in SURFACES:
        raise Atlas3Error("SURFACE_UNKNOWN", f"unknown surface: {surface_id}")
    claim_id = claim.strip().lower().replace(" ", "_")
    if not claim_id:
        raise Atlas3Error("CLAIM_REQUIRED", "claim is required")
    if claim_id in FORBIDDEN_CLAIMS:
        raise Atlas3Error(
            "SURFACE_CLAIM_FORBIDDEN",
            "surface may not claim authority, truth, merge, or owner power",
        )
    if claim_id not in ALLOWED_CLAIMS:
        raise Atlas3Error("SURFACE_CLAIM_UNKNOWN", f"unknown surface claim: {claim_id}")
    status = None if transport_status is None else transport_status.strip()
    reported_success = status is not None and status.lower() in _SUCCESS_TRANSPORT
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "surface_id": surface_id,
        "claim": claim_id,
        "accepted": True,
        "is_authority": False,
        "writes_truth_core": False,
        "availability_is_authorization": False,
        "transport_success_is_authority": False,
        "transport_reported_success": reported_success,
        "transport_status": status,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
