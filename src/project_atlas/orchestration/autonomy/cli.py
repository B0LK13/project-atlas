"""CLI runners for the autonomous governor. Not dispatch and not merge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from project_atlas.orchestration.autonomy.discovery import (
    DiscoveryError,
    collect_live_inventory,
    discover,
)
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor, run_live_pilot
from project_atlas.orchestration.autonomy.lease_projection import (
    RELATIVE_DEFAULT as LEASE_PROJECTION_RELATIVE_DEFAULT,
)
from project_atlas.orchestration.autonomy.loop import (
    STATE_DIR_RELATIVE,
    AutonomousLoop,
    LoopError,
)
from project_atlas.orchestration.autonomy.models import (
    AUTONOMY_PACKAGE_ID,
    BOOTSTRAP_MAIN,
    BOOTSTRAP_TREE,
    LiveInventory,
    NodeState,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.rehydration import RehydrationError, rehydrate_governor
from project_atlas.orchestration.autonomy.trust import (
    TrustError,
    load_runtime_anchor,
    normalize_repository_identity,
)

EXIT_OK = 0
EXIT_ERROR = 1


def _fail_closed(detail: str, *, blocker: str = "TRUST_UNVERIFIABLE") -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": AUTONOMY_PACKAGE_ID,
        "case": "A-B",
        "blocker": blocker,
        "detail": detail,
        "target_moved": blocker == "TARGET_MOVED",
        "trust_state": "UNVERIFIABLE" if blocker != "TARGET_MOVED" else "TARGET_MOVED",
        "static_bootstrap_pin_as_runtime_authority": False,
        "merge_authorized": False,
        "execution_authorized": False,
    }


def _load_trusted(
    *,
    trust_store: Path | None,
    allow_shipped: bool,
    explicit: TrustedAnchorRecord | None = None,
) -> TrustedAnchorRecord:
    return load_runtime_anchor(
        store=trust_store,
        explicit=explicit,
        allow_shipped=allow_shipped and trust_store is None and explicit is None,
    )


def _load_inventory(path: Path | None, repo: Path) -> LiveInventory:
    if path is None:
        return collect_live_inventory(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("inventory must be a JSON object")
    return LiveInventory.model_validate(payload)


def _node_counts(nodes: tuple[object, ...]) -> dict[str, int]:
    ready = 0
    owner_held = 0
    blocked = 0
    for node in nodes:
        state = getattr(node, "state", None)
        if state is NodeState.READY:
            ready += 1
        elif state is NodeState.OWNER_HELD:
            owner_held += 1
        elif state is NodeState.BLOCKED:
            blocked += 1
    return {
        "ready_node_count": ready,
        "owner_held_node_count": owner_held,
        "blocked_node_count": blocked,
    }


def run_governor_status(
    *,
    root: Path,
    trust_store: Path | None = None,
) -> tuple[dict[str, object], int]:
    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=True)
        inventory = collect_live_inventory(root)
    except TrustError as exc:
        return _fail_closed(str(exc), blocker=exc.code), EXIT_ERROR
    except DiscoveryError as exc:
        return _fail_closed(str(exc), blocker="DISCOVERY_UNOBSERVABLE"), EXIT_ERROR
    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
    )
    snapshot = governor.snapshot()
    plan = governor.plan()
    counts = _node_counts(snapshot.nodes)
    next_eligible = plan.what_can_run_now[0] if plan.what_can_run_now else None
    next_state = None
    next_gate = None
    if next_eligible is not None:
        node = next(item for item in snapshot.nodes if item.package_id == next_eligible)
        next_state = node.state.value
        next_gate = node.owner_gate.value if node.owner_gate is not None else None
    report: dict[str, object] = {
        "schema_version": 1,
        "package_id": AUTONOMY_PACKAGE_ID,
        "observed_main": inventory.current_main,
        "observed_tree": inventory.current_tree,
        "current_main": inventory.current_main,
        "current_tree": inventory.current_tree,
        "bootstrap_main": BOOTSTRAP_MAIN,
        "bootstrap_tree": BOOTSTRAP_TREE,
        "trusted_runtime_main": trusted.trusted_main,
        "trusted_runtime_tree": trusted.trusted_tree,
        "target_moved": snapshot.target_moved,
        "trust_state": snapshot.trust_state.value,
        "static_bootstrap_pin_as_runtime_authority": False,
        "worktree_status": inventory.worktree_status,
        "open_relevant_prs": list(inventory.open_relevant_prs),
        "active_successor_packages": list(inventory.active_successor_packages),
        "r2_created": inventory.r2_created,
        "r7_created": inventory.r7_created,
        "authentic_r6_resumed": inventory.authentic_r6_resumed,
        "as_orch_001e_started": inventory.as_orch_001e_started,
        "next_eligible_node": next_eligible,
        "next_eligible_node_state": next_state,
        "next_eligible_node_owner_gate": next_gate,
        **counts,
        "plan": plan.model_dump(mode="json"),
        "merge_authorized": False,
        "execution_authorized": False,
    }
    return report, EXIT_ERROR if snapshot.target_moved else EXIT_OK


def run_governor_discover(
    *,
    root: Path,
    inventory_path: Path | None = None,
    trust_store: Path | None = None,
) -> tuple[dict[str, object], int]:
    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=True)
        inventory = _load_inventory(inventory_path, root)
    except TrustError as exc:
        return _fail_closed(str(exc), blocker=exc.code), EXIT_ERROR
    except DiscoveryError as exc:
        return {
            "schema_version": 1,
            "package_id": AUTONOMY_PACKAGE_ID,
            "case": "A-B",
            "blocker": "DISCOVERY_UNOBSERVABLE",
            "detail": str(exc),
            "static_bootstrap_pin_as_runtime_authority": False,
        }, EXIT_ERROR
    report = discover(inventory, trusted=trusted)
    payload = report.model_dump(mode="json")
    payload["static_bootstrap_pin_as_runtime_authority"] = False
    payload["trusted_runtime_main"] = trusted.trusted_main
    payload["trusted_runtime_tree"] = trusted.trusted_tree
    payload["next_eligible_node"] = report.selected_package_id
    return payload, EXIT_ERROR if report.case == "A-B" else EXIT_OK


def run_governor_pilot(
    *,
    root: Path,
    evidence_dir: Path | None = None,
    inventory_path: Path | None = None,
    trust_store: Path | None = None,
    stdin: TextIO | None = None,
) -> tuple[dict[str, object], int]:
    del stdin
    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=True)
        if inventory_path is not None:
            inventory = _load_inventory(inventory_path, root)
            governor = AutonomousGovernor(
                current_main=inventory.current_main,
                current_tree=inventory.current_tree,
                trusted_anchor=trusted,
            )
            result = governor.run_controlled_pilot(
                inventory,
                branch="feat/as-orch-autonomy-001",
                worktree=str(root),
                evidence_dir=evidence_dir,
            )
            return result, EXIT_OK
        result = run_live_pilot(root, evidence_dir=evidence_dir, trusted_anchor=trusted)
        return result, EXIT_OK
    except TrustError as exc:
        return _fail_closed(str(exc), blocker=exc.code), EXIT_ERROR
    except DiscoveryError as exc:
        return {
            "schema_version": 1,
            "package_id": AUTONOMY_PACKAGE_ID,
            "case": "A-B",
            "blocker": "DISCOVERY_UNOBSERVABLE",
            "detail": str(exc),
            "merge_authorized": False,
            "static_bootstrap_pin_as_runtime_authority": False,
        }, EXIT_ERROR


def run_governor_loop_tick(
    *,
    root: Path,
    trust_store: Path | None = None,
    loop_store: Path | None = None,
) -> tuple[dict[str, object], int]:
    """One 001E tick. Never merges or grants owner authority."""
    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=trust_store is None)
        inventory = collect_live_inventory(root)
        lease_store = root / LEASE_PROJECTION_RELATIVE_DEFAULT
        governor = AutonomousGovernor(
            current_main=inventory.current_main,
            current_tree=inventory.current_tree,
            trusted_anchor=trusted,
            lease_projection_store=lease_store,
        )
        store = loop_store or (root / STATE_DIR_RELATIVE)
        # ORCH001E-011: a fresh AutonomousGovernor starts with an empty node
        # list on every CLI invocation, while `store` may already hold
        # LoopState from a prior process (LEASED, mid-execution, ...). This
        # rehydration pass must run before constructing AutonomousLoop, so
        # the node lookups tick()/recover() perform find what a prior
        # process would have found -- or this call raises RehydrationError
        # first and neither loop nor governor is ever handed inconsistent
        # state.
        rehydrate_governor(
            governor,
            inventory=inventory,
            trusted=trusted,
            loop_store=store,
            lease_projection_store=lease_store,
        )
        loop = AutonomousLoop(
            governor=governor,
            trusted=trusted,
            store=store,
            root=root,
        )
        result = loop.tick()
        if result.phase.value == "IDLE":
            # ORCH001E-011 finding #2 (independent-IV): now that this CLI
            # entrypoint enables the durable lease projection
            # (`lease_projection_store=lease_store` above),
            # `AutonomousLoop.apply_observed_result()` returning the loop to
            # IDLE after a terminal completion does NOT itself release the
            # lease it just finished -- unlike `run_controlled_pilot()`.
            # The only way the loop phase is IDLE with a still-`active`
            # governor lease is exactly that just-completed case (IDLE is
            # otherwise the loop's untouched starting phase, when there is
            # no lease at all yet); release every such lease, both the
            # in-memory bookkeeping and the durable projection, so a later
            # lease for the same package/worker is not rejected as
            # DUPLICATE_ACTIVE_LEASE/FOREIGN_WORKER or mistaken for a
            # replay.
            for existing_lease in governor.snapshot().leases:
                if existing_lease.active:
                    governor.release_lease(existing_lease.lease_id)
        payload = result.model_dump(mode="json")
        payload["package_id"] = "AS-ORCH-001E"
        payload["merge_authorized"] = False
        payload["execution_authorized"] = False
        return payload, EXIT_OK if result.phase.value != "FAILED_CLOSED" else EXIT_ERROR
    except (TrustError, DiscoveryError, LoopError, RehydrationError) as exc:
        code = getattr(exc, "code", "LOOP_FAILED_CLOSED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR


def observed_repository_identity(remote_url: str) -> str:
    """CLI helper for evidence capture. Not an authority grant."""
    return normalize_repository_identity(remote_url)
