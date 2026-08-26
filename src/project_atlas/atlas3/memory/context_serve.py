"""AT3-055 — Local provider-neutral ranked-context serve.

Serves an AT3-054 ranked pack as a local envelope for another provider.
Does not call provider APIs. Live serve remains EXTERNAL_BLOCKED.
Does not write Truth Core. Does not rewrite Ask Atlas 2.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    MERGE_AUTHORIZATION,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
)
from project_atlas.atlas3.memory.context_compiler import compile_memory_context
from project_atlas.atlas3.memory.routing import require_memory_project

PACKAGE_ID: Final[str] = "AT3-055"
GENERATOR_ID: Final[str] = "atlas3-context-serve-055"
LIVE_PROVIDER_SERVE: Final[str] = "EXTERNAL_BLOCKED"
ALLOWED_TARGETS: Final[frozenset[str]] = frozenset(
    {"chatgpt", "claude", "gemini", "cursor"}
)
_LIVE_VALUES: Final[frozenset[str]] = frozenset({"IMPLEMENTED", "LIVE", "SYNCED"})
_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "credentials",
        "api_key",
        "authorization",
        "access_token",
        "bearer",
        "password",
    }
)


def context_serve_capability() -> dict[str, Any]:
    """Honest local-pack serve. Live provider serve stays blocked."""
    return {
        "package": PACKAGE_ID,
        "local_ranked_pack": "IMPLEMENTED",
        "live_provider_serve": LIVE_PROVIDER_SERVE,
        "live_full_history_sync": False,
        "native_history_api": False,
        "ask2_replaced": False,
        "writes_truth_core": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "allowed_targets": sorted(ALLOWED_TARGETS),
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def _reject_live_or_secret(row: dict[str, Any], *, label: str) -> None:
    if row.get("live_provider_serve") is True or row.get("live_full_history_sync") is True:
        raise Atlas3Error(
            "CONTEXT_SERVE_LIVE_CLAIMED",
            f"{label} must not claim live provider serve",
        )
    if row.get("history_api") is True or row.get("native_history_api") is True:
        raise Atlas3Error(
            "CONTEXT_SERVE_LIVE_CLAIMED",
            f"{label} native history API is EXTERNAL_BLOCKED",
        )
    sync = str(row.get("conversation_sync") or row.get("provider_serve") or "")
    if sync in _LIVE_VALUES:
        raise Atlas3Error(
            "CONTEXT_SERVE_LIVE_CLAIMED",
            f"{label} live serve is EXTERNAL_BLOCKED",
        )
    for key in _SECRET_KEYS:
        if row.get(key):
            raise Atlas3Error(
                "CONTEXT_SERVE_CREDENTIAL_REFUSED",
                f"{label} must not carry {key}",
            )


def serve_ranked_context(
    items: object,
    *,
    project_id: str,
    target_provider: str,
    include_stale_historical: bool = False,
    freshness_requirement: str = "UNKNOWN",
) -> dict[str, Any]:
    """Build a local ranked pack addressed to one allowed provider."""
    pid = require_memory_project(project_id)
    target = target_provider.strip().lower()
    if target not in ALLOWED_TARGETS:
        raise Atlas3Error(
            "CONTEXT_SERVE_TARGET_INVALID",
            f"target_provider {target_provider!r} is not an allowed local pack target",
        )
    ranked = compile_memory_context(
        items,
        project_id=pid,
        include_stale_historical=include_stale_historical,
        freshness_requirement=freshness_requirement,
    )
    if not isinstance(ranked, dict):
        raise Atlas3Error("CONTEXT_SERVE_INVALID", "ranked pack must be an object")
    _reject_live_or_secret(ranked, label="ranked")
    if ranked.get("write_applied") is True:
        raise Atlas3Error("CONTEXT_WRITE_CLAIMED", "serve pack is consume-only")
    if ranked.get("promoted_to_truth_core") not in {None, 0}:
        raise Atlas3Error("TRUTH_CORE_WRITE", "serve pack must not promote to Truth Core")
    if ranked.get("stale_presented_as_current") is True:
        raise Atlas3Error("STALE_AS_CURRENT", "serve pack must not treat stale as current")
    layers = ranked.get("layers")
    if not isinstance(layers, dict):
        raise Atlas3Error("CONTEXT_SERVE_INVALID", "ranked layers must be an object")
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "target_provider": target,
        "served": {
            "rank_order": ranked.get("rank_order"),
            "layers": layers,
            "freshness_requirement": ranked.get("freshness_requirement"),
            "unknown_stays_unknown": ranked.get("unknown_stays_unknown"),
        },
        "consume_only": True,
        "local_ranked_pack": True,
        "live_provider_serve": LIVE_PROVIDER_SERVE,
        "live_full_history_sync": False,
        "live_serve_used": False,
        "ask2_replaced": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
