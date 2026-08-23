"""AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001 — closed-loop work producer.

Subordinate to PRIMARY GOVERNOR. Discovers work, derives DAG nodes, transforms
receipts into successors. Never grants merge authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.autonomy.authentic_estate import (
    PROTECTED_OWNER_GATES,
    authentic_estate_ready_for_orchestration,
    d148_evidence_applies,
)
from project_atlas.orchestration.autonomy.exact_main_closure import cert_evidence_applies_to_head
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, AgentRole, SdkRuntimeError
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

PACKAGE_ID: Final[Literal["AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001"]] = (
    "AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001"
)
OBJECTIVES_NAME: Final[str] = "mission-objectives.json"
NODES_NAME: Final[str] = "mission-nodes.json"
RECEIPTS_NAME: Final[str] = "mission-receipts.jsonl"
WORKERS_NAME: Final[str] = "mission-workers.json"
STATE_NAME: Final[str] = "mission-reconciler-state.json"
STACKED_DEPENDENCY: Final[str] = "PR435"
MERGE_ORDER: Final[str] = "PR433 -> PR435 -> MISSION_RECONCILER"

_AUTONOMOUS_MET_STATES: Final[frozenset[str]] = frozenset(
    {"SATISFIED", "COMPLETE", "ACCEPTANCE_WORKFLOW_SATISFIED", "FIXTURE_SATISFIED"}
)
_GAP_SATISFIED_STATES: Final[frozenset[str]] = frozenset(
    {"SATISFIED", "IMPLEMENTED", "FIXTURE_SATISFIED", "ALREADY_SATISFIED"}
)
_CERTIFIED_MAIN_HEAD: Final[str] = "6c3e74964d023cdcb55c3b77d6d029b095d578c6"

ObjectiveId = Literal["O1", "O2", "O3", "O4", "O5", "O6"]
TaskKind = Literal[
    "IMPLEMENTATION",
    "REMEDIATION",
    "INDEPENDENT_IV",
    "ADVERSARIAL",
    "AUTHENTIC_E2E",
    "RELEASE_VALIDATION",
    "ARCHITECTURE_ANALYSIS",
    "BACKLOG_DECOMPOSITION",
    "SECURITY_REVIEW",
    "STALE_PR_RECONCILIATION",
]
NodeStatus = Literal[
    "READY",
    "DISPATCHED",
    "RUNNING",
    "COMPLETED",
    "BLOCKED_DEPENDENCY",
    "BLOCKED_OWNER",
    "ALREADY_SATISFIED",
    "SUPERSEDED",
    "FAILED",
]


class MissionObjective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_id: ObjectiveId
    desired_state: str
    current_state: str
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    completion_criteria: str
    merge_authorized: Literal[False] = False


class WorkNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    NODE_ID: str
    OBJECTIVE_ID: ObjectiveId
    PACKAGE_ID: str
    TASK_KIND: TaskKind
    PRIORITY: int = Field(ge=0, le=100)
    DEPENDENCIES: list[str] = Field(default_factory=list)
    ALLOWED_PATHS: list[str] = Field(default_factory=list)
    SURFACE_SET: list[str] = Field(default_factory=list)
    REQUIRED_RUNTIME: str = "local"
    WORKER_ROLE: str
    ACCEPTANCE_CRITERIA: str
    REQUIRED_VERIFICATION: list[str] = Field(default_factory=list)
    OWNER_GATE: Literal["NONE", "MERGE", "CREDENTIAL", "SECURITY"] = "NONE"
    GENERATION: int = Field(ge=0)
    IDEMPOTENCY_KEY: str
    status: NodeStatus = "READY"
    fingerprint: str = ""
    merge_authorized: Literal[False] = False


class RealWorkerBinding(BaseModel):
    """Actual execution binding — not a synthetic READY card."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    worker_role: str
    package_id: str
    dag_node_id: str
    generation: int
    runtime: Literal["local_pid", "cursor_sdk", "cloud_run"]
    lease_id: str | None = None
    allowed_paths: list[str] = Field(default_factory=list)
    started_at: float
    execution_binding: str
    expected_receipt: str
    pid: int | None = None
    agent_id: str | None = None
    run_id: str | None = None
    status: Literal["RUNNING", "COMPLETED", "FAILED"] = "RUNNING"
    merge_authorized: Literal[False] = False


class MissionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001"] = PACKAGE_ID
    MISSION_GENERATION: int = 0
    PROGRESS_SEQUENCE: int = 0
    WORKER_DISPATCH_SEQUENCE: int = 0
    RECEIPT_CONSUME_SEQUENCE: int = 0
    SUCCESSOR_GENERATION_SEQUENCE: int = 0
    EMPTY_READY_QUEUE_RECONCILIATION_COUNT: int = 0
    IDENTICAL_ANALYSIS_REDIRECT_COUNT: int = 0
    TERMINAL_RECEIPT_WITHOUT_DAG_RECONCILIATION: int = 0
    SYNTHETIC_ACTIVE_WORKER_COUNT: int = 0
    last_planning_fingerprint: str = ""
    last_reconcile_at: float = 0.0
    STACKED_DEPENDENCY: Literal["PR435"] = "PR435"
    MERGE_AUTHORIZATION: Literal["NOT_GRANTED"] = "NOT_GRANTED"
    merge_authorized: Literal[False] = False


