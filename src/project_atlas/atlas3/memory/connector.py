"""AT3-035 — Provider-neutral connector framework."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, honesty_block

PACKAGE_ID: Final[str] = "AT3-035"
IMPORT_MODES: Final[frozenset[str]] = frozenset(
    {
        "EXPORT",
        "API",
        "LOCAL_SESSION",
        "PLUGIN",
        "MCP",
        "MANUAL",
        "STRUCTURED_SUBMISSION",
    }
)
PROVIDER_STATES: Final[frozenset[str]] = frozenset(
    {
        "CONNECTED",
        "AVAILABLE",
        "EXPORT_ONLY",
        "PARTIAL",
        "AUTH_REQUIRED",
        "PERMISSION_DENIED",
        "RATE_LIMITED",
        "UNSUPPORTED",
        "EXTERNAL_BLOCKED",
        "ERROR",
    }
)

ProviderAdapter = dict[str, Any]


def _adapter(
    provider: str,
    *,
    state: str,
    modes: list[str],
    live_full_history_sync: bool,
    notes: str,
) -> ProviderAdapter:
    return {
        "provider": provider,
        "state": state,
        "import_modes": modes,
        "live_full_history_sync": live_full_history_sync,
        "bootstrap_is_ingestion": False,
        "notes": notes,
        "package": PACKAGE_ID,
    }


DEFAULT_ADAPTERS: Final[dict[str, ProviderAdapter]] = {
    "chatgpt": _adapter(
        "chatgpt",
        state="EXPORT_ONLY",
        modes=["EXPORT", "STRUCTURED_SUBMISSION", "MCP"],
        live_full_history_sync=False,
        notes="Export import implemented on 2.x; live full-history sync not generalized.",
    ),
    "claude": _adapter(
        "claude",
        state="EXPORT_ONLY",
        modes=["EXPORT", "MANUAL", "STRUCTURED_SUBMISSION", "LOCAL_SESSION"],
        live_full_history_sync=False,
        notes="No private account history API claimed. CLAUDE.md is bootstrap only.",
    ),
    "gemini": _adapter(
        "gemini",
        state="EXPORT_ONLY",
        modes=["EXPORT", "MANUAL", "STRUCTURED_SUBMISSION"],
        live_full_history_sync=False,
        notes="No native history sync. GEMINI.md is bootstrap only.",
    ),
    "cursor": _adapter(
        "cursor",
        state="PARTIAL",
        modes=["LOCAL_SESSION", "STRUCTURED_SUBMISSION"],
        live_full_history_sync=False,
        notes=(
            "Structured fixture/session ingest implemented. "
            "Cursor Cloud history not implemented. AGENTS.md is bootstrap only."
        ),
    ),
    "codex": _adapter(
        "codex",
        state="PARTIAL",
        modes=["STRUCTURED_SUBMISSION", "LOCAL_SESSION"],
        live_full_history_sync=False,
        notes="Structured capture only.",
    ),
    "copilot": _adapter(
        "copilot",
        state="UNSUPPORTED",
        modes=[],
        live_full_history_sync=False,
        notes="No adapter yet.",
    ),
}

_REGISTRY: dict[str, ProviderAdapter] = dict(DEFAULT_ADAPTERS)


def register_provider(adapter: ProviderAdapter) -> ProviderAdapter:
    provider = str(adapter.get("provider") or "").strip().lower()
    state = str(adapter.get("state") or "")
    if provider not in DEFAULT_ADAPTERS and not provider:
        raise ValueError("provider is required")
    if state not in PROVIDER_STATES:
        raise ValueError(f"unknown provider state {state!r}")
    modes = [str(item) for item in (adapter.get("import_modes") or [])]
    if any(mode not in IMPORT_MODES for mode in modes):
        raise ValueError("unknown import mode")
    _REGISTRY[provider] = adapter
    return adapter


def provider_capabilities(provider: str | None = None) -> dict[str, Any]:
    if provider:
        key = provider.strip().lower()
        found = _REGISTRY.get(key)
        if found is None:
            return {
                "provider": key,
                "state": "UNSUPPORTED",
                "live_full_history_sync": False,
                "synchronized": False,
            }
        return {**found, "synchronized": False}
    return {
        "package": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "providers": {key: {**value, "synchronized": False} for key, value in _REGISTRY.items()},
        "fixture_coverage_is_sync": False,
    }


def connector_status() -> dict[str, Any]:
    return provider_capabilities()


Importer = Callable[..., list[dict[str, Any]]]
