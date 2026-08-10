"""AS-2.0-KCI-HARNESS-001 — Knowledge CI harness gate catalog (≠ authority).

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

PACKAGE_ID = "AS-2.0-KCI-HARNESS-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "KNOWLEDGE CI HARNESS ≠ AUTHORITY PROMOTE"
SCHEMA_KIND = "knowledge-ci-harness"


class KnowledgeCiHarnessError(ValueError):
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


def build_knowledge_ci_harness(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic knowledge-ci-harness record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise KnowledgeCiHarnessError("kci-harness-id-invalid")

    if bool(kwargs.get("promote_authority")):
        raise KnowledgeCiHarnessError("kci-harness-authority-promote-forbidden")
    gates = kwargs.get("gates") or [
        {"gate_id": "schema", "kind": "schema", "required": True},
        {"gate_id": "pytest", "kind": "pytest", "required": True},
        {"gate_id": "ruff", "kind": "ruff", "required": True},
        {"gate_id": "mypy", "kind": "mypy", "required": True},
        {"gate_id": "compat", "kind": "compat", "required": True},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "harness_id": rid,
        "authority_promoted": False,
        "gates": list(gates),
        "authority": {
            "level": "derived",
            "note": "Knowledge CI harness catalogs gates; never promotes authority",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise KnowledgeCiHarnessError(f"knowledge-ci-harness-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "kci" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
