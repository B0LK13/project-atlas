"""AS-2.1 observability polish - live surface health receipt.

Records which 2.1 live packages are present as an ops observability snapshot.
Operational plane only; never authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-OBS-LIVE-001"
TRUTH_BOUNDARY = "OBS LIVE != AUTHORITY / UNKNOWN!=HEALTHY"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_live_observability_receipt(
    vault: Path,
    *,
    receipt_id: str = "live-obs",
) -> dict[str, Any]:
    """Build a deterministic live-surface observability receipt."""
    require_compatibility_anchor()
    ops = vault / "generated" / "ops"
    surfaces = {
        "api_server": True,
        "mcp_server": True,
        "web_actions": (ops / "web-actions").exists(),
        "chatgpt_bridge": (ops / "chatgpt").exists(),
        "collab": (ops / "collab").exists(),
        "provider_live": (ops / "provider").exists(),
        "scheduler": (ops / "scheduler").exists(),
        "autonomy_l3": (ops / "autonomy").exists(),
        "oai_responses_poc": (ops / "oai-responses-poc").exists(),
        "authz_audit": (ops / "authz").exists(),
        "pilot_prep": (ops / "pilot").exists(),
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": receipt_id,
        "surfaces": surfaces,
        "rollup": "unknown",
        "note": "Presence flags only; missing surface != healthy",
        "truth_boundary": TRUTH_BOUNDARY,
        "authority_plane": "none",
        "generated": {"by": "project-atlas"},
    }
    out = ops / "obs" / f"{receipt_id}-live.json"
    _atomic_write_json(out, payload)
    return payload
