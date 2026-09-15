"""NO-REPLAY gate: interrupted work is never silently executed twice.

The supervisor's whole value depends on one promise: if it is killed and
restarted, it does not run again what may already have run. Every mechanism
for that promise existed in `recovery.classify_attempt` and was exercised only
incidentally, as a side effect of tests about other things. A clean-room gate
looked for it by name -- `git grep -E "no_replay|replay_guard" -- src tests` --
and found nothing, so the property was undefended against a refactor that
would quietly delete it. These tests defend it by name.

Two rules shape every assertion here.

FIRST: the observable is the LAUNCH COUNT, never a completion message. The
fixture worker appends one line per real process start, so the number of lines
in its target file is the number of times a child actually ran. A worker that
merely SAYS it finished is `claim-only` mode, and `test_a_completion_claim_is
_not_evidence_of_work` exists because trusting such a message is precisely how
a replay guard gets fooled: the supervisor must count what happened, not read
what it was told.

SECOND: each guard is paired with a mutation that removes it. A guard test
that cannot fail is decoration, so `test_MUTATION_*` reach into the exact
decision the guard depends on, break it, and assert the replay then happens.
If someone deletes the guard, the positive test fails; if someone weakens the
test, the mutation test fails. Both directions are covered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program import supervisor as supervisor_mod
from project_atlas.orchestration.program.enrollment import assign, enroll
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import AttemptPhase, ExecutionConfidence
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.recovery import RecoveryAction, RecoveryVerdict
from project_atlas.orchestration.program.store import load_state, persist_state
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")


def _profile(agent_id: str) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "permission_mode": "acceptEdits",
        "limits": {"max_seconds": 120, "max_attempts": 1},
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_FIXTURE_TARGET",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
        ],
        "adapter_options": {"argv": [sys.executable, str(FIXTURE_WORKER)]},
    }


def _task(task_id: str, out: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": task_id,
        "instruction": "fixture",
        "profile_ref": "implementer",
        "mutation_paths": [out],
        "surface_id": task_id,
        "surface_semantic": task_id.upper().replace("-", "_"),
        "capabilities_required": ["IMPLEMENT"],
        "acceptance": [
            {
                "check_id": "out",
                "kind": "FILE_EXISTS",
                "description": f"{out} exists",
                "path": out,
            }
        ],
    }


def _write_program(tmp_path: Path, workspace: Path, *, tasks: list[dict[str, Any]]) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "no-replay",
            "objective": "no-replay regression gate",
            "approved_by": "test",
            "approval_reference": "NO-REPLAY-GATE",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 12, "idle_sleep_seconds": 0.0},
            "tasks": tasks,
        },
        "profiles": {"implementer": _profile("program-placeholder")},
    }
    path = tmp_path / "program.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


class _Harness:
    """One program, one task, and a rebuildable supervisor over one state root.

    `restart()` builds a NEW supervisor against the SAME state root, which is
    what a real restart is. Reusing the object would keep in-memory state and
    test nothing.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.workspace = tmp_path / "ws"
        self.workspace.mkdir()
        self.registry = tmp_path / "registry"
        self.state_root = tmp_path / "state"
        self.out_name = "only.txt"
        self.program_path = _write_program(
            tmp_path, self.workspace, tasks=[_task("only", self.out_name)]
        )
        self.agent = enroll(
            self.registry,
            agent_id="real-implementer",
            role="implementer",
            adapter=AdapterKind.LOCAL_COMMAND,
            workspace_root=self.workspace,
            enrolled_by="test",
        )
        assign(
            self.registry,
            agent_id=self.agent.agent_id,
            program_path=self.program_path,
            assigned_by="test",
        )

    def restart(self) -> ProgramSupervisor:
        return ProgramSupervisor(
            load_program(self.program_path),
            state_root=self.state_root,
            enrolled_agents=(self.agent,),
            registry_root=self.registry,
        )

    # ---------------------------------------------------------- observables

    def launches_observed(self) -> int:
        """Real process starts, counted from the child's own side effect."""
        target = self.workspace / self.out_name
        if not target.is_file():
            return 0
        return len([line for line in target.read_text(encoding="utf-8").splitlines() if line])

    def launches_recorded(self) -> int:
        """What the supervisor's durable counter believes."""
        state = load_state(self.state_root)
        return 0 if state is None else state.total_launches

    def forget_completion(self) -> None:
        """Erase the durable record that the work already finished.

        This is the no-replay protection for COMPLETED work, removed. A
        finished task is CERTIFIED with its attempt counted; `select_next` only
        chooses READY nodes, so a CERTIFIED task is never a candidate. Put the
        node back to READY and the supervisor no longer knows the work was
        done.
        """
        state = load_state(self.state_root)
        assert state is not None
        for node in state.tasks.values():
            node.state = NodeState.READY
            node.attempts = 0
        persist_state(self.state_root, state)

    def arm_interrupted_attempt(self, *, confidence: ExecutionConfidence | None) -> None:
        """Leave an open, non-terminal attempt on a node that IS dispatchable.

        The protection here is layered, and isolating one layer is the whole
        point of this helper. A completed run leaves the node CERTIFIED, and
        that alone stops a replay -- so an interrupted-attempt test built on
        top of it passes no matter what the uncertainty guard does. An earlier
        version of this file made exactly that mistake, and its mutation
        controls caught it: the guard was mutated away and still no replay
        followed, because nothing was ever going to be dispatched.

        So the node is deliberately returned to READY. The completion guard is
        then GONE by construction, and the only thing standing between this
        attempt and a second launch is `classify_attempt` refusing to call an
        interrupted attempt safe. That is the guard under test, on its own.
        """
        state = load_state(self.state_root)
        assert state is not None
        attempt = next(iter(state.attempts.values()))
        attempt.phase = AttemptPhase.ADAPTER_INVOKED
        attempt.confidence = confidence
        attempt.ended_at = None
        for node in state.tasks.values():
            node.state = NodeState.READY
            node.attempts = 0
        persist_state(self.state_root, state)


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


