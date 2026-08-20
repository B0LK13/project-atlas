"""Live PR target reconciliation + CI→IV/ADV ready items. No second governor."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.ci_observer import (
    CANONICAL_PR,
    CiObservation,
    PrHeadRef,
    classify_against_live_head,
    classify_failure,
    failure_identity,
    observe_exact_head_ci,
    persist_observation,
    refresh_pr_head,
)
from project_atlas.orchestration.sdk.event_log import append_event
from project_atlas.orchestration.sdk.host import write_host_identity
from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRole,
)
from project_atlas.orchestration.sdk.package_registry import (
    require_mutating_route,
    update_package_route_on_head_move,
)
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_PR as SECURITY_CANONICAL_PR,
)
from project_atlas.orchestration.sdk.security_gates import (
    GovernorLease,
    advance_high_water,
    reject_superseded_pr_mutation,
    suppress_stale_directive,
)

LIVE_DAG_NAME = "live-dag.json"
LEASES_NAME = "governor-leases.json"
CANONICAL_BRANCH = "feat/as-orch-continuation-broker-001"
TRUSTED_MAIN = "7e797468a2eca37c959920912b1fa264df4be638"
# Read-only IV/ADV may only touch evidence under the package surface.
IV_ADV_ALLOWED_PATHS: tuple[str, ...] = (
    "src/project_atlas/orchestration/sdk",
    "tests/unit",
    "docs/evidence",
    ".atlas/orchestration/sdk-runtime",
)

RefreshFn = Callable[[], PrHeadRef | None]
ObserveFn = Callable[[str], CiObservation]


class LiveDagState(BaseModel):
    """Persisted live DAG binding. Not certification. Not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    dag_generation: int = Field(default=84, ge=0, le=1_000_000)
    bound_head: str | None = None
    bound_tree: str | None = None
    ci_run_id: str | None = None
    ci_status: str = "UNKNOWN"
    previous_head: str | None = None
    previous_ci_run_id: str | None = None
    previous_ci_classification: str | None = None
    iv_dispatched: bool = False
    adv_dispatched: bool = False
    remediation_dispatched: bool = False
    remediation_failure_ids: list[str] = Field(default_factory=list)
    cloud_runtime_audit_pass: bool = False
    material_transitions: int = 0
    target_move_detected: bool = False
    new_head_adopted: bool = False
    new_ci_adopted: bool = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def live_dag_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / LIVE_DAG_NAME


