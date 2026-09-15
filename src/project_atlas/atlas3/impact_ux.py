"""AT3-095 — Isolated Impact Explorer UX.

Composes AT3-080 impact-explorer data for product UX. Does not add a
new CLI command (no proliferation). Graph != authority. Trust scores
fail closed via the data compiler. MERGE_AUTHORIZATION = NOT_GRANTED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY, honesty_block
from project_atlas.atlas3.impact import PACKAGE_ID as DATA_PACKAGE_ID
from project_atlas.atlas3.impact import compile_impact_explorer

PACKAGE_ID: Final[str] = "AT3-095"
GENERATOR_ID: Final[str] = "atlas3-impact-ux-095"
UX_SURFACE: Final[str] = "impact-explorer"


def compile_impact_ux(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compose Impact Explorer UX over declared impact data."""
    data = compile_impact_explorer(vault, project_id)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_id": DATA_PACKAGE_ID,
        "ux_surface": UX_SURFACE,
        "project_id": data["project_id"],
        "impacts": data["impacts"],
        "counts": data["counts"],
        "status": data["status"],
        "reason": data["reason"],
        "graph_is_authority": False,
        "trust_score_used": False,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