# --------------------------------------------------------------------------
# 1. completed work is not re-dispatched
# --------------------------------------------------------------------------


def test_completed_work_is_not_redispatched_after_restart(tmp_path: Path) -> None:
    """A finished task stays finished across a restart.

    Asserted on the launch count from BOTH sides -- the child's own appends and
    the supervisor's durable counter -- because a guard that stops the counter
    but not the spawn, or the reverse, is still a replay.
    """
    h = _Harness(tmp_path)
    h.restart().start()

    assert h.launches_observed() == 1, "setup: the task should have run exactly once"
    assert h.launches_recorded() == 1

    h.restart().start()
    h.restart().start()

    assert h.launches_observed() == 1, (
        "completed work was RE-DISPATCHED after restart: the child ran again. "
        f"observed launches={h.launches_observed()}"
    )
    assert h.launches_recorded() == 1, (
        "the durable launch counter advanced after restart, so a second launch "
        "was recorded even if the child's own evidence did not show it"
    )


def test_MUTATION_forgetting_the_completion_record_causes_a_replay(
    tmp_path: Path,
) -> None:
    """Negative control for the test above, aimed at the guard that holds.

    The protection for finished work is NOT `classify_attempt`. An earlier
    version of this file assumed it was, mutated ALREADY_TERMINAL away, and no
    replay followed -- the control failed, correctly, and rewrote the test.
    Nor is it the selector alone: presenting a CERTIFIED node to `select_next`
    as READY gets caught one layer deeper by `_lease_for`, which refuses with
    NODE_NOT_READY. The protection is layered and it fails closed.

    What actually prevents the replay is the DURABLE RECORD that the work
    finished. Remove that -- the one thing every layer reads -- and the replay
    appears. That is what makes the positive test above load-bearing: it is
    measuring the durable completion state, and it would catch its loss.
    """
    h = _Harness(tmp_path)
    h.restart().start()
    assert h.launches_observed() == 1

    h.forget_completion()
    h.restart().start()

    assert h.launches_observed() > 1, (
        "the completion record was erased and STILL no replay occurred, so "
        "the positive test above is not measuring the completion guard -- "
        "something incidental is holding the line and the guard could be "
        "deleted without any test noticing"
    )


# --------------------------------------------------------------------------
# 2. uncertain / in-flight execution is not auto-replayed
# --------------------------------------------------------------------------


