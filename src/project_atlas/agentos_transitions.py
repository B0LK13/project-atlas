"""AS-2.0-AGENTOS-002 — Agent OS phase-transition deepen.

Fail-closed phase transitions for AS-2.0-AGENTOS-001 envelopes. Never promotes
Core authority. Bound to Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-AGENTOS-002"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
Phase = Literal[
    "bootstrap",
    "preflight",
    "session-start",
    "work",
    "validation",
    "postflight",
    "closed",
]
ALLOWED: dict[Phase, frozenset[Phase]] = {
    "bootstrap": frozenset({"preflight"}),
    "preflight": frozenset({"session-start"}),
    "session-start": frozenset({"work"}),
    "work": frozenset({"work", "validation"}),
    "validation": frozenset({"postflight"}),
    "postflight": frozenset({"closed"}),
    "closed": frozenset(),
}
TRUTH_BOUNDARY = "AGENTOS TRANSITION ≠ CORE AUTHORITY"


class AgentOsTransitionError(ValueError):
    """Fail-closed Agent OS transition error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def record_phase_transition(
    vault: Path,
    *,
    transition_id: str,
    session_id: str,
    from_phase: Phase,
    to_phase: Phase,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Record a fail-closed Agent OS phase transition (≠ authority)."""
    _ = anchor or require_compatibility_anchor()
    tid = transition_id.strip()
    sid = session_id.strip()
    if not _ID_RE.fullmatch(tid) or not _ID_RE.fullmatch(sid):
        raise AgentOsTransitionError("agentos-transition-id-invalid")
    allowed = ALLOWED.get(from_phase, frozenset())
    if to_phase not in allowed:
        raise AgentOsTransitionError(
            f"agentos-transition-forbidden:{from_phase}->{to_phase}"
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "transition_id": tid,
        "session_id": sid,
        "from_phase": from_phase,
        "to_phase": to_phase,
        "receipt_required": True,
        "authority_promoted": False,
        "authority": {
            "level": "derived",
            "note": "Phase transitions do not authorize Core authority writes",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "agentos-phase-transition")
    except SchemaValidationError as exc:
        raise AgentOsTransitionError(f"agentos-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "agentos" / f"{tid}-transition.json"
    _atomic_write_json(out, payload)
    return payload
