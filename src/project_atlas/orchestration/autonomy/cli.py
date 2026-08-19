"""CLI runners for the autonomous governor. Not dispatch and not merge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from project_atlas.orchestration.autonomy.discovery import collect_live_inventory, discover
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor, run_live_pilot
from project_atlas.orchestration.autonomy.models import (
    AUTONOMY_PACKAGE_ID,
    EXPECTED_BASE_MAIN,
    EXPECTED_BASE_TREE,
    LiveInventory,
)

EXIT_OK = 0
EXIT_ERROR = 1


def _load_inventory(path: Path | None, repo: Path) -> LiveInventory:
    if path is None:
        return collect_live_inventory(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("inventory must be a JSON object")
    return LiveInventory.model_validate(payload)


def run_governor_status(*, root: Path) -> tuple[dict[str, object], int]:
    inventory = collect_live_inventory(root)
    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
    )
    snapshot = governor.snapshot()
    plan = governor.plan()
    report: dict[str, object] = {
        "schema_version": 1,
        "package_id": AUTONOMY_PACKAGE_ID,
        "current_main": inventory.current_main,
        "current_tree": inventory.current_tree,
        "target_moved": snapshot.target_moved,
        "expected_main": EXPECTED_BASE_MAIN,
        "expected_tree": EXPECTED_BASE_TREE,
        "worktree_status": inventory.worktree_status,
        "open_relevant_prs": list(inventory.open_relevant_prs),
        "active_successor_packages": list(inventory.active_successor_packages),
        "r2_created": inventory.r2_created,
        "r7_created": inventory.r7_created,
        "authentic_r6_resumed": inventory.authentic_r6_resumed,
        "as_orch_001e_started": inventory.as_orch_001e_started,
        "plan": plan.model_dump(mode="json"),
        "merge_authorized": False,
        "execution_authorized": False,
    }
    return report, EXIT_ERROR if snapshot.target_moved else EXIT_OK


def run_governor_discover(
    *,
    root: Path,
    inventory_path: Path | None = None,
) -> tuple[dict[str, object], int]:
    inventory = _load_inventory(inventory_path, root)
    report = discover(inventory)
    return report.model_dump(mode="json"), EXIT_ERROR if report.case == "A-B" else EXIT_OK


def run_governor_pilot(
    *,
    root: Path,
    evidence_dir: Path | None = None,
    inventory_path: Path | None = None,
    stdin: TextIO | None = None,
) -> tuple[dict[str, object], int]:
    del stdin
    if inventory_path is not None:
        inventory = _load_inventory(inventory_path, root)
        governor = AutonomousGovernor(
            current_main=inventory.current_main,
            current_tree=inventory.current_tree,
        )
        result = governor.run_controlled_pilot(
            inventory,
            branch="feat/as-orch-autonomy-001",
            worktree=str(root),
            evidence_dir=evidence_dir,
        )
        return result, EXIT_OK
    result = run_live_pilot(root, evidence_dir=evidence_dir)
    return result, EXIT_OK
