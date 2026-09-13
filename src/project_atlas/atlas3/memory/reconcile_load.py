"""AT3-048-F4 — Fail-closed load of persisted memory reconcile artifacts.

Missing reconcile.json is empty. Corrupt or non-object JSON is not empty.
CLI consume paths must not AttributeError or report a healthy zero-hit search
when the artifact is unreadable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    Atlas3Error,
    require_project,
    require_vault,
)
from project_atlas.atlas3.memory.routing import assert_items_project_scope


def load_memory_reconcile(vault: Path | str, project_id: str) -> dict[str, Any] | None:
    """Return the on-disk reconcile object, or None if the file is absent."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = root / OPS_RELATIVE / "memory" / pid / "reconcile.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "RECONCILE_CORRUPT",
            "memory reconcile is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("RECONCILE_CORRUPT", "memory reconcile must be an object")
    return raw


def reconciliation_block(artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    """Nested reconciliation must be an object. A missing key is a flat artifact."""
    if artifact is None:
        return None
    nested = artifact.get("reconciliation")
    if nested is None:
        return artifact
    if not isinstance(nested, dict):
        raise Atlas3Error("RECONCILE_CORRUPT", "reconciliation must be an object")
    return nested


def reconciliation_items(
    block: dict[str, Any] | None,
    *,
    project_id: str,
) -> list[dict[str, Any]]:
    """Return scoped items. Mixed valid+corrupt fails closed."""
    if block is None:
        return []
    raw = block.get("items")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("RECONCILE_CORRUPT", "reconciliation items must be a list")
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Atlas3Error(
                "RECONCILE_CORRUPT",
                f"reconciliation item[{index}] must be an object",
            )
    assert_items_project_scope(raw, project_id=project_id)
    return raw


def reconciliation_conflicts(block: dict[str, Any] | None) -> dict[str, Any]:
    if block is None:
        return {"conflicted_history": False, "reason": "NO_RECONCILE"}
    raw = block.get("conflicts")
    if raw is None:
        return {"conflicted_history": False, "reason": "NO_RECONCILE"}
    if not isinstance(raw, dict):
        raise Atlas3Error("RECONCILE_CORRUPT", "conflicts must be an object")
    return raw


def reconciliation_stale(
    block: dict[str, Any] | None,
    *,
    project_id: str,
) -> list[dict[str, Any]]:
    if block is None:
        return []
    raw = block.get("stale_memories")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("RECONCILE_CORRUPT", "stale_memories must be a list")
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Atlas3Error(
                "RECONCILE_CORRUPT",
                f"stale_memories[{index}] must be an object",
            )
    assert_items_project_scope(raw, project_id=project_id)
    return raw