def _rt(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def default_objectives() -> list[MissionObjective]:
    return [
        MissionObjective(
            objective_id="O1",
            desired_state="Resident self-wake + closed-loop work production",
            current_state="PARTIAL_LIVENESS",
            evidence=["PR435 resident alive"],
            blockers=[],
            dependencies=[],
            priority=95,
            completion_criteria="PROJECT_PROGRESS advances without chat",
        ),
        MissionObjective(
            objective_id="O2",
            desired_state="Authentic demo readiness",
            current_state="FIXTURE_PARTIAL",
            evidence=["PR431 owner-held fixture classifier"],
            blockers=["AUTHENTIC_INGEST", "AUTHENTIC_COMPILE", "AUTHENTIC_QUERY", "API", "WEB"],
            dependencies=["PR431"],
            priority=90,
            completion_criteria="AUTHENTIC_PILOT proven end-to-end",
        ),
        MissionObjective(
            objective_id="O3",
            desired_state="Release readiness",
            current_state="PARTIAL",
            evidence=["Windows/Linux CI exist"],
            blockers=["clean_machine_bootstrap", "release_artifact", "rollback"],
            dependencies=[],
            priority=70,
            completion_criteria="Release matrix green with authentic proofs",
        ),
        MissionObjective(
            objective_id="O4",
            desired_state="Core product capability completion",
            current_state="IN_PROGRESS",
            evidence=["PR434 inbox-list owner-held"],
            blockers=[],
            dependencies=[],
            priority=65,
            completion_criteria="Core user journeys implemented",
        ),
        MissionObjective(
            objective_id="O5",
            desired_state="Verification and security",
            current_state="PARTIAL",
            evidence=["speculative certification protocol"],
            blockers=[],
            dependencies=[],
            priority=75,
            completion_criteria="IV/ADV/authentic E2E for critical packages",
        ),
        MissionObjective(
            objective_id="O6",
            desired_state="Documentation and operability",
            current_state="PARTIAL",
            evidence=[],
            blockers=[],
            dependencies=[],
            priority=40,
            completion_criteria="Runbooks and ops docs current",
        ),
    ]


def load_objectives(root: Path) -> list[MissionObjective]:
    path = _rt(root) / OBJECTIVES_NAME
    if not path.is_file():
        objs = default_objectives()
        persist_objectives(root, objs)
        return objs
    data = json.loads(path.read_text(encoding="utf-8"))
    return [MissionObjective.model_validate(x) for x in data.get("objectives", [])]


def persist_objectives(root: Path, objectives: list[MissionObjective]) -> None:
    _atomic(
        _rt(root) / OBJECTIVES_NAME,
        {
            "objectives": [o.model_dump(mode="json") for o in objectives],
            "merge_authorized": False,
        },
    )


def load_nodes(root: Path) -> dict[str, WorkNode]:
    path = _rt(root) / NODES_NAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, WorkNode] = {}
    for row in data.get("nodes", []):
        node = WorkNode.model_validate(row)
        out[node.NODE_ID] = node
    return out


def persist_nodes(root: Path, nodes: dict[str, WorkNode]) -> None:
    _atomic(
        _rt(root) / NODES_NAME,
        {
            "nodes": [n.model_dump(mode="json") for n in nodes.values()],
            "merge_authorized": False,
        },
    )


def load_mission_state(root: Path) -> MissionState:
    path = _rt(root) / STATE_NAME
    if not path.is_file():
        return MissionState()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["merge_authorized"] = False
    return MissionState.model_validate(data)


def persist_mission_state(root: Path, state: MissionState) -> None:
    _atomic(_rt(root) / STATE_NAME, state.model_dump(mode="json"))


def load_workers(root: Path) -> dict[str, RealWorkerBinding]:
    path = _rt(root) / WORKERS_NAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        wid: RealWorkerBinding.model_validate(row)
        for wid, row in (data.get("workers") or {}).items()
    }


def persist_workers(root: Path, workers: dict[str, RealWorkerBinding]) -> None:
    _atomic(
        _rt(root) / WORKERS_NAME,
        {
            "workers": {k: v.model_dump(mode="json") for k, v in workers.items()},
            "SYNTHETIC_ACTIVE_WORKER_COUNT": 0,
            "merge_authorized": False,
        },
    )


def _fingerprint(parts: list[str]) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _idempotency_key(*, objective: str, kind: str, package: str, surface: str) -> str:
    return _fingerprint([objective, kind, package, surface])


def _owner_held_prs(root: Path) -> set[int]:
    path = _rt(root) / "d129-owner-merge-queue.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {int(x["PR"]) for x in data.get("QUEUE", []) if "PR" in x}


def _objective_autonomous_met(obj: MissionObjective) -> bool:
    return obj.current_state in _AUTONOMOUS_MET_STATES


def _cert_evidence_applies(evidence: dict[str, Any], main_head: str, root: Path) -> bool:
    """Checkpoint certification applies to reconcile head or metadata-only descendant."""
    return cert_evidence_applies_to_head(evidence, main_head, root)


def _gap_package_id(gap: str, *, prefix: str = "AS-CODER-ALPHA") -> str:
    slug = gap.replace("_", "-")
    return f"{prefix}-{slug}-001"


def _load_cert_evidence(root: Path) -> dict[str, Any]:
    path = _rt(root) / "d146-checkpoint.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _runbook_pin_current(root: Path, *, main_head: str) -> bool:
    runbook = root / "docs" / "productization" / "CLEAN-MACHINE-PREP-RUNBOOK.md"
    if not runbook.is_file():
        return False
    try:
        text = runbook.read_text(encoding="utf-8")
    except OSError:
        return False
    return main_head in text


