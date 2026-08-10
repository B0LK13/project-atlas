"""AS-2.1 ops receipt inventory adapter (read-only).

Lists reconstructable ops receipt metadata under generated/ops.
Never fabricates completion claims. Missing receipts stay unknown.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-OBS-RECEIPTS-001"
TRUTH_BOUNDARY = (
    "OPS RECEIPT INVENTORY != COMPLETION CLAIM / UNKNOWN!=HEALTHY / != AUTHORITY"
)

# Bounded allow-list of ops subdirs scanned for *.json receipts.
_OPS_KINDS: tuple[str, ...] = (
    "obs",
    "scheduler",
    "autonomy",
    "web-actions",
    "chatgpt",
    "collab",
    "provider",
    "openai-import",
    "oai-responses-poc",
    "authz",
    "pilot",
    "perf",
    "provider-quarantine",
)


def inventory_ops_receipts(
    vault: Path,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Inventory ops receipt JSON files (metadata only; no claim promotion)."""
    require_compatibility_anchor()
    if limit < 1 or limit > 500:
        raise ValueError("ops-receipt-limit-out-of-range")
    ops = vault / "generated" / "ops"
    rows: list[dict[str, Any]] = []
    if ops.is_dir():
        for kind in _OPS_KINDS:
            kind_dir = ops / kind
            if not kind_dir.is_dir():
                continue
            for path in sorted(kind_dir.glob("*.json")):
                if path.name.endswith(".tmp"):
                    continue
                row: dict[str, Any] = {
                    "kind": kind,
                    "name": path.name,
                    "relative_path": f"generated/ops/{kind}/{path.name}",
                    "bytes": path.stat().st_size,
                }
                # Optional package_id peek (fail-soft; never elevate).
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        pkg = raw.get("package_id")
                        if isinstance(pkg, str) and pkg.strip():
                            row["package_id"] = pkg.strip()
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    row["parse"] = "unknown"
                rows.append(row)
                if len(rows) >= limit:
                    break
            if len(rows) >= limit:
                break
    available = len(rows) > 0
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_source": "generated/ops" if available else "unavailable",
        "receipt_rows": len(rows),
        "receipts": rows,
        "available": available,
        "rollup": "unknown",
        "completion_claimed": False,
        "ui_canonical": False,
        "authority": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "note": (
            "Inventory of on-disk ops receipts only; absence stays unknown; "
            "never infers PILOT PASS or release certification"
        ),
        "generated": {"by": "project-atlas"},
    }
