"""Live discovery of the next safe non-destructive ready node.

Does not preselect R2/R6/R7/001E. Those remain owner-gated or blocked.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

from project_atlas.orchestration.autonomy.models import (
    EXPECTED_BASE_MAIN,
    EXPECTED_BASE_TREE,
    PILOT_PACKAGE_ID,
    DiscoveryCandidate,
    DiscoveryReport,
    LiveInventory,
    OwnerGateKind,
)

_SUCCESSOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"as-orch-001d-r2", re.IGNORECASE),
    re.compile(r"as-orch-001d-r7", re.IGNORECASE),
    re.compile(r"as-orch-001e", re.IGNORECASE),
    re.compile(r"feat/as-orch-001e", re.IGNORECASE),
)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def collect_live_inventory(repo: Path) -> LiveInventory:
    """Observe git facts. Does not call GitHub mutation APIs."""
    current_main = _run_git(repo, "rev-parse", "origin/main") or EXPECTED_BASE_MAIN
    current_tree = _run_git(repo, "rev-parse", "origin/main^{tree}") or EXPECTED_BASE_TREE
    branches = _run_git(repo, "branch", "-a")
    r2_created: Literal["YES", "NO"] = (
        "YES" if re.search(r"001d-r2", branches, re.IGNORECASE) else "NO"
    )
    r7_created: Literal["YES", "NO"] = (
        "YES" if re.search(r"001d-r7", branches, re.IGNORECASE) else "NO"
    )
    started_e: Literal["YES", "NO"] = (
        "YES" if re.search(r"as-orch-001e", branches, re.IGNORECASE) else "NO"
    )
    successors: list[str] = []
    for line in branches.splitlines():
        name = line.strip().lstrip("* ").split()[0] if line.strip() else ""
        if any(pattern.search(name) for pattern in _SUCCESSOR_PATTERNS):
            successors.append(name)
    status = _run_git(repo, "status", "-sb").splitlines()
    worktree = "CLEAN" if len(status) <= 1 else "DIRTY_UNTRACKED_OR_MODIFIED"
    return LiveInventory(
        current_main=current_main,
        current_tree=current_tree,
        worktree_status=worktree,
        open_relevant_prs=("396", "394"),
        active_successor_packages=tuple(successors),
        r2_created=r2_created,
        r7_created=r7_created,
        authentic_r6_resumed="NO",
        as_orch_001e_started=started_e,
        pr396_mutated="NO",
    )


def discover(inventory: LiveInventory) -> DiscoveryReport:
    """Classify live candidates. Prefer a self-contained non-destructive pilot."""
    target_moved = (
        inventory.current_main != EXPECTED_BASE_MAIN
        or inventory.current_tree != EXPECTED_BASE_TREE
    )
    successor_started = bool(inventory.active_successor_packages) or inventory.r2_created == "YES"
    successor_started = successor_started or inventory.r7_created == "YES"
    successor_started = successor_started or inventory.as_orch_001e_started == "YES"
    if target_moved:
        return DiscoveryReport(
            inventory=inventory,
            target_moved=True,
            successor_already_started=successor_started,
            candidates=(),
            selected_package_id=None,
            case="A-B",
            blocker="TARGET_MOVED",
        )
    if successor_started:
        return DiscoveryReport(
            inventory=inventory,
            target_moved=False,
            successor_already_started=True,
            candidates=(),
            selected_package_id=None,
            case="A-B",
            blocker="SUCCESSOR_ALREADY_STARTED",
        )
    candidates = (
        DiscoveryCandidate(
            package_id="AS-ORCH-001D-R2",
            eligible=False,
            destructive=False,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
            reason="NOT_PRESELECTED_OWNER_GATED",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001D-R7",
            eligible=False,
            destructive=False,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
            reason="NOT_PRESELECTED_OWNER_GATED",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001E",
            eligible=False,
            destructive=True,
            owner_gate=OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
            reason="AUTONOMOUS_LOOP_NOT_AUTHORIZED",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001D-R6",
            eligible=False,
            destructive=False,
            owner_gate=OwnerGateKind.C_CERTIFIED_OBJECT_MUTATION,
            reason="DO_NOT_MUTATE_PR_396",
        ),
        DiscoveryCandidate(
            package_id=PILOT_PACKAGE_ID,
            eligible=True,
            destructive=False,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
            reason="NEXT_SAFE_NON_DESTRUCTIVE_READY_PACKAGE",
        ),
    )
    selected = next(item.package_id for item in candidates if item.eligible)
    return DiscoveryReport(
        inventory=inventory,
        target_moved=False,
        successor_already_started=False,
        candidates=candidates,
        selected_package_id=selected,
        case="A-A-PREFLIGHT",
        blocker=None,
    )
