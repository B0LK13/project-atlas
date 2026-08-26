"""AT3-072 — Isolated provider-register / capabilities CLI design.

Design contract only. No CLI proliferation.
Provider register is not a live history API and not a capability itself.
Does not write Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final

from project_atlas.atlas3.capabilities import list_capabilities
from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block
from project_atlas.atlas3.memory.providers import memory_providers

PACKAGE_ID: Final[str] = "AT3-072"
GENERATOR_ID: Final[str] = "atlas3-provider-register-072"
ALLOWED_CLI: Final[frozenset[str]] = frozenset(
    {
        "pulse",
        "start",
        "proof",
        "memory",
        "ledger",
        "capabilities",
        "compatibility",
        "inventory",
        "file-graph",
        "estate-nodes",
        "causal-graph",
        "decided-by",
        "rel-expand",
        "iv-bind",
        "adv-bind",
        "surface-contract",
        "transport-authority",
        "provider-register",
        "impact-explorer",
        "twin-health",
        "home",
        "timeline",
    }
)
FORBIDDEN_CLI: Final[frozenset[str]] = frozenset(
    {
        "query.read",
        "atlas.query.read",
        "chatgpt-sync-live",
        "live-history-sync",
    }
)


def compile_provider_register() -> dict[str, Any]:
    """Return the isolated provider-register / capabilities CLI design."""
    providers = memory_providers()
    capabilities = list_capabilities()
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "design_only": True,
        "cli_proliferation": False,
        "live_provider_register": False,
        "live_full_history_sync": False,
        "allowed_cli": sorted(ALLOWED_CLI),
        "providers": providers,
        "capabilities": capabilities.get("capabilities"),
        "surface_is_capability": False,
        "register_is_authority": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def assert_cli_design(proposed_commands: Iterable[str]) -> dict[str, Any]:
    """Refuse CLI proliferation and forbidden live-sync wrappers."""
    proposed = [item.strip() for item in proposed_commands if str(item).strip()]
    if not proposed:
        raise Atlas3Error("CLI_DESIGN_REQUIRED", "proposed_commands is required")
    forbidden = sorted({item for item in proposed if item in FORBIDDEN_CLI})
    if forbidden:
        raise Atlas3Error(
            "FORBIDDEN_CLI",
            "live-sync and query.read wrappers are not part of the CLI design",
        )
    extra = sorted({item for item in proposed if item not in ALLOWED_CLI})
    if extra:
        raise Atlas3Error(
            "CLI_PROLIFERATION",
            "proposed commands exceed the AT3-072 allowlist",
        )
    catalog = compile_provider_register()
    catalog["proposed_commands"] = sorted(set(proposed))
    catalog["accepted"] = True
    return catalog
