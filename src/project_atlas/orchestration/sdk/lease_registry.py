"""Durable governor lease registry — scheduler reloads before backend invocation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from project_atlas.orchestration.sdk.models import (
    MUTATING_ROLES,
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRole,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.package_registry import require_mutating_route
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    CANONICAL_PR,
    SUPERSEDED_PR,
    GovernorLease,
    require_valid_lease,
    suppress_stale_directive,
)

LEASES_NAME = "governor-leases.json"
TRUSTED_MAIN = "7e797468a2eca37c959920912b1fa264df4be638"


class LeaseBoundItem(Protocol):
    role: AgentRole
    lease_id: str | None
    dag_generation: int
    package_id: str
    branch: str | None
    candidate_head: str | None


def leases_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / LEASES_NAME


def load_durable_leases(root: Path) -> dict[str, GovernorLease]:
    path = leases_path(root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, GovernorLease] = {}
    for key, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        try:
            out[str(key)] = GovernorLease.model_validate(raw)
        except ValueError:
            continue
    return out


def persist_durable_leases(root: Path, leases: dict[str, GovernorLease]) -> Path:
    path = leases_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    dumped = {k: v.model_dump(mode="json") for k, v in leases.items()}
    path.write_text(json.dumps(dumped, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def persist_durable_lease(root: Path, lease: GovernorLease) -> Path:
    current = load_durable_leases(root)
    current[lease.lease_id] = lease
    return persist_durable_leases(root, current)


def expire_stale_leases(
    root: Path,
    *,
    live_generation: int,
    live_head: str,
) -> dict[str, GovernorLease]:
    current = load_durable_leases(root)
    updated: dict[str, GovernorLease] = {}
    for key, lease in current.items():
        stale = lease.dag_generation != live_generation
        if lease.candidate_head and lease.candidate_head != live_head:
            stale = True
        if stale and (lease.active or not lease.expired):
            updated[key] = lease.model_copy(update={"active": False, "expired": True})
        else:
            updated[key] = lease
    persist_durable_leases(root, updated)
    return updated


def mint_governor_writer_lease(
    root: Path,
    *,
    lease_id: str,
    role: AgentRole,
    dag_generation: int,
    candidate_head: str,
    candidate_tree: str,
    worktree: str,
    base_main: str = TRUSTED_MAIN,
) -> GovernorLease:
    """Mint a mutating writer lease after the pre-mint package-route check."""
    if role not in MUTATING_ROLES:
        raise SdkRuntimeError("writer lease requires mutating role", code="LEASE_MISMATCH")
    require_mutating_route(
        root,
        target_pr=CANONICAL_PR,
        branch=CANONICAL_BRANCH,
        head=candidate_head,
        dag_generation=dag_generation,
    )
    lease = GovernorLease(
        lease_id=lease_id,
        package_id=PACKAGE_ID,
        canonical_pr=CANONICAL_PR,
        branch=CANONICAL_BRANCH,
        role=role,
        dag_generation=dag_generation,
        allowed_paths=(
            "src/project_atlas/orchestration/sdk",
            "tests/unit",
            "scripts",
        ),
        worktree=worktree,
        candidate_head=candidate_head,
        candidate_tree=candidate_tree,
        base_main=base_main,
        active=True,
        expired=False,
        mutation_authorized=True,
    )
    persist_durable_lease(root, lease)
    return lease


def resolve_durable_lease(root: Path, lease_id: str | None) -> GovernorLease | None:
    if not lease_id:
        return None
    return load_durable_leases(root).get(lease_id)


def require_scheduler_lease(
    root: Path | None,
    item: LeaseBoundItem,
    *,
    invocation: bool = False,
) -> GovernorLease | None:
    """Fail closed for mutating work. Read-only items may omit a lease.

    ``invocation=True`` is the second check immediately before backend call.
    """
    role = item.role
    if not isinstance(role, AgentRole):
        raise SdkRuntimeError("invalid role on ready item", code="LEASE_REQUIRED")
    mutating = role in MUTATING_ROLES
    if not mutating:
        return None
    lease_id = item.lease_id
    if not lease_id:
        raise SdkRuntimeError(
            "mutating ReadyWorkItem missing lease_id",
            code="LEASE_REQUIRED",
        )
    if root is None:
        raise SdkRuntimeError(
            "durable lease registry required for mutating dispatch",
            code="LEASE_REQUIRED",
        )
    dag_generation = int(item.dag_generation)
    package_id = str(item.package_id)
    branch = item.branch
    candidate_head = item.candidate_head
    lease = resolve_durable_lease(root, str(lease_id))
    require_valid_lease(
        lease,
        role=role,
        dag_generation=dag_generation,
        package_id=package_id,
        mutating=True,
    )
    assert lease is not None
    if package_id != PACKAGE_ID:
        raise SdkRuntimeError("foreign package mutation rejected", code="STALE_LINEAGE")
    if lease.canonical_pr == SUPERSEDED_PR or branch == "feat/as-orch-428":
        raise SdkRuntimeError("PR428 mutation rejected", code="STALE_LINEAGE")
    require_mutating_route(
        root,
        target_pr=lease.canonical_pr,
        branch=branch or lease.branch or CANONICAL_BRANCH,
        head=candidate_head or lease.candidate_head,
        dag_generation=dag_generation,
    )
    stale = suppress_stale_directive(
        directive_pr=lease.canonical_pr,
        directive_head=lease.candidate_head,
        live_pr=CANONICAL_PR,
        live_head=candidate_head or lease.candidate_head or "",
    )
    if stale:
        raise SdkRuntimeError(f"stale directive at invocation: {stale}", code="STALE_DIRECTIVE")
    if (
        invocation
        and lease.candidate_head
        and candidate_head
        and lease.candidate_head != candidate_head
    ):
        raise SdkRuntimeError("lease head moved before invocation", code="STALE_LINEAGE")
    return lease
