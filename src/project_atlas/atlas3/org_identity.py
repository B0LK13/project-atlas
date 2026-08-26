"""AT3-111 — Isolated org identity.

Does not mint organization identity. Federation is not org identity.
Missing stays UNKNOWN. Estate availability is not authorization.
MERGE_AUTHORIZATION = NOT_GRANTED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_vault,
)

PACKAGE_ID: Final[str] = "AT3-111"
GENERATOR_ID: Final[str] = "atlas3-org-identity-111"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path) -> Path:
    return vault / OPS_RELATIVE / "org-identity" / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "ORG_IDENTITY_CORRUPT",
            "declared org identity is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("ORG_IDENTITY_CORRUPT", "declared org identity must be an object")
    return raw


def compile_org_identity(vault: Path | str) -> dict[str, Any]:
    """Report declared org identity without minting. Missing stays UNKNOWN."""
    root = require_vault(vault)
    path = _declared_path(root)
    if not path.is_file():
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
            "org_id": None,
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_ORG_IDENTITY",
            "org_identity_minted": False,
            "federation_is_org_identity": False,
            "estate_is_authorization": False,
            "certified_for_merge": False,
            "merge_authorization": "NOT_GRANTED",
            "promoted_to_truth_core": 0,
            "write_applied": False,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    if (
        declared.get("org_identity_minted") is True
        or declared.get("minted") is True
        or declared.get("create_org") is True
    ):
        raise Atlas3Error("ORG_IDENTITY_MINTED", "org identity must not be minted")
    if declared.get("federation_is_org_identity") is True:
        raise Atlas3Error(
            "FEDERATION_AUTHORITY_CLAIMED",
            "federation is not org identity",
        )
    if declared.get("estate_is_authorization") is True:
        raise Atlas3Error(
            "ESTATE_AUTHORIZATION_CLAIMED",
            "estate availability is not owner authorization",
        )
    org_id = str(declared.get("org_id") or "").strip() or None
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "org_id": org_id,
        "status": "derived" if org_id else "UNKNOWN",
        "reason": "DECLARED_ORG_IDENTITY" if org_id else "NO_ORG_ID",
        "org_identity_minted": False,
        "federation_is_org_identity": False,
        "estate_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
