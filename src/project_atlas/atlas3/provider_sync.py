"""AT3-102 — Isolated provider sync status.

Honest capability states only. Live full-history sync is not implemented.
AT3-046 incremental conversation sync remains EXTERNAL_BLOCKED.
CONNECTED / AVAILABLE is not synchronized. Does not add a CLI command.
MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block
from project_atlas.atlas3.memory.connector import PACKAGE_ID as CONNECTOR_PACKAGE_ID
from project_atlas.atlas3.memory.connector import provider_capabilities
from project_atlas.atlas3.memory.providers import memory_providers

PACKAGE_ID: Final[str] = "AT3-102"
GENERATOR_ID: Final[str] = "atlas3-provider-sync-102"
INCREMENTAL_PACKAGE_ID: Final[str] = "AT3-046"


def _reject_sync_authority(row: dict[str, Any], *, label: str) -> None:
    if row.get("live_full_history_sync") is True:
        raise Atlas3Error(
            "LIVE_HISTORY_SYNC_CLAIMED",
            f"{label} must not claim live full-history sync",
        )
    if row.get("synchronized") is True:
        raise Atlas3Error(
            "SYNC_AUTHORITY_CLAIMED",
            f"{label} synchronized is not implied by transport or presence",
        )
    if row.get("incremental_sync") is True or row.get("conversation_sync") is True:
        raise Atlas3Error(
            "INCREMENTAL_SYNC_CLAIMED",
            f"{label} incremental conversation sync is EXTERNAL_BLOCKED",
        )
    if str(row.get("conversation_sync") or "") in {"IMPLEMENTED", "LIVE"}:
        raise Atlas3Error(
            "INCREMENTAL_SYNC_CLAIMED",
            f"{label} live conversation sync is not implemented",
        )


def compile_provider_sync_status() -> dict[str, Any]:
    """Report honest provider sync capability. No provider is synchronized."""
    caps = provider_capabilities()
    matrix = memory_providers()
    providers = caps.get("providers")
    if not isinstance(providers, dict):
        raise Atlas3Error("PROVIDER_MATRIX_CORRUPT", "provider capabilities must be an object")
    observed: dict[str, dict[str, Any]] = {}
    for name, raw in sorted(providers.items()):
        if not isinstance(raw, dict):
            raise Atlas3Error("PROVIDER_MATRIX_CORRUPT", f"{name} capability must be an object")
        _reject_sync_authority(raw, label=name)
        observed[name] = {
            "provider": name,
            "state": str(raw.get("state") or "UNKNOWN"),
            "import_modes": list(raw.get("import_modes") or []),
            "live_full_history_sync": False,
            "synchronized": False,
            "incremental_sync": "EXTERNAL_BLOCKED",
        }
    for label, detail in (
        ("chatgpt_detail", matrix.get("chatgpt_detail")),
        ("claude_detail", matrix.get("claude_detail")),
        ("claude_current", matrix.get("claude_current")),
        ("gemini_detail", matrix.get("gemini_detail")),
        ("gemini_current", matrix.get("gemini_current")),
    ):
        if isinstance(detail, dict):
            _reject_sync_authority(detail, label=label)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_ids": [CONNECTOR_PACKAGE_ID, INCREMENTAL_PACKAGE_ID],
        "status": "derived",
        "reason": "HONEST_PROVIDER_SYNC_STATUS",
        "providers": observed,
        "counts": {"providers": len(observed)},
        "live_full_history_sync": False,
        "synchronized": False,
        "incremental_sync": "EXTERNAL_BLOCKED",
        "incremental_package_id": INCREMENTAL_PACKAGE_ID,
        "connected_is_synchronized": False,
        "fixture_coverage_is_sync": False,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
