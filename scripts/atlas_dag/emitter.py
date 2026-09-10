"""Automatic Git object resolution for coordination events (FEATURE_04).

Agents describe the transition; repository/GitHub truth supplies the object
identity. HEAD, TREE, base, main, and stacked-parent identity are RESOLVED
from live refs and Git ancestry — never transcribed by hand, and never
taken from an agent-supplied value: `--expect-head` is an assertion only,
compared against resolved truth and FAILED on mismatch.

`build_event` is read-only. `emit_event` additionally enforces registry
event permissions, lane ownership (from the #719 stream), duplicate
transition idempotence, and posts only to the canonical DAG Control issue.
`--dry-run` performs zero GitHub mutation.

The deterministic event id binds a transition identity to the resolved
head: the same logical transition at the same resolved head yields the
same event_id (duplicate emit is a no-op), and any head move yields a new
id with prior candidate-wide evidence demoted per D-005/D-009.

A prospective merge SHA is never accepted as HEAD or as a merge receipt:
identity comes exclusively from live refs + the Feature-3 stack topology.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import agents as agents_mod
from . import events as events_mod
from . import stack as stack_mod

SCHEMA_CONST = "ATLAS_EVENT_V1"


class EmitError(RuntimeError):
    """Fail-closed: resolution, permission, or validation failure."""


@dataclass
class ResolvedContext:
    """Object identity resolved from live repository/GitHub truth."""

    repo: str | None
    pr: int
    lane: str
    head: str
    tree: str | None
    base_branch: str | None
    base_head: str | None
    main_branch: str | None
    main_head: str | None
    parent_pr: int | None
    parent_head: str | None
    actor: str
    role: str
    session_id: str


@dataclass
class EmitChecks:
    """Why an emit was denied (empty = permitted)."""

    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_context(client, pr_number: int, profile: dict,
                    expected_repo: str | None = None) -> ResolvedContext:
    """Resolve every object-identity field from live truth. Fail closed."""
    repo = client.repo
    if expected_repo is not None and repo != expected_repo:
        raise EmitError(f"WRONG_REPOSITORY_IDENTITY:{repo}!={expected_repo}")
    if not repo:
        raise EmitError("REPOSITORY_IDENTITY_UNKNOWN")

    match = next((p for p in client.open_prs() if p.get("number") == pr_number), None)
    if match is None:
        raise EmitError(f"UNKNOWN_PR:{pr_number}")
    head = match.get("headRefOid")
    if not head:
        raise EmitError("PR_HEAD_UNRESOLVED")
    commit = client.commit(head)
    if not commit or not commit.get("tree"):
        raise EmitError("CANDIDATE_TREE_UNKNOWN")
    base_branch = match.get("baseRefName")
    base = client.branch_head(base_branch) if base_branch else None
    main_branch = client.default_branch()
    main = client.branch_head(main_branch) if main_branch else None
    if not main:
        raise EmitError("MAIN_HEAD_UNKNOWN")

    parent_pr = None
    parent_head = None
    if base_branch and base_branch != main_branch:
        # Stacked parent identity comes from Feature-3 topology (live refs
        # + ancestry), never from PR prose.
        sibling = dict(match)
        sibling["lane"] = f"pr/{pr_number}"
        sibling["head_branch"] = match.get("headRefName")
        sibling["base"] = base_branch
        sibling["head"] = head
        sibling["state"] = "RUNNABLE_WRITE"
        all_prs = client.open_prs()
        nodes = []
        for p in all_prs:
            nodes.append({
                "lane": f"pr/{p['number']}", "pr": p["number"],
                "head": p.get("headRefOid"), "head_branch": p.get("headRefName"),
                "base": p.get("baseRefName"),
            })
        stacks = stack_mod.build_stacks(nodes, client, main_branch)
        record = stacks.get(f"pr/{pr_number}")
        if record is not None:
            if record["stack_state"] == stack_mod.AMBIGUOUS:
                raise EmitError("STACK_PARENT_AMBIGUOUS")
            parent_pr = record.get("parent_pr")
            parent_head = record.get("parent_head")

    agent_id = str(profile.get("agent_id"))
    metadata = profile.get("metadata") or {}
    session_id = str(metadata.get("session_id") or agent_id)
    role_text = str(profile.get("role") or "").lower()
    if "verifier" in role_text:
        role = "VERIFIER"
    elif "coordinator" in role_text:
        role = "COORDINATOR"
    else:
        role = "AGENT"
    return ResolvedContext(
        repo=repo, pr=pr_number, lane=f"pr/{pr_number}", head=head,
        tree=commit["tree"], base_branch=base_branch,
        base_head=base["sha"] if base else None,
        main_branch=main_branch, main_head=main["sha"] if main else None,
        parent_pr=parent_pr, parent_head=parent_head,
        actor=agent_id, role=role, session_id=session_id,
    )


def event_id_for(ctx: ResolvedContext, event: str, utc: str) -> str:
    """Deterministic transition identity: same transition at the same
    resolved head => same id (duplicate emit is idempotent)."""
    day = utc[:10].replace("-", "")
    return f"evt-{day}-{ctx.actor}-{event.lower().replace('_', '-')}-{ctx.pr}-{ctx.head[:12]}"


def build_event(ctx: ResolvedContext, event: str, state: str, note: str,
                utc: str | None = None, dependencies: list[str] | None = None,
                evidence: list[str] | None = None,
                invalidates: list[str] | None = None,
                next_actions: list[str] | None = None,
                expect_head: str | None = None) -> dict:
    """Canonical ATLAS_EVENT_V1 payload. Read-only; no mutation."""
    if expect_head is not None and expect_head != ctx.head:
        raise EmitError(f"EXPECT_HEAD_MISMATCH:supplied={expect_head}"
                        f" resolved={ctx.head}")
    timestamp = utc or utcnow()
    payload = {
        "schema": SCHEMA_CONST,
        "event_id": event_id_for(ctx, event, timestamp),
        "timestamp_utc": timestamp,
        "actor": ctx.actor,
        "role": ctx.role,
        "session_id": ctx.session_id,
        "lane": ctx.lane,
        "pr": ctx.pr,
        "head": ctx.head,
        "tree": ctx.tree,
        "base_branch": ctx.base_branch,
        "base_head": ctx.base_head,
        "main_head": ctx.main_head,
        "parent_pr": ctx.parent_pr,
        "parent_head": ctx.parent_head,
        "event": event,
        "state": state,
        "dependencies": sorted(dependencies or []),
        "evidence": sorted(evidence or []),
        "invalidates": sorted(invalidates or []),
        "next_actions": sorted(next_actions or []),
        "note": note,
    }
    validator = events_mod.validator_for(events_mod.EVENT_SCHEMA)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        raise EmitError(f"SCHEMA_INVALID:{errors[0].message}")
    return payload


def fenced(payload: dict) -> str:
    """The canonical fenced form — raw manual construction unnecessary."""
    return "```json\n" + json.dumps(payload, sort_keys=True) + "\n```\n"


def check_emit_permission(registry: agents_mod.RegistryResult, agent_id: str,
                          event: str, lane_owner: str | None,
                          lane_frozen: bool = False) -> EmitChecks:
    """Registry event permission + lane ownership context."""
    checks = EmitChecks()
    resolved = agents_mod.resolve_agent(registry, agent_id)
    if resolved.status != "REGISTERED":
        checks.reasons.append(f"AGENT_NOT_REGISTERED:{resolved.status}")
        return checks
    profile = resolved.profile or {}
    if not profile.get("active", False):
        checks.reasons.append("AGENT_INACTIVE")
        return checks
    allowed = {str(e) for e in profile.get("event_permissions", [])}
    if event not in allowed:
        checks.reasons.append(f"EVENT_NOT_PERMITTED:{event}")
    if lane_frozen:
        checks.reasons.append("LANE_FROZEN_BY_REPOSITORY_TRUTH")
    if event != "OWNER_CLAIMED" and lane_owner is not None \
            and lane_owner != agent_id:
        checks.reasons.append(f"OWNERSHIP_MUTEX_HELD_BY:{lane_owner}")
    if event == "OWNER_CLAIMED" and lane_owner not in (None, agent_id):
        checks.reasons.append(f"OWNERSHIP_MUTEX_HELD_BY:{lane_owner}")
    return checks


def emit_event(client, registry: agents_mod.RegistryResult, payload: dict,
               dry_run: bool = False) -> str:
    """Post to the canonical #719 bus with duplicate idempotence.

    Returns a status string: dry-run / posted / already-present.
    """
    issue = client.dag_issue()
    if not issue:
        raise EmitError("DAG_CONTROL_ISSUE_NOT_FOUND")
    if not dry_run:
        # Re-resolve at post time: a head move between build and emit is a
        # TOCTOU failure, never a stale post.
        live = next((p for p in client.open_prs()
                     if p.get("number") == payload.get("pr")), None)
        if not live or live.get("headRefOid") != payload.get("head"):
            raise EmitError("HEAD_MOVED_DURING_RESOLUTION")
        ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
        if payload["event_id"] in ingested.by_id:
            return "already-present"
    body = fenced(payload)
    if dry_run:
        return "dry-run"
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(body)
        body_path = handle.name
    try:
        client.run_gh(["issue", "comment", str(issue["number"]),
                       "--repo", client.repo or "", "--body-file", body_path])
    finally:
        import os
        os.unlink(body_path)
    return "posted"
