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
from project_atlas.orchestration.sdk.scheduler import ReadyWorkItem

LIVE_DAG_NAME = "live-dag.json"
CANONICAL_BRANCH = "feat/as-orch-continuation-broker-001"
TRUSTED_MAIN = "7e797468a2eca37c959920912b1fa264df4be638"

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
    ) -> None:
        self.root = root
        self.pr_number = pr_number
        self.supervisor_pid = supervisor_pid
        self._refresh = refresh or (
            lambda: refresh_pr_head(pr_number=pr_number)
        )
        self._observe = observe or (lambda sha: observe_exact_head_ci(head_sha=sha))
        self.real_sdk_backend = real_sdk_backend
        self.state = load_live_dag(root)

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
        persist_observation(self.root, classified)
        self.state.ci_status = classified.status
        self.state.ci_run_id = classified.run_id
        if classified.status in {"PASS", "FAIL", "CANCELLED"}:
            append_event(
                self.root,
                "CI_TERMINAL",
                dag_generation=self.state.dag_generation,
                head=self.state.bound_head,
                tree=self.state.bound_tree,
                run_id=classified.run_id,
                detail=classified.status,
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
        self.state.target_move_detected = True
        self.state.new_head_adopted = True
        self.state.material_transitions += 1
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

    def _ready_items(self) -> list[ReadyWorkItem]:
        state = self.state
        if not state.bound_head or not self.real_sdk_backend:
            return []
        items: list[ReadyWorkItem] = []
        if state.ci_status == "PASS":
            if not state.iv_dispatched:
                items.append(
                    ReadyWorkItem(
                        role=AgentRole.INDEPENDENT_VERIFIER,
                        package_id=PACKAGE_ID,
                        node_id="IV-LIVE",
                        cycle_id=f"IV-{state.bound_head[:12]}",
                        dag_generation=state.dag_generation,
                        base_main=TRUSTED_MAIN,
                        branch=CANONICAL_BRANCH,
                        candidate_head=state.bound_head,
                        candidate_tree=state.bound_tree,
                        prompt=_iv_prompt(state.bound_head, state.bound_tree),
                    )
                )
            if not state.adv_dispatched:
                items.append(
                    ReadyWorkItem(
                        role=AgentRole.SECURITY_REVIEWER,
                        package_id=PACKAGE_ID,
                        node_id="ADV-LIVE",
                        cycle_id=f"ADV-{state.bound_head[:12]}",
                        dag_generation=state.dag_generation,
                        base_main=TRUSTED_MAIN,
                        branch=CANONICAL_BRANCH,
                        candidate_head=state.bound_head,
                        candidate_tree=state.bound_tree,
                        prompt=_adv_prompt(state.bound_head, state.bound_tree),
                    )
                )
        elif state.ci_status == "FAIL" and not state.remediation_dispatched:
            items.append(
                ReadyWorkItem(
                    role=AgentRole.REMEDIATOR,
                    package_id=PACKAGE_ID,
                    node_id="REMEDIATE-LIVE",
                    cycle_id=f"REM-{state.bound_head[:12]}",
                    dag_generation=state.dag_generation,
                    base_main=TRUSTED_MAIN,
                    branch=CANONICAL_BRANCH,
                    candidate_head=state.bound_head,
                    candidate_tree=state.bound_tree,
                    prompt=_remediator_prompt(state.bound_head, state.ci_run_id),
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
        persist_live_dag(self.root, self.state)