def test_uncertain_execution_is_not_auto_replayed(tmp_path: Path) -> None:
    """UNCERTAIN is the state where replay is most tempting and least safe.

    The attempt may have done all, some or none of its work; nothing on disk
    separates those. The only safe move is to stop and require a person. This
    asserts the supervisor does NOT launch again, and that the restart reports
    the attempt as needing reconciliation rather than quietly discarding it.
    """
    h = _Harness(tmp_path)
    h.restart().start()
    assert h.launches_observed() == 1

    h.arm_interrupted_attempt(confidence=ExecutionConfidence.UNCERTAIN)

    supervisor = h.restart()
    supervisor.start()

    assert h.launches_observed() == 1, (
        "an UNCERTAIN attempt was AUTO-REPLAYED: the child ran a second time "
        "for work that may already have been done"
    )

    reconcile = supervisor.reconcile()
    open_attempts = {
        item["attempt_id"]
        for item in reconcile["interrupted_attempts"]
        if item["recovery_action"] == "NEEDS_RECONCILIATION"
    }
    assert open_attempts, (
        "the UNCERTAIN attempt was neither replayed nor surfaced for "
        "reconciliation -- it was silently dropped, which loses the work"
    )


def test_in_flight_execution_is_not_replayed(tmp_path: Path) -> None:
    """A worker still running must not be joined by a second one.

    ADAPTER_INVOKED with a live launch record is the in-flight case. The
    supervisor must leave it alone, not start a competing child against the
    same mutation paths.
    """
    h = _Harness(tmp_path)
    h.restart().start()
    assert h.launches_observed() == 1

    h.arm_interrupted_attempt(confidence=None)

    h.restart().start()

    assert h.launches_observed() == 1, (
        "an in-flight attempt was replayed: a second child was started while "
        "the first was, as far as the durable record showed, still going"
    )


def test_MUTATION_treating_uncertain_as_safe_causes_a_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control for the two tests above.

    Mutate every non-terminal verdict to SAFE_TO_LAUNCH -- i.e. "no evidence
    it ever started" -- and the replay must appear.
    """
    h = _Harness(tmp_path)
    h.restart().start()
    assert h.launches_observed() == 1

    real = supervisor_mod.classify_attempt

    def mutated(attempt: Any, **kwargs: Any) -> RecoveryVerdict:
        verdict = real(attempt, **kwargs)
        if verdict.action is RecoveryAction.ALREADY_TERMINAL:
            return verdict
        return RecoveryVerdict(
            action=RecoveryAction.SAFE_TO_LAUNCH,
            confidence=None,
            reason="MUTANT: uncertainty treated as absence",
        )

    monkeypatch.setattr(supervisor_mod, "classify_attempt", mutated)

    h.arm_interrupted_attempt(confidence=ExecutionConfidence.UNCERTAIN)

    h.restart().start()

    assert h.launches_observed() > 1, (
        "UNCERTAIN was mutated to SAFE_TO_LAUNCH and no replay followed, so "
        "the uncertainty guard is not what the positive tests are measuring"
    )


# --------------------------------------------------------------------------
# 3. a completion message is not evidence
# --------------------------------------------------------------------------


def test_a_completion_claim_is_not_evidence_of_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`claim-only` says exactly what a successful worker says, and does nothing.

    This is the control for the whole file's measurement strategy. If the
    supervisor believed the message, this task would be recorded as done and
    the launch count would be irrelevant. It must instead observe that nothing
    was produced -- and the launch count is what stays trustworthy.
    """
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "claim-only")
    h = _Harness(tmp_path)
    h.restart().start()

    assert h.launches_observed() == 0, (
        "the fixture wrote its target in claim-only mode; this control cannot "
        "distinguish a claim from real work"
    )
    assert h.launches_recorded() == 1, (
        "the supervisor did not record the launch it actually made; the "
        "durable counter, not the worker's message, is the observable"
    )

    state = load_state(h.state_root)
    assert state is not None
    task_states = {task_id: node.state.value for task_id, node in state.tasks.items()}
    assert "COMPLETE" not in task_states.values(), (
        "a worker that only PRINTED a completion claim was recorded as "
        f"COMPLETE: {task_states}. The message was believed over the evidence."
    )
