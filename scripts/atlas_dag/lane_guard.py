"""Fail-closed lane guard: may THIS agent write to THIS lane right now?

LANE_OWNERSHIP = MUTEX (atlas_dag.model.ownership)
UNOWNED != PERMITTED   (claim first through the control plane)
AMBIGUOUS != OWNED     (never last-writer-wins)
UNKNOWN != OWNED       (bus unavailable / branch has no PR => refuse)
GUARD != AUTHORIZATION (a guard verdict grants nothing; it only refuses)

Motivation (2026-09-09): two agents edited the same PR-branch worktree at
once because nothing checked the ownership mutex before writing. The bus
already knows who owns a lane; this module asks it, read-only, and gives
agents a pre-commit hook that refuses to commit into a lane they do not own.
"""
from __future__ import annotations

import stat
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import events as events_mod
from .model import ownership

SCHEMA_CONST = "ATLAS_LANE_GUARD_V1"
ALLOWED = "ALLOWED"
REFUSED = "REFUSED"
HOOK_MARKER = "# ATLAS_LANE_GUARD_V1"

GUARD_NE_AUTHORIZATION = True
UNOWNED_NE_PERMITTED = True
AMBIGUOUS_NE_OWNED = True
UNKNOWN_NE_OWNED = True


class LaneGuardError(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def honesty() -> dict[str, bool]:
    return {
        "guard_ne_authorization": GUARD_NE_AUTHORIZATION,
        "unowned_ne_permitted": UNOWNED_NE_PERMITTED,
        "ambiguous_ne_owned": AMBIGUOUS_NE_OWNED,
        "unknown_ne_owned": UNKNOWN_NE_OWNED,
    }


def _packet(decision: str, *, agent_id: str | None, pr: int | None, branch: str | None,
            ownership_state: str, claimants: list[str], reasons: list[str],
            clock: Callable[[], str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA_CONST,
        "decision": decision,
        "agent": agent_id or None,
        "lane": f"pr/{pr}" if pr is not None else None,
        "pr": pr,
        "branch": branch,
        "ownership": ownership_state,
        "claimants": list(claimants),
        "reasons": list(reasons),
        "honesty": honesty(),
        "evaluated_at_utc": clock(),
    }


def evaluate_lane_guard(*, agent_id: str | None, pr: int | None, events: list[dict],
                        live_head: str | None = None, branch: str | None = None,
                        clock: Callable[[], str] = utcnow) -> dict[str, Any]:
    """Pure verdict from an event stream. Never mutates; never claims."""
    agent = (agent_id or "").strip()
    if not agent:
        return _packet(REFUSED, agent_id=None, pr=pr, branch=branch,
                       ownership_state="UNKNOWN", claimants=[],
                       reasons=["AGENT_IDENTITY_UNSET"], clock=clock)
    if pr is None:
        return _packet(REFUSED, agent_id=agent, pr=None, branch=branch,
                       ownership_state="UNKNOWN", claimants=[],
                       reasons=["LANE_UNRESOLVED"], clock=clock)
    state, claimants = ownership(events, pr, live_head)
    if state == "OWNED" and claimants == [agent]:
        return _packet(ALLOWED, agent_id=agent, pr=pr, branch=branch,
                       ownership_state=state, claimants=claimants,
                       reasons=["LANE_OWNED_BY_AGENT"], clock=clock)
    if state == "OWNED":
        return _packet(REFUSED, agent_id=agent, pr=pr, branch=branch,
                       ownership_state=state, claimants=claimants,
                       reasons=[f"LANE_OWNED_BY_OTHER:{claimants[0]}"], clock=clock)
    if state == "AMBIGUOUS":
        return _packet(REFUSED, agent_id=agent, pr=pr, branch=branch,
                       ownership_state=state, claimants=claimants,
                       reasons=["OWNERSHIP_AMBIGUOUS"], clock=clock)
    return _packet(REFUSED, agent_id=agent, pr=pr, branch=branch,
                   ownership_state=state, claimants=claimants,
                   reasons=["LANE_UNOWNED_CLAIM_FIRST"], clock=clock)


def resolve_pr_for_branch(client: Any, branch: str) -> int | None:
    """Open PR whose head branch is ``branch`` (exact match), else None."""
    for pr in client.open_prs() or []:
        if pr.get("headRefName") == branch and pr.get("number") is not None:
            return int(pr["number"])
    return None


def guard_live(client: Any, *, agent_id: str | None, pr: int | None = None,
               branch: str | None = None,
               clock: Callable[[], str] = utcnow) -> dict[str, Any]:
    """Resolve lane + bus ownership from live truth, then evaluate. Read-only."""
    if pr is None and branch:
        pr = resolve_pr_for_branch(client, branch)
        if pr is None:
            return _packet(REFUSED, agent_id=agent_id, pr=None, branch=branch,
                           ownership_state="UNKNOWN", claimants=[],
                           reasons=[f"NO_OPEN_PR_FOR_BRANCH:{branch}"], clock=clock)
    issue = client.dag_issue()
    if not issue:
        return _packet(REFUSED, agent_id=agent_id, pr=pr, branch=branch,
                       ownership_state="UNKNOWN", claimants=[],
                       reasons=["DAG_CONTROL_ISSUE_NOT_FOUND"], clock=clock)
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    return evaluate_lane_guard(agent_id=agent_id, pr=pr, events=ingested.events,
                               branch=branch, clock=clock)


def hook_script(*, agent_id: str, dag_script: Path, repo: str | None = None) -> str:
    repo_arg = f' --repo "{repo}"' if repo else ""
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER} — installed by `atlas-dag lane-guard --install-hook`.\n"
        "# Refuses to commit into a lane this agent does not own on the DAG bus.\n"
        "# Remove this file to uninstall. There is no bypass switch by design.\n"
        # symbolic-ref works on an unborn branch; rev-parse --abbrev-ref does not.
        'branch=$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "")\n'
        f'exec python3 "{dag_script}" lane-guard --agent "{agent_id}" '
        f'--branch "$branch"{repo_arg}\n'
    )


def _hooks_dir(worktree: Path) -> Path:
    if not worktree.is_dir():
        raise LaneGuardError(f"NOT_A_GIT_WORKTREE:{worktree}")
    out = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=str(worktree),
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise LaneGuardError(f"NOT_A_GIT_WORKTREE:{worktree}")
    path = Path(out.stdout.strip())
    return path if path.is_absolute() else (worktree / path)


def install_hook(worktree: Path, *, agent_id: str, dag_script: Path,
                 repo: str | None = None) -> Path:
    """Write the pre-commit hook. Fail closed on a foreign existing hook."""
    agent = (agent_id or "").strip()
    if not agent:
        raise LaneGuardError("AGENT_IDENTITY_UNSET")
    hooks = _hooks_dir(worktree)
    hooks.mkdir(parents=True, exist_ok=True)
    target = hooks / "pre-commit"
    if target.exists() and HOOK_MARKER not in target.read_text(encoding="utf-8"):
        raise LaneGuardError(f"FOREIGN_PRE_COMMIT_HOOK_PRESENT:{target}")
    target.write_text(hook_script(agent_id=agent, dag_script=dag_script.resolve(), repo=repo),
                      encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def exit_code(packet: dict[str, Any]) -> int:
    return 0 if packet.get("decision") == ALLOWED else 1


__all__ = [
    "ALLOWED",
    "REFUSED",
    "SCHEMA_CONST",
    "LaneGuardError",
    "evaluate_lane_guard",
    "exit_code",
    "guard_live",
    "hook_script",
    "install_hook",
    "resolve_pr_for_branch",
]
