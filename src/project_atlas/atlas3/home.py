"""AT3-090 — Isolated Atlas Home composer.

Composes Pulse + Start + twin health. UI != canonical truth.
Does not invent a current task. Does not write Truth Core.
MERGE_AUTHORIZATION remains NOT_GRANTED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, Atlas3Error, honesty_block
from project_atlas.atlas3.pulse import compile_pulse
from project_atlas.atlas3.start import compile_start
from project_atlas.atlas3.twin_health import compile_twin_health

PACKAGE_ID: Final[str] = "AT3-090"
GENERATOR_ID: Final[str] = "atlas3-home-090"


def compile_home(
    vault: Path | str,
    project_id: str,
    *,
    token_budget: int,
    current_task: str | None = None,
    freshness_requirement: str = "UNKNOWN",
) -> dict[str, Any]:
    """Compose Pulse, Start, and twin health. Home is not Truth Core."""
    if token_budget <= 0:
        raise Atlas3Error(
            "TOKEN_BUDGET_REQUIRED",
            "atlas home requires an explicit positive --budget / token_budget",
        )
    pulse = compile_pulse(vault, project_id)
    start = compile_start(
        vault,
        project_id,
        token_budget=token_budget,
        current_task=current_task,
        freshness_requirement=freshness_requirement,
    )
    health = compile_twin_health(vault, project_id)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": str(pulse.get("project_id") or project_id),
        "pulse": pulse,
        "start": start,
        "twin_health": health,
        "ui_is_canonical_truth": False,
        "home_is_authority": False,
        "invented_current_task": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
