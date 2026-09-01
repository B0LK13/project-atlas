"""Live discovery of the next safe ready node.

R2/R7/R6 are closed (superseded/obsolete). 001D is merged on trusted
main. 001E is implemented on this tree and waits at the owner merge
gate. Git observation is fail-closed: missing
repo, non-toplevel --root, or unreadable pins do not fall back to SHAs.
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


def _for_each_ref(repo: Path, *patterns: str) -> list[tuple[str, str]]:
    """``(refname, tip_commit_sha)`` pairs via robust plumbing -- never
    fragile ``git branch -a`` display-line parsing. Excludes symbolic
    remote HEAD refs (``refs/remotes/<remote>/HEAD``); every remaining
    entry is a concrete branch pinned to an exact commit."""
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)\t%(objectname)", *patterns],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DiscoveryError("git for-each-ref failed")
    refs: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        refname, _, tip = line.partition("\t")
        if not refname or not tip or refname.endswith("/HEAD"):
            continue
        refs.append((refname, tip))
    return refs


def _is_merged_into(repo: Path, tip: str, current_main: str) -> bool:
    """True only if ``tip`` is a genuine ancestor of ``current_main`` --
    never inferred from a branch name existing. Fails closed (raises
    ``DiscoveryError``) on any git failure other than the two ancestry
    outcomes (`0` = is an ancestor, `1` = is not) -- an unobservable
    topology query is never silently treated as "not merged" (which
    would fail open, understating activity) nor as "merged" (which
    would fail open the other way, hiding a genuinely active successor)."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", tip, current_main],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise DiscoveryError(f"git merge-base --is-ancestor could not observe ancestry for {tip!r}")


def collect_live_inventory(repo: Path) -> LiveInventory:
    """Observe git facts at an exact toplevel. Does not invent pins or PR lists.

    Successor-package activity (``active_successor_packages``,
    ``r2_created``, ``r7_created``, ``as_orch_001e_started``) is
    TOPOLOGY-based, not name-presence-based: a ref whose name matches
    ``_SUCCESSOR_PATTERNS`` only counts as active if its exact tip
    commit is NOT already an ancestor of ``origin/main`` (real IV
    finding: a historical branch merged long ago and simply never
    deleted from the remote -- ``BRANCH_REF_EXISTS != ACTIVE_SUCCESSOR``
    -- was being treated as an in-flight successor forever, permanently
    hard-blocking discovery via a false positive). Every one of these
    fields is derived from the SAME filtered set of genuinely-unmerged
    matching refs, so fixing only one field could not leave another
    reintroducing the same stale false positive through a different
    name. Deliberately conservative: only an EXACT first-parent-
    independent ancestry match (any path, via ``merge-base
    --is-ancestor`` -- unlike the checkpoint-recovery mechanism, this
    is about "was this content ever integrated at all", not "is it on
    the trunk", so any-path ancestry is the right check here) counts as
    integrated; a squash/rebase-equivalent branch whose exact tip was
    never itself committed to main stays conservatively active.
    """
    resolved = _require_toplevel(repo)
    current_main = _require_pin(_run_git(resolved, "rev-parse", "origin/main"), "origin/main")
    current_tree = _require_pin(
        _run_git(resolved, "rev-parse", "origin/main^{tree}"),
        "origin/main tree",
    )
    current_branch = _run_git(resolved, "branch", "--show-current")

    matching_refs = _for_each_ref(resolved, "refs/heads", "refs/remotes")
    unmerged_successors: list[str] = []
    for refname, tip in matching_refs:
        if not any(pattern.search(refname) for pattern in _SUCCESSOR_PATTERNS):
            continue
        if not _is_merged_into(resolved, tip, current_main):
            unmerged_successors.append(refname)

    r2_created: Literal["YES", "NO"] = (
        "YES" if any(re.search(r"001d-r2", r, re.IGNORECASE) for r in unmerged_successors) else "NO"
    )
    r7_created: Literal["YES", "NO"] = (
        "YES" if any(re.search(r"001d-r7", r, re.IGNORECASE) for r in unmerged_successors) else "NO"
    )
    started_e: Literal["YES", "NO"] = (
        "YES"
        if any(re.search(r"as-orch-001e", r, re.IGNORECASE) for r in unmerged_successors)
        else "NO"
    )
    status = _run_git(resolved, "status", "-sb").splitlines()
    worktree = "CLEAN" if len(status) <= 1 else "DIRTY_UNTRACKED_OR_MODIFIED"
    pr396: Literal["YES", "NO"] = "YES" if current_branch == _PR396_BRANCH else "NO"
    return LiveInventory(
        current_main=current_main,
        current_tree=current_tree,
        worktree_status=worktree,
        open_relevant_prs=(),
        active_successor_packages=tuple(unmerged_successors),
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
            owner_gate=None,
            reason="SUPERSEDED_CLOSED_SEMANTIC_DELTA_ZERO",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001D-R7",
            eligible=False,
            destructive=False,
            owner_gate=None,
            reason="OBSOLETE_NO_DEFINED_SEMANTIC",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001D-R6",
            eligible=False,
            destructive=False,
            owner_gate=OwnerGateKind.C_CERTIFIED_OBJECT_MUTATION,
            reason="SUPERSEDED_CLOSED_DO_NOT_MUTATE_PR_396",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001E",
            eligible=False,
            destructive=True,
            owner_gate=OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
            reason="IMPLEMENTED_PENDING_OWNER_MERGE",
        ),
        DiscoveryCandidate(
            package_id=PILOT_PACKAGE_ID,
            eligible=False,
            destructive=False,
            owner_gate=None,
            reason="COMPLETED_CERTIFICATION_PILOT_CLOSED",
        ),
        DiscoveryCandidate(
            package_id="AS-ORCH-001D",
            eligible=False,
            destructive=False,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
            reason="MERGED_AND_SEALED_ON_TRUSTED_MAIN",
        ),
    )
    selected = next((item.package_id for item in candidates if item.eligible), None)
    return DiscoveryReport(
        inventory=inventory,
        trusted_runtime_main=trusted.trusted_main,
        trusted_runtime_tree=trusted.trusted_tree,
        target_moved=False,
        successor_already_started=False,
        candidates=candidates,
        selected_package_id=selected,
        case="A-A-PREFLIGHT",
        blocker="OWNER_GATE" if selected is None else None,
    )