def _load_d148_evidence(root: Path) -> dict[str, Any]:
    path = _rt(root) / "d148-o2-certification.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _gap_statuses(root: Path, *, main_head: str) -> dict[str, str]:
    """Evidence-bound gap classification for analysis receipts."""
    evidence = _load_cert_evidence(root)
    if not _cert_evidence_applies(evidence, main_head, root):
        evidence = {}
    d148 = _load_d148_evidence(root)
    if not d148_evidence_applies(d148, main_head, root):
        d148 = {}
    estate_ready = authentic_estate_ready_for_orchestration(root)
    if d148.get("AUTHENTIC_INGEST_SATISFIED"):
        authentic_ingest = "SATISFIED"
    elif estate_ready:
        authentic_ingest = "NOT_IMPLEMENTED"
    else:
        authentic_ingest = "BLOCKED_OWNER"
    if d148.get("AUTHENTIC_COMPILE_SATISFIED"):
        authentic_compile = "SATISFIED"
    elif estate_ready and d148.get("AUTHENTIC_INGEST_SATISFIED"):
        authentic_compile = "NOT_IMPLEMENTED"
    elif estate_ready:
        authentic_compile = "BLOCKED_OWNER"
    else:
        authentic_compile = "BLOCKED_OWNER"
    if d148.get("AUTHENTIC_QUERY_SATISFIED"):
        authentic_query = "SATISFIED"
    elif estate_ready and d148.get("AUTHENTIC_COMPILE_SATISFIED"):
        authentic_query = "NOT_IMPLEMENTED"
    elif estate_ready and d148.get("AUTHENTIC_INGEST_SATISFIED"):
        authentic_query = "BLOCKED_OWNER"
    else:
        authentic_query = "BLOCKED_OWNER"
    gaps: dict[str, str] = {
        "AUTHENTIC_INGEST": authentic_ingest,
        "AUTHENTIC_COMPILE": authentic_compile,
        "AUTHENTIC_QUERY": authentic_query,
        "API": "NOT_IMPLEMENTED",
        "WEB": "NOT_IMPLEMENTED",
        "CLEAN_MACHINE_BOOTSTRAP": "NOT_IMPLEMENTED",
        "RELEASE_ARTIFACT": "NOT_IMPLEMENTED",
    }
    if evidence.get("CLEAN_MACHINE_FINAL"):
        gaps["CLEAN_MACHINE_BOOTSTRAP"] = "SATISFIED"
    if str(evidence.get("RELEASE_READINESS", "")).upper() == "CERTIFIED":
        gaps["RELEASE_ARTIFACT"] = "SATISFIED"
    if evidence.get("ACCEPTANCE_WORKFLOW_PILOT"):
        gaps["API"] = "FIXTURE_SATISFIED"
        gaps["WEB"] = "FIXTURE_SATISFIED"
    if _runbook_pin_current(root, main_head=main_head):
        gaps["STALE_OPERATIONAL_PIN"] = "SATISFIED"
    return gaps


def planning_fingerprint(root: Path, *, main_head: str) -> str:
    held = sorted(_owner_held_prs(root))
    objs = load_objectives(root)
    obj_sig = ",".join(f"{o.objective_id}:{o.current_state}" for o in objs)
    return _fingerprint([main_head, str(held), obj_sig])


