"""AT3-101 — Isolated ledger observability.

Read-path integrity is mandatory. Corruption is not filtered into a
healthy count. The Event Ledger is evidence substrate, not Truth Core.
Does not add a CLI command. Does not write status artifacts.
MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    TRUTH_BOUNDARY,
    honesty_block,
    require_project,
    require_vault,
)
from project_atlas.atlas3.ledger import PACKAGE_ID as LEDGER_PACKAGE_ID
from project_atlas.atlas3.ledger import list_events

PACKAGE_ID: Final[str] = "AT3-101"
GENERATOR_ID: Final[str] = "atlas3-ledger-obs-101"


def compile_ledger_observability(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Observe a project ledger after validated read. Integrity failures raise."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    rows = list_events(root, pid)
    kinds: dict[str, int] = {}
    types: dict[str, int] = {}
    for row in rows:
        kind_key = str(row.get("kind") or "unknown")
        type_key = str(row.get("event_type") or "unknown")
        kinds[kind_key] = kinds.get(kind_key, 0) + 1
        types[type_key] = types.get(type_key, 0) + 1
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_id": LEDGER_PACKAGE_ID,
        "project_id": pid,
        "status": "derived" if rows else "UNKNOWN",
        "reason": "VALIDATED_LEDGER_READ" if rows else "NO_LEDGER_EVENTS",
        "integrity_state": "VALID",
        "event_count": len(rows),
        "kinds": dict(sorted(kinds.items())),
        "event_types": dict(sorted(types.items())),
        "healthy": False,
        "ledger_is_truth_core": False,
        "dual_writes_ops_events": False,
        "filtered_corrupt_rows": 0,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
