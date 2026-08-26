"""AT3-006 — Isolated program security catalog.

Catalog != scanner != external certification.
EXTERNAL_SECURITY_REVALIDATION_REQUIRED remains YES.
Does not add a CLI command. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block
from project_atlas.atlas3.security import CONTROLS, THREATS, threat_model
from project_atlas.atlas3.security import PACKAGE_ID as CATALOG_SOURCE

PACKAGE_ID: Final[str] = "AT3-006"
GENERATOR_ID: Final[str] = "atlas3-security-catalog-006"


def compile_security_catalog(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report the reviewed threat catalog without claiming certification."""
    catalog = payload if payload is not None else threat_model()
    if not isinstance(catalog, dict):
        raise Atlas3Error("SECURITY_CATALOG_CORRUPT", "threat catalog must be an object")
    if catalog.get("external_security_certification") is True:
        raise Atlas3Error(
            "SECURITY_CERTIFICATION_CLAIMED",
            "catalog is not an external security certification",
        )
    if catalog.get("catalog_is_certification") is True or catalog.get("certified") is True:
        raise Atlas3Error(
            "SECURITY_CERTIFICATION_CLAIMED",
            "reviewed catalog is not a certification",
        )
    if catalog.get("catalog_is_scanner") is True:
        raise Atlas3Error("CATALOG_IS_SCANNER", "threat catalog is not a scanner")
    if str(catalog.get("external_security_certification") or "") == "PASS":
        raise Atlas3Error(
            "SECURITY_CERTIFICATION_CLAIMED",
            "EXTERNAL_SECURITY_CERTIFICATION remains required",
        )
    model = threat_model()
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "source_package": CATALOG_SOURCE,
        "status": "derived",
        "reason": "REVIEWED_THREAT_CATALOG",
        "threats": list(THREATS),
        "controls": dict(sorted(CONTROLS.items())),
        "threat_count": len(THREATS),
        "reviewed": True,
        "catalog_is_scanner": False,
        "catalog_is_certification": False,
        "external_security_certification": False,
        "external_security_revalidation_required": True,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "new_cli_command": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "source": {
            "package": model.get("package"),
            "reviewed": model.get("reviewed"),
            "external_security_certification": False,
        },
    }