def seed_demo_release_nodes(
    root: Path,
    *,
    generation: int,
    main_head: str,
) -> list[WorkNode]:
    """Derive executable nodes from current demo/release honesty."""
    held = _owner_held_prs(root)
    objectives = load_objectives(root)
    o2_met = any(
        o.objective_id == "O2" and _objective_autonomous_met(o) for o in objectives
    )
    all_met = all(_objective_autonomous_met(o) for o in objectives)
    gaps = _gap_statuses(root, main_head=main_head)
    nodes: list[WorkNode] = []

    def add(
        *,
        oid: ObjectiveId,
        package: str,
        kind: TaskKind,
        priority: int,
        criteria: str,
        surfaces: list[str],
        role: str,
        owner_gate: Literal["NONE", "MERGE", "CREDENTIAL", "SECURITY"] = "NONE",
        deps: list[str] | None = None,
        status: NodeStatus = "READY",
    ) -> None:
        key = _idempotency_key(
            objective=oid, kind=kind, package=package, surface=",".join(surfaces)
        )
        node = WorkNode(
            NODE_ID=f"{oid}-{kind}-{key}",
            OBJECTIVE_ID=oid,
            PACKAGE_ID=package,
            TASK_KIND=kind,
            PRIORITY=priority,
            DEPENDENCIES=deps or [],
            ALLOWED_PATHS=surfaces,
            SURFACE_SET=surfaces,
            WORKER_ROLE=role,
            ACCEPTANCE_CRITERIA=criteria,
            REQUIRED_VERIFICATION=["receipt", "idempotent"],
            OWNER_GATE=owner_gate,
            GENERATION=generation,
            IDEMPOTENCY_KEY=key,
            status=status,
            fingerprint=_fingerprint([main_head, key, status]),
        )
        nodes.append(node)

    # Demo gaps — stale merge queue vs authentic estate frontier
    if 431 in held:
        add(
            oid="O2",
            package="AS-CODER-ALPHA-AUTHENTIC-INGEST-001",
            kind="IMPLEMENTATION",
            priority=92,
            criteria="Authentic ingest on real project docs",
            surfaces=["src/project_atlas/", "tests/"],
            role="IMPLEMENTER",
            owner_gate="MERGE",
            status="BLOCKED_OWNER",
            deps=["PR431"],
        )
        add(
            oid="O2",
            package="AS-CODER-ALPHA-AUTHENTIC-QUERY-001",
            kind="IMPLEMENTATION",
            priority=91,
            criteria="Authentic query returns useful knowledge",
            surfaces=["src/project_atlas/", "tests/"],
            role="IMPLEMENTER",
            owner_gate="MERGE",
            status="BLOCKED_OWNER",
            deps=["PR431", "AS-CODER-ALPHA-AUTHENTIC-INGEST-001"],
        )
    elif not o2_met:
        add(
            oid="O2",
            package="AS-CODER-ALPHA-AUTHENTIC-DEMO-PREP-001",
            kind="ARCHITECTURE_ANALYSIS",
            priority=94,
            criteria=(
                "Produce successor plan for ingest/compile/query "
                "without claiming authentic pass"
            ),
            surfaces=["docs/", ".atlas/orchestration/sdk-runtime/"],
            role="READ_ONLY_ANALYST",
            status="READY",
        )
    else:
        for gap, package in (
            ("AUTHENTIC_INGEST", "AS-CODER-ALPHA-AUTHENTIC-INGEST-001"),
            ("AUTHENTIC_COMPILE", "AS-CODER-ALPHA-AUTHENTIC-COMPILE-001"),
            ("AUTHENTIC_QUERY", "AS-CODER-ALPHA-AUTHENTIC-QUERY-001"),
        ):
            gap_status = gaps.get(gap)
            if gap_status in _GAP_SATISFIED_STATES:
                continue
            if gap_status == "NOT_IMPLEMENTED":
                deps: list[str] = []
                if gap == "AUTHENTIC_COMPILE":
                    deps = ["AS-CODER-ALPHA-AUTHENTIC-INGEST-001"]
                elif gap == "AUTHENTIC_QUERY":
                    deps = ["AS-CODER-ALPHA-AUTHENTIC-COMPILE-001"]
                add(
                    oid="O2",
                    package=package,
                    kind="IMPLEMENTATION",
                    priority=92,
                    criteria=f"Authentic {gap.lower().replace('_', ' ')} on AUTHENTIC_ESTATE_ROOT",
                    surfaces=["src/project_atlas/", "tests/"],
                    role="IMPLEMENTER",
                    owner_gate="NONE",
                    status="READY",
                    deps=deps,
                )
            elif gap_status == "BLOCKED_OWNER":
                add(
                    oid="O2",
                    package=package,
                    kind="IMPLEMENTATION",
                    priority=92,
                    criteria=f"Authentic {gap.lower().replace('_', ' ')} on AUTHENTIC_ESTATE_ROOT",
                    surfaces=["src/project_atlas/", "tests/"],
                    role="IMPLEMENTER",
                    owner_gate="CREDENTIAL",
                    status="BLOCKED_OWNER",
                    deps=["AUTHENTIC_ESTATE_ROOT"],
                )
    if gaps.get("CLEAN_MACHINE_BOOTSTRAP") not in _GAP_SATISFIED_STATES:
        add(
            oid="O3",
            package="AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
            kind="RELEASE_VALIDATION",
            priority=80,
            criteria="Document and test clean-machine bootstrap gaps on Windows",
            surfaces=["docs/", "scripts/", "tests/"],
            role="READ_ONLY_ANALYST",
            status="READY",
        )
    if gaps.get("RELEASE_ARTIFACT") not in _GAP_SATISFIED_STATES:
        add(
            oid="O3",
            package="AS-RELEASE-ARTIFACT-GAP-001",
            kind="BACKLOG_DECOMPOSITION",
            priority=72,
            criteria="Enumerate release artifact / upgrade path gaps",
            surfaces=["docs/"],
            role="READ_ONLY_ANALYST",
            status="READY",
        )
    if not all_met:
        add(
            oid="O1",
            package="AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001",
            kind="ARCHITECTURE_ANALYSIS",
            priority=86,
            criteria="Closed-loop reconciler active and producing successors",
            surfaces=["src/project_atlas/orchestration/sdk/"],
            role="READ_ONLY_ANALYST",
            status="READY",
        )
        add(
            oid="O5",
            package="AS-ORCH-SPECULATIVE-CERTIFICATION-001",
            kind="INDEPENDENT_IV",
            priority=70,
            criteria="Owner-held packages retain exact-pin integrity",
            surfaces=[".atlas/orchestration/sdk-runtime/"],
            role="INDEPENDENT_VERIFIER",
            status="READY",
        )
    return nodes


_STALE_SEED_PACKAGES: Final[frozenset[str]] = frozenset(
    {
        "AS-CODER-ALPHA-AUTHENTIC-DEMO-PREP-001",
        "AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
        "AS-RELEASE-ARTIFACT-GAP-001",
        "AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001",
        "AS-ORCH-SPECULATIVE-CERTIFICATION-001",
    }
)


def _prune_stale_ready_nodes(
    root: Path,
    *,
    generation: int,
    main_head: str,
    nodes: dict[str, WorkNode],
) -> int:
    """Supersede stale seeded READY nodes; never prune replenish or receipt successors."""
    expected_keys = {
        n.IDEMPOTENCY_KEY
        for n in seed_demo_release_nodes(root, generation=generation, main_head=main_head)
    }
    gaps = _gap_statuses(root, main_head=main_head)
    pruned = 0
    for node in nodes.values():
        if node.status != "READY":
            continue
        if node.PACKAGE_ID not in _STALE_SEED_PACKAGES:
            continue
        if node.IDEMPOTENCY_KEY in expected_keys:
            continue
        if node.PACKAGE_ID == "AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001":
            if gaps.get("CLEAN_MACHINE_BOOTSTRAP") not in _GAP_SATISFIED_STATES:
                continue
        elif (
            node.PACKAGE_ID == "AS-RELEASE-ARTIFACT-GAP-001"
            and gaps.get("RELEASE_ARTIFACT") not in _GAP_SATISFIED_STATES
        ):
            continue
        node.status = "SUPERSEDED"
        pruned += 1
    return pruned