def load_live_dag(root: Path) -> LiveDagState:
    path = live_dag_path(root)
    if path.is_file():
        try:
            return LiveDagState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    state = LiveDagState()
    observer = root / STATE_DIR_RELATIVE / "ci-observer.json"
    if observer.is_file():
        try:
            payload = json.loads(observer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            head = str(payload.get("head_sha") or "")
            if len(head) == 40:
                state.bound_head = head
                state.ci_run_id = str(payload.get("run_id") or "") or None
                state.ci_status = str(payload.get("status") or "UNKNOWN")
    return state


def persist_live_dag(root: Path, state: LiveDagState) -> Path:
    path = live_dag_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _iv_prompt(head: str, tree: str | None) -> str:
    tree_txt = tree or "UNKNOWN"
    return (
        "READ-ONLY independent verification for AS-ORCH-CONTINUATION-BROKER-001 "
        f"on PR #429 head {head} tree {tree_txt}. "
        "Use read/grep/glob/ls only. Do not edit, commit, push, or merge. "
        "Confirm the package ID and that this exact head/tree is the bound candidate. "
        "Return PASS or FAIL with evidence paths only."
    )


def _adv_prompt(head: str, tree: str | None) -> str:
    tree_txt = tree or "UNKNOWN"
    return (
        "READ-ONLY security review for AS-ORCH-CONTINUATION-BROKER-001 "
        f"on PR #429 head {head} tree {tree_txt}. "
        "Cover SDK agent/run replay, idempotency collision, bridge workspace confusion, "
        "cross-worktree resume, foreign project agent, stale head run, duplicate run/"
        "worker, result replay, OWNER_REQUIRED injection, prompt injection, tool policy "
        "escape, direct main push attempt, force push attempt, supervisor double start, "
        "supervisor state rollback, SDK bridge crash, CI target move, stale CI cancelled, "
        "and stop-hook fallback replay. "
        "Do not edit, commit, push, or merge. NEW_P0 and NEW_P1 must be reported."
    )


def _remediator_prompt(head: str, run_id: str | None) -> str:
    return (
        "BOUNDED remediator for AS-ORCH-CONTINUATION-BROKER-001 on PR #429 only. "
        f"Candidate head {head}. Exact-head CI run {run_id or 'unknown'} failed. "
        "Classify infrastructure vs candidate defect. If candidate defect, patch #429 "
        "only on feat/as-orch-continuation-broker-001. Do not merge. Do not force-push. "
        "Do not create another PR. Do not push main."
    )


class LiveDagController:
    """Refresh PR head, classify stale CI, emit events, yield ready workers."""

    def __init__(
        self,
        root: Path,
        *,
        pr_number: int = CANONICAL_PR,
        supervisor_pid: int | None = None,
        refresh: RefreshFn | None = None,
        observe: ObserveFn | None = None,
        real_sdk_backend: bool = False,
        worker_dispatch_enabled: bool | None = None,
    ) -> None:
        self.root = root
        self.pr_number = pr_number
        self.supervisor_pid = supervisor_pid
        self._refresh = refresh or (
            lambda: refresh_pr_head(pr_number=pr_number)
        )
        self._observe = observe or (lambda sha: observe_exact_head_ci(head_sha=sha))
        # D-088: CLI authentic worker may dispatch; do not require official SDK.
        self.real_sdk_backend = real_sdk_backend
        self.worker_dispatch_enabled = (
            real_sdk_backend if worker_dispatch_enabled is None else worker_dispatch_enabled
        )
        self.state = load_live_dag(root)
        self._leases: dict[str, GovernorLease] = {}

    def tick(self) -> tuple[LiveDagState, list[ReadyWorkItem]]:
        live = self._refresh()
        state = self.state
        if live is None:
            if state.bound_head:
                obs = self._observe(state.bound_head)
                persist_observation(self.root, obs)
                state.ci_status = obs.status
                state.ci_run_id = obs.run_id
                persist_live_dag(self.root, state)
            return state, []

        if state.bound_head is None:
            self._adopt_initial(live)
        elif live.head_sha != state.bound_head:
            self._adopt_moved_head(live)

        assert self.state.bound_head is not None
        obs = self._observe(self.state.bound_head)
        classified = classify_against_live_head(exact=obs, live_head=live.head_sha)
        classified = classify_failure(
            observation=classified,
            live_head=live.head_sha,
            current_generation=self.state.dag_generation,
        )
        persist_observation(self.root, classified)
        self.state.ci_status = classified.status
        self.state.ci_run_id = classified.run_id
        if classified.status in {"PASS", "FAIL", "CANCELLED"}:
            event_name: Literal["CI_TERMINAL", "CI_JOB_SIGNAL"] = (
                "CI_TERMINAL"
                if (classified.run_status or "") == "completed"
                else "CI_JOB_SIGNAL"
            )
            detail: str = classified.status
            if classified.failed_required_job_id:
                detail = f"{classified.status}:{classified.failed_required_job_id}"
            append_event(
                self.root,
                event_name,
                dag_generation=self.state.dag_generation,
                head=self.state.bound_head,
                tree=self.state.bound_tree,
                run_id=classified.run_id,
                detail=detail,
            )
        persist_live_dag(self.root, self.state)
        if self.supervisor_pid is not None and self.state.bound_head:
            write_host_identity(
                self.root,
                pid=self.supervisor_pid,
                backend="LOCAL_SDK" if self.real_sdk_backend else "OBSERVER",
                package_head=self.state.bound_head,
                worktree=str(self.root),
            )
        return self.state, self._ready_items()

    def _adopt_initial(self, live: PrHeadRef) -> None:
        append_event(
            self.root,
            "TARGET_HEAD_OBSERVED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
        )
        self.state.bound_head = live.head_sha
        self.state.bound_tree = live.tree_sha
        self.state.new_head_adopted = True
        update_package_route_on_head_move(
            self.root,
            head=live.head_sha,
            tree=live.tree_sha,
            dag_generation=self.state.dag_generation,
        )
        append_event(
            self.root,
            "NEW_HEAD_ADOPTED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
        )
        obs = self._observe(live.head_sha)
        persist_observation(self.root, obs)
        self.state.ci_run_id = obs.run_id
        self.state.ci_status = obs.status
        self.state.new_ci_adopted = True
        append_event(
            self.root,
            "NEW_CI_ADOPTED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
            run_id=obs.run_id,
        )

    def _adopt_moved_head(self, live: PrHeadRef) -> None:
        old_head = self.state.bound_head
        old_run = self.state.ci_run_id
        old_obs = self._observe(old_head) if old_head else None
        append_event(
            self.root,
            "TARGET_HEAD_OBSERVED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
            detail=f"previous={old_head}",
        )
        if old_obs is not None and old_obs.conclusion == "cancelled":
            append_event(
                self.root,
                "OLD_CI_CANCELLED",
                dag_generation=self.state.dag_generation,
                head=old_head,
                run_id=old_obs.run_id,
            )
        append_event(
            self.root,
            "OLD_CI_SUPERSEDED",
            dag_generation=self.state.dag_generation,
            head=old_head,
            run_id=old_run or (old_obs.run_id if old_obs else None),
            detail="STALE_SUPERSEDED",
        )
        self.state.previous_head = old_head
        self.state.previous_ci_run_id = old_run or (old_obs.run_id if old_obs else None)
        self.state.previous_ci_classification = "STALE_SUPERSEDED"
        self.state.dag_generation += 1
        self.state.bound_head = live.head_sha
        self.state.bound_tree = live.tree_sha
        self.state.iv_dispatched = False
        self.state.adv_dispatched = False
        self.state.remediation_dispatched = False
        self.state.cloud_runtime_audit_pass = False
        self.state.target_move_detected = True
        self.state.new_head_adopted = True
        self.state.material_transitions += 1
        update_package_route_on_head_move(
            self.root,
            head=live.head_sha,
            tree=live.tree_sha,
            dag_generation=self.state.dag_generation,
        )
        append_event(
            self.root,
            "NEW_HEAD_ADOPTED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
        )
        new_obs = self._observe(live.head_sha)
        persist_observation(self.root, new_obs)
        self.state.ci_run_id = new_obs.run_id
        self.state.ci_status = new_obs.status
        self.state.new_ci_adopted = True
        self.state.material_transitions += 1
        append_event(
            self.root,
            "NEW_CI_ADOPTED",
            dag_generation=self.state.dag_generation,
            head=live.head_sha,
            tree=live.tree_sha,
            run_id=new_obs.run_id,
        )

    def _mint_lease(self, *, role: AgentRole, node_id: str, mutating: bool) -> GovernorLease:
        reject_superseded_pr_mutation(target_pr=self.pr_number)
        if self.pr_number != SECURITY_CANONICAL_PR:
            raise ValueError("non-canonical PR cannot mint lease")
        assert self.state.bound_head is not None
        stale = suppress_stale_directive(
            directive_pr=self.pr_number,
            directive_head=self.state.bound_head,
            live_pr=SECURITY_CANONICAL_PR,
            live_head=self.state.bound_head,
        )
        if stale:
            raise ValueError(f"stale directive suppressed: {stale}")
        if mutating:
            require_mutating_route(
                self.root,
                target_pr=self.pr_number,
                branch=CANONICAL_BRANCH,
                head=self.state.bound_head,
                dag_generation=self.state.dag_generation,
            )
        lease = GovernorLease(
            lease_id=f"lease-{node_id.lower()}-{self.state.dag_generation}",
            package_id=PACKAGE_ID,
            canonical_pr=SECURITY_CANONICAL_PR,
            branch=CANONICAL_BRANCH,
            role=role,
            dag_generation=self.state.dag_generation,
            allowed_paths=IV_ADV_ALLOWED_PATHS
            if not mutating
            else (
                "src/project_atlas/orchestration/sdk",
                "tests/unit",
                "scripts",
            ),
            worktree=str(self.root),
            candidate_head=self.state.bound_head,
            candidate_tree=self.state.bound_tree,
            active=True,
            expired=False,
            mutation_authorized=mutating,
        )
        self._leases[lease.lease_id] = lease
        path = self.root / STATE_DIR_RELATIVE / LEASES_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.model_dump(mode="json") for k, v in self._leases.items()}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return lease

    def _failure_id_for_current(self) -> str | None:
        path = self.root / STATE_DIR_RELATIVE / "ci-observer.json"
        if not path.is_file():
            return None
        try:
            obs = CiObservation.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (
            obs.status != "FAIL"
            or not obs.run_id
            or not obs.failed_required_job_id
            or not obs.failure_digest
            or not self.state.bound_head
        ):
            # Workflow-level FAIL without job id still needs a stable identity.
            if obs.status == "FAIL" and obs.run_id and self.state.bound_head:
                return failure_identity(
                    head=self.state.bound_head,
                    run_id=obs.run_id,
                    job_id=obs.failed_required_job_id or "workflow",
                    failure_digest=obs.failure_digest or obs.run_id,
                )
            return None
        return failure_identity(
            head=self.state.bound_head,
            run_id=obs.run_id,
            job_id=obs.failed_required_job_id,
            failure_digest=obs.failure_digest,
        )

    def _ready_items(self) -> list[ReadyWorkItem]:
        state = self.state
        if not state.bound_head or not self.worker_dispatch_enabled:
            return []
        items: list[ReadyWorkItem] = []
        if state.ci_status == "PASS" and state.cloud_runtime_audit_pass:
            if not state.iv_dispatched:
                lease = self._mint_lease(
                    role=AgentRole.INDEPENDENT_VERIFIER,
                    node_id="IV-LIVE",
                    mutating=False,
                )
                items.append(
                    ReadyWorkItem(
                        role=AgentRole.INDEPENDENT_VERIFIER,
                        package_id=PACKAGE_ID,
                        node_id="IV-LIVE",
                        cycle_id=f"IV-{state.bound_head[:12]}",
                        dag_generation=state.dag_generation,
                        lease_id=lease.lease_id,
                        base_main=TRUSTED_MAIN,
                        branch=CANONICAL_BRANCH,
                        candidate_head=state.bound_head,
                        candidate_tree=state.bound_tree,
                        prompt=_iv_prompt(state.bound_head, state.bound_tree),
                        critical_path_score=100,
                    )
                )
            if not state.adv_dispatched:
                lease = self._mint_lease(
                    role=AgentRole.SECURITY_REVIEWER,
                    node_id="ADV-LIVE",
                    mutating=False,
                )
                items.append(
                    ReadyWorkItem(
                        role=AgentRole.SECURITY_REVIEWER,
                        package_id=PACKAGE_ID,
                        node_id="ADV-LIVE",
                        cycle_id=f"ADV-{state.bound_head[:12]}",
                        dag_generation=state.dag_generation,
                        lease_id=lease.lease_id,
                        base_main=TRUSTED_MAIN,
                        branch=CANONICAL_BRANCH,
                        candidate_head=state.bound_head,
                        candidate_tree=state.bound_tree,
                        prompt=_adv_prompt(state.bound_head, state.bound_tree),
                        critical_path_score=100,
                    )
                )
        elif state.ci_status == "FAIL" and not state.remediation_dispatched:
            fid = self._failure_id_for_current()
            if fid and fid in state.remediation_failure_ids:
                return items
            # Only candidate defects remediates; stale/infra do not.
            path = self.root / STATE_DIR_RELATIVE / "ci-observer.json"
            failure_class = "CANDIDATE_DEFECT"
            if path.is_file():
                try:
                    obs = CiObservation.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                    failure_class = obs.failure_class
                except (OSError, ValueError):
                    pass
            if failure_class != "CANDIDATE_DEFECT":
                return items
            if fid:
                state.remediation_failure_ids.append(fid)
            lease = self._mint_lease(
                role=AgentRole.REMEDIATOR,
                node_id="REMEDIATE-LIVE",
                mutating=True,
            )
            items.append(
                ReadyWorkItem(
                    role=AgentRole.REMEDIATOR,
                    package_id=PACKAGE_ID,
                    node_id="REMEDIATE-LIVE",
                    cycle_id=f"REM-{state.bound_head[:12]}",
                    dag_generation=state.dag_generation,
                    lease_id=lease.lease_id,
                    base_main=TRUSTED_MAIN,
                    branch=CANONICAL_BRANCH,
                    candidate_head=state.bound_head,
                    candidate_tree=state.bound_tree,
                    prompt=_remediator_prompt(state.bound_head, state.ci_run_id),
                    critical_path_score=200,
                )
            )
        return items

    def mark_dispatched(self, node_id: str) -> None:
        if node_id == "IV-LIVE":
            self.state.iv_dispatched = True
            append_event(
                self.root,
                "IV_DISPATCHED",
                dag_generation=self.state.dag_generation,
                head=self.state.bound_head,
                tree=self.state.bound_tree,
                node=node_id,
            )
            self.state.material_transitions += 1
            advance_high_water(
                self.root,
                dag_generation=self.state.dag_generation,
                event_sequence=self.state.material_transitions,
            )
        elif node_id == "ADV-LIVE":
            self.state.adv_dispatched = True
            append_event(
                self.root,
                "ADV_DISPATCHED",
                dag_generation=self.state.dag_generation,
                head=self.state.bound_head,
                tree=self.state.bound_tree,
                node=node_id,
            )
            self.state.material_transitions += 1
            advance_high_water(
                self.root,
                dag_generation=self.state.dag_generation,
                event_sequence=self.state.material_transitions,
            )
        elif node_id == "REMEDIATE-LIVE":
            self.state.remediation_dispatched = True
            append_event(
                self.root,
                "REMEDIATION_DISPATCHED",
                dag_generation=self.state.dag_generation,
                head=self.state.bound_head,
                tree=self.state.bound_tree,
                node=node_id,
            )
            self.state.material_transitions += 1
            advance_high_water(
                self.root,
                dag_generation=self.state.dag_generation,
                event_sequence=self.state.material_transitions,
            )
        persist_live_dag(self.root, self.state)
