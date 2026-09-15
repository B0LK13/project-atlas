"""AS-2.1-OPS-RECEIPT-ADAPTER — read-only ops receipt inventory.

Lists reconstructable ops receipt metadata under generated/ops.
Honest UNKNOWN: missing or unreadable evidence never becomes healthy,
completion, PILOT PASS, or release certification.

Owned surface for Track A sole-writer; not authority / not Layer B.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-OPS-RECEIPT-ADAPTER"
# Prior Track B alias retained for consumers that still key on it.
LEGACY_PACKAGE_ID = "AS-2.1-OBS-RECEIPTS-001"
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


def _kind_status(kind_dir: Path) -> str:
    """Return present | absent | unknown for an allow-listed kind directory."""
    if not kind_dir.exists():
        return "absent"
    if not kind_dir.is_dir():
        return "unknown"
    return "present"


def inventory_ops_receipts(
    vault: Path,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Inventory ops receipt JSON files (metadata only; no claim promotion).

    Presence of files never upgrades rollup beyond ``unknown``. Malformed
    JSON stays ``parse=unknown``. Unscanned dirs under generated/ops are
    reported honestly rather than treated as healthy absence.
    """
    require_compatibility_anchor()
    if limit < 1 or limit > 500:
        raise ValueError("ops-receipt-limit-out-of-range")

    ops = vault / "generated" / "ops"
    rows: list[dict[str, Any]] = []
    kinds: dict[str, str] = {}
    truncated = False

    if not ops.exists():
        ops_root_status = "absent"
    elif not ops.is_dir():
        ops_root_status = "unknown"
    else:
        ops_root_status = "present"

    if ops_root_status == "present":
        for kind in _OPS_KINDS:
            kind_dir = ops / kind
            status = _kind_status(kind_dir)
            kinds[kind] = status
            if status != "present":
                continue
            for path in sorted(kind_dir.glob("*.json")):
                if path.name.endswith(".tmp"):
                    continue
                if len(rows) >= limit:
                    truncated = True
                    break
                row: dict[str, Any] = {
                    "kind": kind,
                    "name": path.name,
                    "relative_path": f"generated/ops/{kind}/{path.name}",
                    "bytes": path.stat().st_size,
                    # Row-level health is never inferred from file presence.
                    "health": "unknown",
                }
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        pkg = raw.get("package_id")
                        if isinstance(pkg, str) and pkg.strip():
                            row["package_id"] = pkg.strip()
                        # Never promote embedded rollup/health claims.
                        embedded = raw.get("rollup")
                        if isinstance(embedded, str) and embedded.strip():
                            row["embedded_rollup"] = embedded.strip()
                            row["embedded_rollup_promoted"] = False
                    else:
                        row["parse"] = "unknown"
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    row["parse"] = "unknown"
                rows.append(row)
            if truncated:
                break

        # Dirs under generated/ops outside the allow-list stay visible as
        # unscanned/unknown — never silent healthy omission.
        unscanned: list[str] = []
        try:
            for child in sorted(ops.iterdir()):
                if not child.is_dir():
                    continue
                if child.name not in _OPS_KINDS:
                    unscanned.append(child.name)
        except OSError:
            unscanned = []
    else:
        unscanned = []
        for kind in _OPS_KINDS:
            kinds[kind] = "unknown" if ops_root_status == "unknown" else "absent"

    available = len(rows) > 0
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "legacy_package_id": LEGACY_PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_source": "generated/ops" if available else "unavailable",
        "ops_root": ops_root_status,
        "receipt_rows": len(rows),
        "receipts": rows,
        "kinds": kinds,
        "unscanned_kinds": unscanned,
        "truncated": truncated,
        "limit": limit,
        "available": available,
        # Honest UNKNOWN: inventory never fabricates healthy ops.
        "rollup": "unknown",
        "health": "unknown",
        "unknown_equals_healthy": False,
        "completion_claimed": False,
        "authentic_pilot": False,
        "release_certified": False,
        "ui_canonical": False,
        "authority": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "note": (
            "Inventory of on-disk ops receipts only; absence stays unknown; "
            "presence never upgrades rollup to healthy; "
            "never infers PILOT PASS or release certification"
        ),
        "generated": {"by": "project-atlas"},
    }
