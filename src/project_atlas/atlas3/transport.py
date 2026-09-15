"""AT3-071 — Isolated transport != authority prover.

TRANSPORT SUCCESS != AUTHORITY.
HTTP 200 / CLI 0 / MCP ok / A2A ack never grant truth, merge, or owner power.
Does not write Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block
from project_atlas.atlas3.surface import FORBIDDEN_CLAIMS, SURFACES, normalize_surface

PACKAGE_ID: Final[str] = "AT3-071"
GENERATOR_ID: Final[str] = "atlas3-transport-authority-071"
_SUCCESS_TRANSPORT: Final[frozenset[str]] = frozenset(
    {"0", "200", "ok", "success", "pass", "true", "ack"}
)


def prove_transport_is_not_authority(
    *,
    surface: str,
    transport_status: str,
    authority_claim: str | None = None,
) -> dict[str, Any]:
    """Prove a transport outcome is not authority. Owner-power claims fail closed."""
    surface_id = normalize_surface(surface)
    if not surface_id:
        raise Atlas3Error("SURFACE_REQUIRED", "surface is required")
    if surface_id not in SURFACES:
        raise Atlas3Error("SURFACE_UNKNOWN", f"unknown surface: {surface_id}")
    status = transport_status.strip()
    if not status:
        raise Atlas3Error("TRANSPORT_STATUS_REQUIRED", "transport_status is required")
    reported_success = status.lower() in _SUCCESS_TRANSPORT
    if authority_claim is not None:
        claim_id = authority_claim.strip().lower().replace(" ", "_")
        if not claim_id:
            raise Atlas3Error("CLAIM_REQUIRED", "authority_claim is required when provided")
        if claim_id in FORBIDDEN_CLAIMS:
            raise Atlas3Error(
                "TRANSPORT_IS_NOT_AUTHORITY",
                "transport success cannot grant authority, truth, merge, or owner power",
            )
        raise Atlas3Error(
            "AUTHORITY_CLAIM_UNKNOWN",
            f"unknown authority claim: {claim_id}",
        )
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "surface_id": surface_id,
        "transport_status": status,
        "transport_reported_success": reported_success,
        "transport_is_authority": False,
        "transport_success_is_authority": False,
        "availability_is_authorization": False,
        "is_authority": False,
        "writes_truth_core": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