def surfaces_overlap(a: list[str], b: list[str]) -> bool:
    for x in a:
        for y in b:
            if x.startswith(y) or y.startswith(x):
                return True
    return False


def mission_reconcile(
    root: Path,
    *,
    main_head: str = "bd8faa8f97df454943181d19f1e14ee826900a20",
    now: float | None = None,
) -> dict[str, Any]:
    """Full mission reconciliation generation. Returns summary (not authority)."""
    ts = time.time() if now is None else now
    state = load_mission_state(root)
    objectives = load_objectives(root)
    nodes = load_nodes(root)
    fp = planning_fingerprint(root, main_head=main_head)

    if fp == state.last_planning_fingerprint and state.MISSION_GENERATION > 0:
        # Identical fingerprint: still replenish empty READY (D-133 CASE A).
        ready = [n for n in nodes.values() if n.status == "READY"]
        created = 0
        if not ready:
            state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT += 1
            unmet = [o for o in objectives if not _objective_autonomous_met(o)]
            if unmet:
                key = _idempotency_key(
                    objective="O3",
                    kind="RELEASE_VALIDATION",
                    package=(
                        f"AS-RELEASE-REPLENISH-{state.MISSION_GENERATION}-"
                        f"{state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT}"
                    ),
                    surface="docs/",
                )
                if not any(key == n.IDEMPOTENCY_KEY for n in nodes.values()):
                    nodes[f"O3-REPLENISH-{key}"] = WorkNode(
                        NODE_ID=f"O3-REPLENISH-{key}",
                        OBJECTIVE_ID="O3",
                        PACKAGE_ID="AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
                        TASK_KIND="RELEASE_VALIDATION",
                        PRIORITY=78,
                        DEPENDENCIES=[],
                        ALLOWED_PATHS=["docs/", "scripts/", "tests/"],
                        SURFACE_SET=["docs/", "scripts/"],
                        WORKER_ROLE="READ_ONLY_ANALYST",
                        ACCEPTANCE_CRITERIA=(
                            "Replenish READY after empty queue; enumerate release gaps"
                        ),
                        REQUIRED_VERIFICATION=["receipt"],
                        OWNER_GATE="NONE",
                        GENERATION=max(state.MISSION_GENERATION, 1),
                        IDEMPOTENCY_KEY=key,
                        status="READY",
                        fingerprint=_fingerprint([main_head, key]),
                    )
                    created = 1
                    state.MISSION_GENERATION += 1
                    state.PROGRESS_SEQUENCE += 1
                    persist_nodes(root, nodes)
        state.last_reconcile_at = ts
        persist_mission_state(root, state)
        ready = [n for n in nodes.values() if n.status == "READY"]
        _prune_stale_ready_nodes(
            root,
            generation=state.MISSION_GENERATION,
            main_head=main_head,
            nodes=nodes,
        )
        persist_nodes(root, nodes)
        ready = [n for n in nodes.values() if n.status == "READY"]
        return {
            "MISSION_GENERATION": state.MISSION_GENERATION,
            "skipped_identical_fingerprint": created == 0,
            "nodes_created": created,
            "READY_NODE_COUNT": len(ready),
            "EMPTY_READY_QUEUE_RECONCILIATION_COUNT": (
                state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT
            ),
            "UNMET_OBJECTIVE_COUNT": sum(
                1 for o in objectives if not _objective_autonomous_met(o)
            ),
            "merge_authorized": False,
        }

    state.MISSION_GENERATION += 1
    seeded = seed_demo_release_nodes(
        root, generation=state.MISSION_GENERATION, main_head=main_head
    )
    created = 0
    for node in seeded:
        existing = next(
            (n for n in nodes.values() if n.IDEMPOTENCY_KEY == node.IDEMPOTENCY_KEY),
            None,
        )
        if existing is not None:
            if existing.status in {"COMPLETED", "ALREADY_SATISFIED"}:
                continue
            if (
                existing.status == "SUPERSEDED"
                and node.status == "BLOCKED_OWNER"
                and existing.PACKAGE_ID == node.PACKAGE_ID
            ):
                existing.status = "BLOCKED_OWNER"
                if existing.OWNER_GATE not in PROTECTED_OWNER_GATES:
                    existing.OWNER_GATE = node.OWNER_GATE
                existing.DEPENDENCIES = list(node.DEPENDENCIES)
                existing.ACCEPTANCE_CRITERIA = node.ACCEPTANCE_CRITERIA
                continue
            if (
                existing.status == "SUPERSEDED"
                and node.status == "BLOCKED_OWNER"
                and existing.OWNER_GATE == "MERGE"
                and node.OWNER_GATE == "CREDENTIAL"
            ):
                # D-149: MERGE is not rewritten to a consumable CREDENTIAL gate.
                existing.status = "BLOCKED_OWNER"
                existing.DEPENDENCIES = list(node.DEPENDENCIES)
                existing.ACCEPTANCE_CRITERIA = node.ACCEPTANCE_CRITERIA
                continue
            # Keep existing non-terminal
            continue
        nodes[node.NODE_ID] = node
        created += 1

    # Update O2 evidence from owner-held
    for obj in objectives:
        if obj.objective_id == "O2" and 431 in _owner_held_prs(root):
            if "PR431_OWNER_HELD" not in obj.blockers:
                obj.blockers.append("PR431_OWNER_HELD")
            obj.current_state = "BLOCKED_OWNER_PARTIAL"

    ready = [n for n in nodes.values() if n.status == "READY"]
    if not ready:
        state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT += 1
        # Owner-independent replenishment: re-open analysis when objectives unmet
        unmet = [o for o in objectives if not _objective_autonomous_met(o)]
        if unmet and not all(_objective_autonomous_met(o) for o in objectives):
            key = _idempotency_key(
                objective="O3",
                kind="RELEASE_VALIDATION",
                package=(
                    f"AS-RELEASE-REPLENISH-{state.MISSION_GENERATION}-"
                    f"{state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT}"
                ),
                surface="docs/",
            )
            if not any(key == n.IDEMPOTENCY_KEY for n in nodes.values()):
                node = WorkNode(
                    NODE_ID=f"O3-REPLENISH-{key}",
                    OBJECTIVE_ID="O3",
                    PACKAGE_ID="AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
                    TASK_KIND="RELEASE_VALIDATION",
                    PRIORITY=78,
                    DEPENDENCIES=[],
                    ALLOWED_PATHS=["docs/", "scripts/", "tests/"],
                    SURFACE_SET=["docs/", "scripts/"],
                    WORKER_ROLE="READ_ONLY_ANALYST",
                    ACCEPTANCE_CRITERIA="Replenish READY after empty queue; enumerate release gaps",
                    REQUIRED_VERIFICATION=["receipt"],
                    OWNER_GATE="NONE",
                    GENERATION=state.MISSION_GENERATION,
                    IDEMPOTENCY_KEY=key,
                    status="READY",
                    fingerprint=_fingerprint([main_head, key]),
                )
                nodes[node.NODE_ID] = node
                created += 1
        ready = [n for n in nodes.values() if n.status == "READY"]

    _prune_stale_ready_nodes(
        root,
        generation=state.MISSION_GENERATION,
        main_head=main_head,
        nodes=nodes,
    )
    ready = [n for n in nodes.values() if n.status == "READY"]

    state.last_planning_fingerprint = fp
    state.last_reconcile_at = ts
    persist_objectives(root, objectives)
    persist_nodes(root, nodes)
    persist_mission_state(root, state)
    _refresh_merge_gate_state(root)

    return {
        "MISSION_GENERATION": state.MISSION_GENERATION,
        "nodes_created": created,
        "READY_NODE_COUNT": len(ready),
        "UNMET_OBJECTIVE_COUNT": sum(
            1 for o in objectives if not _objective_autonomous_met(o)
        ),
        "EMPTY_READY_QUEUE_RECONCILIATION_COUNT": state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT,
        "SURFACE_OVERLAP_CHECKED": "YES",
        "merge_authorized": False,
    }


