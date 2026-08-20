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


def run_governor_broker(
    *,
    root: Path,
    trust_store: Path | None = None,
    loop_store: Path | None = None,
    broker_store: Path | None = None,
    max_cycles: int = 32,
) -> tuple[dict[str, object], int]:
    """Supervise 001E invocations via AS-ORCH-CONTINUATION-BROKER-001.

    Wires the existing 001D DispatchPort. Does not merge or grant owner
    authority. Resource-boundary yields start a fresh invocation.
    """
    from project_atlas.orchestration.autonomy.broker import (
        BROKER_PACKAGE_ID,
        CONTINUATION_BACKEND_SELECTED,
        BrokerError,
        ContinuationBroker,
        wire_001d_dispatch_port,
    )
    from project_atlas.orchestration.autonomy.broker import (
        STATE_DIR_RELATIVE as BROKER_STATE_DIR,
    )

    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=trust_store is None)
        inventory = collect_live_inventory(root)
        governor = AutonomousGovernor(
            current_main=inventory.current_main,
            current_tree=inventory.current_tree,
            trusted_anchor=trusted,
        )
        store = broker_store or (root / BROKER_STATE_DIR)
        broker = ContinuationBroker(
            governor=governor,
            trusted=trusted,
            store=store,
            root=root,
            loop_store=loop_store,
            dispatch=wire_001d_dispatch_port(),
        )
        result = broker.run(max_cycles=max_cycles)
        payload = result.model_dump(mode="json")
        payload["package_id"] = BROKER_PACKAGE_ID
        payload["continuation_backend"] = CONTINUATION_BACKEND_SELECTED
        payload["dispatchport_wired"] = True
        payload["merge_authorized"] = False
        payload["execution_authorized"] = False
        payload["broker_is_second_governor"] = False
        exit_code = EXIT_OK
        if result.outcome.value in {"SAFETY_STOP", "HARD_BLOCKED"}:
            exit_code = EXIT_ERROR
        return payload, exit_code
    except (TrustError, DiscoveryError, LoopError, BrokerError) as exc:
        code = getattr(exc, "code", "BROKER_FAILED_CLOSED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR


def run_governor_service(
    *,
    root: Path,
    trust_store: Path | None = None,
    loop_store: Path | None = None,
    broker_store: Path | None = None,
    host_store: Path | None = None,
    poll_seconds: float = 2.0,
    owner_backoff_seconds: float = 5.0,
) -> tuple[dict[str, object], int]:
    """Long-lived durable host. Returns only on stop/safety/unrecoverable."""
    from project_atlas.orchestration.autonomy.broker import (
        BROKER_PACKAGE_ID,
        BrokerError,
        ContinuationBroker,
        wire_001d_dispatch_port,
    )
    from project_atlas.orchestration.autonomy.broker import (
        STATE_DIR_RELATIVE as BROKER_STATE_DIR,
    )
    from project_atlas.orchestration.autonomy.host_service import (
        STATE_DIR_RELATIVE as HOST_STATE_DIR,
    )
    from project_atlas.orchestration.autonomy.host_service import (
        DurableHostService,
        HostError,
        HostStopReason,
    )
    from project_atlas.orchestration.autonomy.local_agent import select_mutating_backend_name
    from project_atlas.orchestration.autonomy.mutating_transport import (
        MutatingExecutionPort,
        ProcessMutatingBackend,
        cloud_api_key_present,
        local_cursor_cli_present,
    )

    try:
        trusted = _load_trusted(trust_store=trust_store, allow_shipped=trust_store is None)
        inventory = collect_live_inventory(root)
        governor = AutonomousGovernor(
            current_main=inventory.current_main,
            current_tree=inventory.current_tree,
            trusted_anchor=trusted,
        )
        broker = ContinuationBroker(
            governor=governor,
            trusted=trusted,
            store=broker_store or (root / BROKER_STATE_DIR),
            root=root,
            loop_store=loop_store,
            dispatch=wire_001d_dispatch_port(),
        )
        mutating: MutatingExecutionPort
        backend_name = select_mutating_backend_name()
        if backend_name.value == "CLOUD_API":
            from project_atlas.orchestration.autonomy.cursor_cloud import CursorCloudBackend

            mutating = CursorCloudBackend()
        elif backend_name.value == "LOCAL_AGENT":
            from project_atlas.orchestration.autonomy.local_agent import LocalAgentBackend

            mutating = LocalAgentBackend()
        else:
            mutating = ProcessMutatingBackend(
                root=root,
                store=root / ".atlas" / "orchestration" / "workers" / "mutating",
            )
        service = DurableHostService(
            governor=governor,
            broker=broker,
            store=host_store or (root / HOST_STATE_DIR),
            root=root,
            trusted=trusted,
            mutating=mutating,
            poll_seconds=poll_seconds,
            owner_backoff_seconds=owner_backoff_seconds,
        )
        reason = service.run()
        payload = {
            "schema_version": 1,
            "package_id": BROKER_PACKAGE_ID,
            "stop_reason": reason.value,
            "backend_selected": backend_name.value,
            "cloud_api_key_present": cloud_api_key_present(),
            "local_cursor_authenticated": local_cursor_cli_present(),
            "host_is_second_governor": False,
            "merge_authorized": False,
            "execution_authorized": False,
        }
        exit_code = EXIT_OK if reason is HostStopReason.EXPLICIT_STOP else EXIT_ERROR
        return payload, exit_code
    except (TrustError, DiscoveryError, LoopError, HostError, BrokerError) as exc:
        code = getattr(exc, "code", "HOST_FAILED_CLOSED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR


def run_governor_service_stop(
    *,
    root: Path,
    host_store: Path | None = None,
) -> tuple[dict[str, object], int]:
    from project_atlas.orchestration.autonomy.host_service import (
        STATE_DIR_RELATIVE as HOST_STATE_DIR,
    )
    from project_atlas.orchestration.autonomy.host_service import request_stop

    store = host_store or (root / HOST_STATE_DIR)
    request_stop(store)
    return {
        "schema_version": 1,
        "package_id": AUTONOMY_PACKAGE_ID,
        "stop_requested": True,
        "merge_authorized": False,
    }, EXIT_OK


def run_governor_service_install(
    *,
    root: Path,
    output: Path | None = None,
) -> tuple[dict[str, object], int]:
    import shutil
    import sys

    from project_atlas.orchestration.autonomy.host_install import (
        SYSTEMD_UNIT_NAME,
        TASK_NAME,
        render_systemd_user_unit,
        render_windows_schtasks_command,
        write_linux_unit,
    )

    atlas_bin = shutil.which("atlas") or sys.executable + " -m project_atlas.cli"
    unit_text = render_systemd_user_unit(root=root, atlas_bin=atlas_bin)
    task_cmd = render_windows_schtasks_command(root=root, atlas_bin=atlas_bin)
    written = None
    if output is not None:
        written = str(write_linux_unit(output=output, root=root, atlas_bin=atlas_bin))
    return {
        "schema_version": 1,
        "package_id": AUTONOMY_PACKAGE_ID,
        "linux_unit": SYSTEMD_UNIT_NAME,
        "windows_task": TASK_NAME,
        "linux_unit_text": unit_text,
        "windows_command": task_cmd,
        "unit_path": written,
        "secrets_embedded": False,
        "merge_authorized": False,
    }, EXIT_OK


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
        governor = AutonomousGovernor(
            current_main=inventory.current_main,
            current_tree=inventory.current_tree,
            trusted_anchor=trusted,
        )
        store = loop_store or (root / STATE_DIR_RELATIVE)
        loop = AutonomousLoop(
            governor=governor,
            trusted=trusted,
            store=store,
            root=root,
        )
        result = loop.tick()
        payload = result.model_dump(mode="json")
        payload["package_id"] = "AS-ORCH-001E"
        payload["merge_authorized"] = False
        payload["execution_authorized"] = False
        return payload, EXIT_OK if result.phase.value != "FAILED_CLOSED" else EXIT_ERROR
    except (TrustError, DiscoveryError, LoopError) as exc:
        code = getattr(exc, "code", "LOOP_FAILED_CLOSED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR


def observed_repository_identity(remote_url: str) -> str:
    """CLI helper for evidence capture. Not an authority grant."""
    return normalize_repository_identity(remote_url)
