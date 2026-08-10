"""AS-2.1-PILOT-AUTH-001-PREP - authentic estate pilot preparation.

Searches only registry/known candidate roots. Never invents
``.atlas-project.yaml`` onto arbitrary disks. If zero roots: escalate
(AUTHENTIC_FOUND=0) — authentic PILOT remains release-critical.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-PILOT-AUTH-001-PREP"
TRUTH_BOUNDARY = (
    "PILOT PREP KNOWN-ROOT SEARCH != AUTHENTIC PILOT PASS / != ROOT INVENTION"
)
MARKER = ".atlas-project.yaml"


class PilotAuthPrepError(ValueError):
    """Fail-closed pilot prep error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def default_known_roots() -> list[Path]:
    """Conservative known-candidate list (registry/local conventions only)."""
    home = Path.home()
    return [
        home / "atlas-estate",
        home / "AtlasEstate",
        home / "projects" / "atlas-estate",
        Path("D:/atlas-estate"),
        Path("D:/AtlasEstate"),
        Path("C:/atlas-estate"),
    ]


def scan_known_pilot_roots(
    candidates: Iterable[Path] | None = None,
    *,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Scan known candidates for authentic markers; never create them."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("pilot.scan")
    found: list[dict[str, str]] = []
    missing: list[str] = []
    for raw in candidates if candidates is not None else default_known_roots():
        root = Path(raw)
        marker = root / MARKER
        if marker.is_file():
            found.append(
                {
                    "root": str(root.resolve()),
                    "marker": str(marker.resolve()),
                    "status": "FOUND",
                }
            )
        else:
            missing.append(str(root))
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "authentic_found": len(found),
        "found": found,
        "missing_count": len(missing),
        "missing_sample": missing[:20],
        "authentic_estate_pilot": False,
        "pilot_pass": False,
        "escalation_required": len(found) == 0,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }


def write_pilot_prep_report(
    vault: Path,
    *,
    report_id: str = "pilot-prep",
    candidates: Iterable[Path] | None = None,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Persist a prep report under generated/ops/pilot/."""
    payload = scan_known_pilot_roots(candidates, operator=operator)
    payload["report_id"] = report_id
    out = vault / "generated" / "ops" / "pilot" / f"{report_id}-prep.json"
    _atomic_write_json(out, payload)
    return payload