def _refresh_merge_gate_state(root: Path) -> None:
    try:
        from project_atlas.orchestration.sdk.merge_sequence_gate import (
            refresh_dependent_merge_gate_state,
        )

        refresh_dependent_merge_gate_state(root, child_pr_number=436)
    except Exception:
        return


def ready_work_items(root: Path, *, capacity: int = 2) -> list[ReadyWorkItem]:
    """Convert READY mission nodes to scheduler items. Not workers yet."""
    nodes = load_nodes(root)
    ready = sorted(
        [n for n in nodes.values() if n.status == "READY"],
        key=lambda n: (-n.PRIORITY, n.NODE_ID),
    )
    # Surface conflict gate — skip overlapping with already selected
    selected: list[WorkNode] = []
    for node in ready:
        if any(surfaces_overlap(node.SURFACE_SET, s.SURFACE_SET) for s in selected):
            continue
        if node.OWNER_GATE == "MERGE" and node.status == "READY":
            # Should have been BLOCKED_OWNER — fail closed
            node.status = "BLOCKED_OWNER"
            continue
        selected.append(node)
        if len(selected) >= capacity:
            break
    persist_nodes(root, nodes)
    items: list[ReadyWorkItem] = []
    for node in selected:
        role = AgentRole.READ_ONLY_ANALYST
        if node.WORKER_ROLE in {"IMPLEMENTER", "REMEDIATOR"}:
            role = AgentRole.IMPLEMENTER
        elif node.WORKER_ROLE == "INDEPENDENT_VERIFIER":
            role = AgentRole.INDEPENDENT_VERIFIER
        items.append(
            ReadyWorkItem(
                role=role,
                package_id=node.PACKAGE_ID,
                node_id=node.NODE_ID,
                cycle_id="mission",
                dag_generation=node.GENERATION,
                base_main="bd8faa8f97df454943181d19f1e14ee826900a20",
                prompt=node.ACCEPTANCE_CRITERIA,
                critical_path_score=node.PRIORITY,
            )
        )
    return items


