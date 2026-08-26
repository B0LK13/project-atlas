"""AT3-056 — Fixture-level provider handoff.

Composes export ingest + AT3-054 rank + AT3-055 local serve so a second
provider can receive ranked memory without a live history API.
Does not rewrite Ask Atlas 2. Live multi-account product remains
EXTERNAL_BLOCKED.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    MERGE_AUTHORIZATION,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
)
from project_atlas.atlas3.memory.context_serve import ALLOWED_TARGETS, serve_ranked_context
from project_atlas.atlas3.memory.pipeline import ingest_provider_turns
from project_atlas.atlas3.memory.routing import require_memory_project

PACKAGE_ID: Final[str] = "AT3-056"
GENERATOR_ID: Final[str] = "atlas3-provider-handoff-056"
LIVE_MULTI_ACCOUNT: Final[str] = "EXTERNAL_BLOCKED"
_LIVE_VALUES: Final[frozenset[str]] = frozenset({"IMPLEMENTED", "LIVE", "SYNCED"})


def handoff_capability() -> dict[str, Any]:
    """Honest fixture-path handoff. Live multi-account product stays blocked."""
    return {
        "package": PACKAGE_ID,
        "fixture_handoff": "IMPLEMENTED",
        "live_multi_account_product": LIVE_MULTI_ACCOUNT,
        "live_full_history_sync": False,
        "native_history_api": False,
        "ask2_replaced": False,
        "writes_truth_core": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def fixture_provider_handoff(
    turns: object,
    *,
    source_provider: str,
    target_provider: str,
    conversation_id: str,
    project_id: str,
    import_mode: str = "EXPORT",
    owner_origin: dict[str, Any] | None = None,
    freshness_requirement: str = "UNKNOWN",
) -> dict[str, Any]:
    """Ingest source turns, rank, and serve a local pack to target_provider."""
    pid = require_memory_project(project_id)
    source = source_provider.strip().lower()
    target = target_provider.strip().lower()
    if source not in ALLOWED_TARGETS:
        raise Atlas3Error(
            "HANDOFF_SOURCE_INVALID",
            f"source_provider {source_provider!r} is not an allowed fixture source",
        )
    if target not in ALLOWED_TARGETS:
        raise Atlas3Error(
            "HANDOFF_TARGET_INVALID",
            f"target_provider {target_provider!r} is not an allowed fixture target",
        )
    if source == target:
        raise Atlas3Error(
            "HANDOFF_SAME_PROVIDER",
            "fixture handoff requires a different target provider",
        )
    if not isinstance(turns, list):
        raise Atlas3Error("HANDOFF_INVALID", "turns must be a list")
    for index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            raise Atlas3Error("HANDOFF_INVALID", f"turn[{index}] must be an object")
        if turn.get("live_full_history_sync") is True or turn.get("live_incremental_sync") is True:
            raise Atlas3Error(
                "HANDOFF_LIVE_CLAIMED",
                f"turn[{index}] must not claim live history sync",
            )
        sync = str(turn.get("conversation_sync") or "")
        if sync in _LIVE_VALUES:
            raise Atlas3Error(
                "HANDOFF_LIVE_CLAIMED",
                f"turn[{index}] live conversation sync is EXTERNAL_BLOCKED",
            )
        mode = str(turn.get("import_mode") or import_mode).strip().upper()
        if mode == "API":
            raise Atlas3Error("HANDOFF_LIVE_CLAIMED", "import_mode=API is not a fixture handoff")
    items = ingest_provider_turns(
        [turn for turn in turns if isinstance(turn, dict)],
        provider=source,
        conversation_id=conversation_id,
        project_id=pid,
        import_mode=import_mode,
        owner_origin=owner_origin,
    )
    served = serve_ranked_context(
        items,
        project_id=pid,
        target_provider=target,
        freshness_requirement=freshness_requirement,
    )
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "source_provider": source,
        "target_provider": target,
        "conversation_id": conversation_id,
        "item_count": len(items),
        "served": served,
        "fixture_handoff": True,
        "live_multi_account_product": LIVE_MULTI_ACCOUNT,
        "live_full_history_sync": False,
        "live_handoff_used": False,
        "ask2_replaced": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
