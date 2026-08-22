"""Generic closed-loop extension port for the resident driver (PR435).

PR435 owns this contract. Concrete mission reconciliation (PR436+) registers
an implementation at runtime. The resident must never statically import a
future child package module.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Final, Literal, Protocol, runtime_checkable

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

PROVIDER_MODULES: Final[tuple[str, ...]] = (
    "project_atlas.orchestration.sdk.mission_reconciler",
)
MODE_NAME: Final[str] = "d134-governor-mode.json"

GovernorMode = Literal[
    "RESIDENT_SCHEDULER_ONLY",
    "CLOSED_LOOP_MANDATORY",
    "DEGRADED_MISSION_RECONCILER_UNAVAILABLE",
]


@runtime_checkable
class ClosedLoopHook(Protocol):
    """Minimal surface the resident needs from a closed-loop work producer."""

    def reconcile(self, root: Path, *, now: float | None = None) -> dict[str, object]:
        """Run mission reconciliation / replenish READY."""

    def ready_work(self, root: Path, *, capacity: int = 2) -> list[ReadyWorkItem]:
        """Return READY work items (not workers)."""

    def active_worker_count(self, root: Path) -> int:
        """Count real execution bindings only."""

    def progress_state(self, root: Path) -> dict[str, object]:
        """Durable progress counters for observability."""

    def closed_loop_tick(self, root: Path, *, now: float | None = None) -> dict[str, object]:
        """One reconcile → dispatch → interpret cycle."""


_HOOK: ClosedLoopHook | None = None
_PROVIDERS_PROBED: bool = False


def register_closed_loop_hook(hook: ClosedLoopHook) -> None:
    """Bind a concrete closed-loop implementation (called by PR436+)."""
    global _HOOK
    _HOOK = hook


def clear_closed_loop_hook() -> None:
    """Test helper — remove registered hook."""
    global _HOOK, _PROVIDERS_PROBED
    _HOOK = None
    _PROVIDERS_PROBED = False


def get_closed_loop_hook() -> ClosedLoopHook | None:
    return _HOOK


def probe_optional_providers() -> bool:
    """Import known optional providers so they can self-register.

    Returns True if any provider module imported successfully.
    Never a static dependency of the resident driver.
    """
    global _PROVIDERS_PROBED
    imported = False
    for name in PROVIDER_MODULES:
        try:
            importlib.import_module(name)
            imported = True
        except ImportError:
            continue
    _PROVIDERS_PROBED = True
    return imported


def ensure_closed_loop_binding(*, require_if_provider_present: bool = True) -> GovernorMode:
    """Resolve governor mode after optional provider probe."""
    provider_present = probe_optional_providers()
    if _HOOK is not None:
        return "CLOSED_LOOP_MANDATORY"
    if provider_present and require_if_provider_present:
        return "DEGRADED_MISSION_RECONCILER_UNAVAILABLE"
    return "RESIDENT_SCHEDULER_ONLY"


def persist_governor_mode(root: Path, *, mode: GovernorMode, now: float) -> None:
    path = root / STATE_DIR_RELATIVE / MODE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    autonomy: Literal["YES", "FAIL", "NO"]
    if mode == "CLOSED_LOOP_MANDATORY":
        autonomy = "YES"
    elif mode == "DEGRADED_MISSION_RECONCILER_UNAVAILABLE":
        autonomy = "FAIL"
    else:
        autonomy = "NO"
    path.write_text(
        json.dumps(
            {
                "GOVERNOR_MODE": mode,
                "CLOSED_LOOP_AUTONOMY": autonomy,
                "MISSION_RECONCILER_MANDATORY_CYCLE": (
                    "YES" if mode == "CLOSED_LOOP_MANDATORY" else "NO"
                ),
                "at": now,
                "merge_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