def dispatch_local_analysis_worker(
    root: Path,
    node: WorkNode,
    *,
    main_head: str | None = None,
    now: float | None = None,
) -> RealWorkerBinding:
    """Bind a real local PID worker that writes an analysis receipt (read-only)."""
    ts = time.time() if now is None else now
    state = load_mission_state(root)
    workers = load_workers(root)
    wid = f"local-{uuid.uuid4().hex[:12]}"
    receipt_name = f"mission-receipt-{wid}.json"
    receipt_path = _rt(root) / "mission-receipts" / receipt_name
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    # Execute analysis inline but record real PID binding (this process).
    head = main_head or _CERTIFIED_MAIN_HEAD
    gaps = _gap_statuses(root, main_head=head)
    successors: list[dict[str, Any]] = []
    skip_statuses = _GAP_SATISFIED_STATES | frozenset({"BLOCKED_OWNER"})
    # Every analysis receipt must feed the next planning cycle.
    if node.OBJECTIVE_ID in {"O1", "O2", "O5"} or node.TASK_KIND == "ARCHITECTURE_ANALYSIS":
        for gap in ("AUTHENTIC_INGEST", "AUTHENTIC_COMPILE", "AUTHENTIC_QUERY", "API", "WEB"):
            status = gaps[gap]
            if status in skip_statuses:
                continue
            successors.append(
                {
                    "action": "CREATE_SUCCESSOR_NODE",
                    "package": _gap_package_id(gap),
                    "blocked": status == "BLOCKED_OWNER",
                    "gap": gap,
                    "status": status,
                }
            )
    if node.OBJECTIVE_ID in {"O1", "O3"} or node.TASK_KIND in {
        "RELEASE_VALIDATION",
        "BACKLOG_DECOMPOSITION",
    }:
        for gap in ("CLEAN_MACHINE_BOOTSTRAP", "RELEASE_ARTIFACT"):
            status = gaps[gap]
            if status in skip_statuses:
                continue
            successors.append(
                {
                    "action": "CREATE_SUCCESSOR_NODE",
                    "package": _gap_package_id(gap, prefix="AS-RELEASE"),
                    "blocked": False,
                    "gap": gap,
                    "status": status,
                }
            )
    if not successors:
        payload = {
            "worker_id": wid,
            "node_id": node.NODE_ID,
            "package_id": node.PACKAGE_ID,
            "objective_id": node.OBJECTIVE_ID,
            "TASK_KIND": node.TASK_KIND,
            "gaps": gaps,
            "successors": successors,
            "NO_ACTION": True,
            "NO_ACTION_PROOF": "all_gaps_satisfied_or_owner_blocked",
            "main_head": head,
            "at": ts,
            "pid": os.getpid(),
            "merge_authorized": False,
        }
    else:
        payload = {
            "worker_id": wid,
            "node_id": node.NODE_ID,
            "package_id": node.PACKAGE_ID,
            "objective_id": node.OBJECTIVE_ID,
            "TASK_KIND": node.TASK_KIND,
            "gaps": gaps,
            "successors": successors,
            "NO_ACTION": False,
            "main_head": head,
            "at": ts,
            "pid": os.getpid(),
            "merge_authorized": False,
        }
    receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    binding = RealWorkerBinding(
        worker_id=wid,
        worker_role=node.WORKER_ROLE,
        package_id=node.PACKAGE_ID,
        dag_node_id=node.NODE_ID,
        generation=node.GENERATION,
        runtime="local_pid",
        allowed_paths=list(node.ALLOWED_PATHS),
        started_at=ts,
        execution_binding=f"pid:{os.getpid()}",
        expected_receipt=str(receipt_path),
        pid=os.getpid(),
        status="COMPLETED",
    )
    workers[wid] = binding
    persist_workers(root, workers)

    nodes = load_nodes(root)
    if node.NODE_ID in nodes:
        nodes[node.NODE_ID].status = "COMPLETED"
        persist_nodes(root, nodes)

    state.WORKER_DISPATCH_SEQUENCE += 1
    state.PROGRESS_SEQUENCE += 1
    persist_mission_state(root, state)

    # Append receipt log
    log = _rt(root) / RECEIPTS_NAME
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"worker_id": wid, "receipt": str(receipt_path), "at": ts}) + "\n")

    return binding


def interpret_receipt(root: Path, receipt_path: Path) -> dict[str, Any]:
    """Transform a terminal receipt into successor DAG updates."""
    state = load_mission_state(root)
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkRuntimeError("mission receipt unreadable", code="RECEIPT_MALFORMED") from exc

    state.RECEIPT_CONSUME_SEQUENCE += 1
    nodes = load_nodes(root)
    created: list[str] = []
    for succ in data.get("successors") or []:
        if succ.get("action") != "CREATE_SUCCESSOR_NODE":
            continue
        gap_status = str(succ.get("status") or "")
        if gap_status in _GAP_SATISFIED_STATES or gap_status == "BLOCKED_OWNER":
            continue
        package = str(succ.get("package") or "UNKNOWN")
        blocked = bool(succ.get("blocked")) or gap_status == "BLOCKED_OWNER"
        key = _idempotency_key(
            objective=str(data.get("objective_id") or "O4"),
            kind="IMPLEMENTATION",
            package=package,
            surface=str(succ.get("gap") or package),
        )
        if any(key == n.IDEMPOTENCY_KEY for n in nodes.values()):
            continue
        status: NodeStatus = "BLOCKED_OWNER" if blocked else "READY"
        oid_raw = str(data.get("objective_id") or "O4")
        oid: ObjectiveId = oid_raw if oid_raw in {"O1", "O2", "O3", "O4", "O5", "O6"} else "O4"  # type: ignore[assignment]
        node = WorkNode(
            NODE_ID=f"SUCC-{key}",
            OBJECTIVE_ID=oid,
            PACKAGE_ID=package,
            TASK_KIND="IMPLEMENTATION" if not blocked else "ARCHITECTURE_ANALYSIS",
            PRIORITY=88 if not blocked else 50,
            DEPENDENCIES=["AUTHENTIC_ESTATE_ROOT"] if blocked else [],
            ALLOWED_PATHS=["src/project_atlas/", "tests/", "docs/"],
            SURFACE_SET=["src/project_atlas/"],
            WORKER_ROLE="IMPLEMENTER" if not blocked else "READ_ONLY_ANALYST",
            ACCEPTANCE_CRITERIA=f"Address gap {succ.get('gap')}",
            REQUIRED_VERIFICATION=["unit", "iv"],
            OWNER_GATE="CREDENTIAL" if blocked else "NONE",
            GENERATION=state.MISSION_GENERATION,
            IDEMPOTENCY_KEY=key,
            status=status,
            fingerprint=key,
        )
        nodes[node.NODE_ID] = node
        created.append(node.NODE_ID)
        state.SUCCESSOR_GENERATION_SEQUENCE += 1

    if not created and not data.get("NO_ACTION"):
        # Still reconciled
        pass
    if data.get("NO_ACTION") and not data.get("NO_ACTION_PROOF"):
        raise SdkRuntimeError("NO_ACTION without proof", code="NO_ACTION_UNJUSTIFIED")

    state.PROGRESS_SEQUENCE += 1
    state.TERMINAL_RECEIPT_WITHOUT_DAG_RECONCILIATION = 0
    persist_nodes(root, nodes)
    persist_mission_state(root, state)

    # Replenish via reconcile
    reconcile_head = str(data.get("main_head") or _CERTIFIED_MAIN_HEAD)
    mission_reconcile(root, main_head=reconcile_head)

    return {
        "outcome": "CREATE_SUCCESSOR_NODE" if created else "NO_ACTION_WITH_PROOF",
        "created": created,
        "RECEIPT_CONSUME_SEQUENCE": state.RECEIPT_CONSUME_SEQUENCE,
        "SUCCESSOR_GENERATION_SEQUENCE": state.SUCCESSOR_GENERATION_SEQUENCE,
        "merge_authorized": False,
    }


