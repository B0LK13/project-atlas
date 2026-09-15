"""AS-2.0-AGENT-EVAL-001 — Agent eval/shadow receipts (no subjective scores).

Bound to the Atlas 1.0 compatibility anchor. Never Layer B authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-AGENT-EVAL-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "AGENT EVAL SHADOW ≠ AUTHORITY / ≠ SUBJECTIVE SCORE"
SCHEMA_KIND = "agent-eval-shadow-receipt"


class AgentEvalShadowError(ValueError):
    """Fail-closed contract error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_agent_eval_shadow_receipt(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic agent-eval-shadow-receipt record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise AgentEvalShadowError("agent-eval-id-invalid")

    if bool(kwargs.get("promote_authority")):
        raise AgentEvalShadowError("agent-eval-authority-promote-forbidden")
    if bool(kwargs.get("allow_subjective_score")):
        raise AgentEvalShadowError("agent-eval-subjective-score-forbidden")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "mode": "shadow",
        "authority_promoted": False,
        "score_subjective": False,
        "cases_run": int(kwargs.get("cases_run", 0)),
        "authority": {
            "level": "derived",
            "note": "Shadow eval is observational; objective signals only",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise AgentEvalShadowError(f"agent-eval-shadow-receipt-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "agent-eval" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
