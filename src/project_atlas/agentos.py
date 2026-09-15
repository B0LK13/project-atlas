"""AS-2.0-AGENTOS-001 — governed Agent OS session envelope.

Complementary to the sibling control plane. Does not mutate Core authority
planes. Bound to the Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-AGENTOS-001"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

Phase = Literal[
    "bootstrap",
    "preflight",
    "session-start",
    "work",
    "validation",
    "postflight",
    "closed",
]

PROTECTED_PATH_PREFIXES = (
    "projects/",
    "routing/state/",
    "routing/receipts/",
    "relationships/",
)


class AgentOsError(ValueError):
    """Fail-closed Agent OS envelope error."""


@dataclass(frozen=True, slots=True)
class SkillBinding:
    skill_id: str
    skill_sha256: str


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def open_session_envelope(
    vault: Path,
    *,
    session_id: str,
    task_id: str,
    phase: Phase = "bootstrap",
    skill: SkillBinding | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Create a governed session envelope under generated/ops/agentos/."""
    _ = anchor or require_compatibility_anchor()
    sid = session_id.strip()
    if not _ID_RE.fullmatch(sid):
        raise AgentOsError("agentos-session-id-invalid")
    tid = task_id.strip()
    if not tid or len(tid) > 128:
        raise AgentOsError("agentos-task-id-invalid")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "session_id": sid,
        "task_id": tid,
        "phase": phase,
        "protected_paths_acknowledged": True,
        "receipt_required": True,
        "authority": {
            "level": "derived",
            "note": "Agent OS envelope does not authorize Core authority writes",
        },
        "truth_boundary": "AGENT OS ENVELOPE ≠ CORE AUTHORITY",
        "generated": {"by": "project-atlas"},
    }
    if skill is not None:
        if not skill.skill_id.strip():
            raise AgentOsError("agentos-skill-id-empty")
        if not _SHA_RE.fullmatch(skill.skill_sha256):
            raise AgentOsError("agentos-skill-sha-invalid")
        payload["skill_binding"] = {
            "skill_id": skill.skill_id.strip(),
            "skill_sha256": skill.skill_sha256,
        }

    try:
        validate_record(payload, "agentos-session-envelope")
    except SchemaValidationError as exc:
        raise AgentOsError(f"agentos-schema:{exc}") from exc

    out = vault.resolve() / "generated" / "ops" / "agentos" / f"{sid}.json"
    _atomic_write_json(out, payload)
    return payload


def is_protected_path(relative_path: str) -> bool:
    """Return True when a relative vault path is agent-protected."""
    token = relative_path.replace("\\", "/").lstrip("./")
    return any(token == p.rstrip("/") or token.startswith(p) for p in PROTECTED_PATH_PREFIXES)