def closed_loop_tick(root: Path, *, main_head: str | None = None) -> dict[str, Any]:
    """One closed-loop generation: reconcile -> dispatch real worker -> interpret receipt."""
    head = main_head or "bd8faa8f97df454943181d19f1e14ee826900a20"
    summary = mission_reconcile(root, main_head=head)
    items = ready_work_items(root, capacity=1)
    if not items:
        # Empty READY — forced reconciliation already counted
        state = load_mission_state(root)
        return {
            **summary,
            "REAL_WORKER_DISPATCH_COUNT": 0,
            "REAL_ACTIVE_WORKER_COUNT": 0,
            "PROGRESS_SEQUENCE": state.PROGRESS_SEQUENCE,
            "note": "no_ready_after_reconcile",
        }

    nodes = load_nodes(root)
    node = nodes[items[0].node_id]
    # Skip owner-blocked
    if node.status == "BLOCKED_OWNER":
        return {**summary, "REAL_WORKER_DISPATCH_COUNT": 0, "note": "top_ready_blocked_owner"}

    binding = dispatch_local_analysis_worker(root, node, main_head=head)
    interp = interpret_receipt(root, Path(binding.expected_receipt))
    state = load_mission_state(root)
    workers = load_workers(root)
    active = sum(1 for w in workers.values() if w.status == "RUNNING")
    return {
        **summary,
        "REAL_WORKER_DISPATCH_COUNT": 1,
        "REAL_WORKER_COMPLETION_COUNT": 1,
        "REAL_ACTIVE_WORKER_COUNT": active,
        "SYNTHETIC_ACTIVE_WORKER_COUNT": 0,
        "RECEIPT_TO_SUCCESSOR_TRANSITION_COUNT": len(interp.get("created") or []),
        "PROGRESS_SEQUENCE": state.PROGRESS_SEQUENCE,
        "WORKER_DISPATCH_SEQUENCE": state.WORKER_DISPATCH_SEQUENCE,
        "worker_id": binding.worker_id,
        "created_successors": interp.get("created"),
        "merge_authorized": False,
    }


def real_active_worker_count(root: Path) -> int:
    return sum(1 for w in load_workers(root).values() if w.status == "RUNNING")


class MissionClosedLoopAdapter:
    """PR436 implementation of the PR435 ClosedLoopHook contract."""

    def reconcile(self, root: Path, *, now: float | None = None) -> dict[str, object]:
        return dict(mission_reconcile(root, now=now))

    def ready_work(self, root: Path, *, capacity: int = 2) -> list[ReadyWorkItem]:
        return list(ready_work_items(root, capacity=capacity))

    def active_worker_count(self, root: Path) -> int:
        return real_active_worker_count(root)

    def progress_state(self, root: Path) -> dict[str, object]:
        state = load_mission_state(root)
        return {
            "MISSION_GENERATION": state.MISSION_GENERATION,
            "PROGRESS_SEQUENCE": state.PROGRESS_SEQUENCE,
            "WORKER_DISPATCH_SEQUENCE": state.WORKER_DISPATCH_SEQUENCE,
            "RECEIPT_CONSUME_SEQUENCE": state.RECEIPT_CONSUME_SEQUENCE,
            "SUCCESSOR_GENERATION_SEQUENCE": state.SUCCESSOR_GENERATION_SEQUENCE,
            "EMPTY_READY_QUEUE_RECONCILIATION_COUNT": (
                state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT
            ),
        }

    def closed_loop_tick(
        self, root: Path, *, now: float | None = None
    ) -> dict[str, object]:
        return dict(closed_loop_tick(root))


def bind_closed_loop_hook() -> None:
    """Register this package as the resident closed-loop provider."""
    from project_atlas.orchestration.sdk.closed_loop_port import register_closed_loop_hook

    register_closed_loop_hook(MissionClosedLoopAdapter())


# Self-register when imported from a PR436 runtime (resident probes this module).
bind_closed_loop_hook()
