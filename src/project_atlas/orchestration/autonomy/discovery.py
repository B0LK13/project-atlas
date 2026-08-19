"""Live discovery of the next safe non-destructive ready node.

Does not preselect R2/R6/R7/001E. Those remain owner-gated or blocked.
Git observation is fail-closed: missing repo, non-toplevel --root, or
unreadable pins do not fall back to expected SHAs.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Literal

from project_atlas.orchestration.autonomy.models import (
    PILOT_PACKAGE_ID,
    DiscoveryCandidate,
    DiscoveryReport,
    LiveInventory,
    OwnerGateKind,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import evaluate_target_moved

_SUCCESSOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"as-orch-001d-r2", re.IGNORECASE),
    re.compile(r"as-orch-001d-r7", re.IGNORECASE),
    re.compile(r"as-orch-001e", re.IGNORECASE),
    re.compile(r"feat/as-orch-001e", re.IGNORECASE),
)
_PIN_RE = re.compile(r"^[0-9a-f]{40}$")
_PR396_BRANCH = "cursor/as-orch-001d-agent-dispatcher-d054"


class DiscoveryError(ValueError):
    """Live observation failed closed. Not an eligibility grant."""

    code = "DISCOVERY_UNOBSERVABLE"


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DiscoveryError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _require_toplevel(repo: Path) -> Path:
    resolved = repo.resolve()
    if not (resolved / ".git").exists():
        raise DiscoveryError("root is not a git repository")
    toplevel = Path(_run_git(resolved, "rev-parse", "--show-toplevel"))
    if not _same_path(resolved, toplevel):
        raise DiscoveryError("root is not the git toplevel")
    return resolved


def _require_pin(value: str, label: str) -> str:
    if not _PIN_RE.fullmatch(value):
        raise DiscoveryError(f"{label} is not an observable git pin")
    return value


def collect_live_inventory(repo: Path) -> LiveInventory:
    """Observe git facts at an exact toplevel. Does not invent pins or PR lists."""
    resolved = _require_toplevel(repo)
    current_main = _require_pin(_run_git(resolved, "rev-parse", "origin/main"), "origin/main")
    current_tree = _require_pin(
        _run_git(resolved, "rev-parse", "origin/main^{tree}"),
        "origin/main tree",
    )
    branches = _run_git(resolved, "branch", "-a")
    current_branch = _run_git(resolved, "branch", "--show-current")
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
    status = _run_git(resolved, "status", "-sb").splitlines()
    worktree = "CLEAN" if len(status) <= 1 else "DIRTY_UNTRACKED_OR_MODIFIED"
    pr396: Literal["YES", "NO"] = "YES" if current_branch == _PR396_BRANCH else "NO"
    return LiveInventory(
        current_main=current_main,
        current_tree=current_tree,
        worktree_status=worktree,
        open_relevant_prs=(),
        active_successor_packages=tuple(successors),
        r2_created=r2_created,
        r7_created=r7_created,
        authentic_r6_resumed="NO",
        as_orch_001e_started=started_e,
        pr396_mutated=pr396,
    )


def discover(inventory: LiveInventory, *, trusted: TrustedAnchorRecord) -> DiscoveryReport:
    """Classify live candidates against the trusted runtime anchor.

    Compile-time bootstrap pins are not runtime authority. Descendant
    relationship is not consulted and cannot grant eligibility.
    """
    target_moved = evaluate_target_moved(
        inventory.current_main,
        inventory.current_tree,
        trusted,
    )
    successor_started = bool(inventory.active_successor_packages) or inventory.r2_created == "YES"
    successor_started = successor_started or inventory.r7_created == "YES"
    successor_started = successor_started or inventory.as_orch_001e_started == "YES"
    if target_moved:
        return DiscoveryReport(
            inventory=inventory,
            trusted_runtime_main=trusted.trusted_main,
            trusted_runtime_tree=trusted.trusted_tree,
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
            trusted_runtime_main=trusted.trusted_main,
            trusted_runtime_tree=trusted.trusted_tree,
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
        trusted_runtime_main=trusted.trusted_main,
        trusted_runtime_tree=trusted.trusted_tree,
        target_moved=False,
        successor_already_started=False,
        candidates=candidates,
        selected_package_id=selected,
        case="A-A-PREFLIGHT",
        blocker=None,
    )
