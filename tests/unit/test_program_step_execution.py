"""Execution-level continuation proofs; bounded zero-model workers only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program import approved_queue
from project_atlas.orchestration.program.continuation import (
    CheckpointPolicy,
    ContinuationCheckpoint,
    ExecutionIdentity,
    ReplayClass,
    persist_checkpoint,
    persist_envelope,
)
from project_atlas.orchestration.program.continuation_projection import materialise_envelopes
from project_atlas.orchestration.program.enrollment import assign, enroll
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.resident import ResidentDispatcher


def prepare(
    tmp_path: Path,
    *,
    steps: bool = False,
    configure: Callable[[dict[str, Any]], None] | None = None,
) -> ResidentDispatcher:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    argv = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path('SECOND.txt').write_text('SECOND\\n')",
    ]
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "steps",
            "objective": "execute remaining work",
            "approved_by": "fixture-operator",
            "approval_reference": "DURABLE-CONTINUATION",
            "workspace_root": str(workspace),
            "allow_unversioned_fixture": True,
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 20, "idle_sleep_seconds": 0.0},
            "tasks": [
                {
                    "task_id": "work",
                    "title": "work",
                    "instruction": "continue",
                    "profile_ref": "impl",
                    "mutation_paths": ["FIRST.txt", "SECOND.txt"],
                    "surface_id": "work",
                    "surface_semantic": "WORK",
                    "acceptance": [
                        {
                            "check_id": "second",
                            "kind": "FILE_EXISTS",
                            "description": "remaining step ran",
                            "path": "SECOND.txt",
                        }
                    ],
                }
            ],
        },
        "profiles": {
            "impl": {
                "agent_id": "step-worker",
                "adapter": "local-command",
                "credential": "NOT_APPLICABLE",
                "capabilities": ["IMPLEMENT"],
                "adapter_options": {"argv": argv},
            }
        },
    }
    path = tmp_path / "program.json"
    if steps:
        payload["program"]["tasks"][0]["execution_steps"] = [
            {
                "step_id": name,
                "argv": [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; p=Path('{name}.txt'); "
                    f"p.open('a').write('{name}\\n')",
                ],
                "acceptance": [
                    {
                        "check_id": name.lower(),
                        "kind": "FILE_EXISTS",
                        "description": "observed step output",
                        "path": f"{name}.txt",
                    }
                ],
            }
            for name in ("FIRST", "SECOND")
        ]
    if configure is not None:
        configure(payload)
    path.write_text(json.dumps(payload))
    registry, queue = tmp_path / "registry", tmp_path / "queue"
    enroll(
        registry,
        agent_id="step-worker",
        role="impl",
        adapter="local-command",
        workspace_root=workspace,
        enrolled_by="fixture-operator",
    )
    assign(
        registry,
        agent_id="step-worker",
        program_path=path,
        assigned_by="fixture-operator",
        governed_root=tmp_path,
    )
    if "verifier" in payload["profiles"]:
        enroll(
            registry,
            agent_id="fixture-verifier",
            role="verifier",
            adapter="local-command",
            workspace_root=workspace,
            enrolled_by="fixture-operator",
        )
        assign(
            registry,
            agent_id="fixture-verifier",
            program_path=path,
            assigned_by="fixture-operator",
            governed_root=tmp_path,
        )
    approved_queue.admit(
        queue,
        program_path=path,
        program_id="steps",
        state_root=tmp_path,
        admitted_by="fixture-operator",
        reference="bounded fixture",
        governed_root=tmp_path,
    )
    return ResidentDispatcher(
        root=tmp_path,
        queue_root=queue,
        checkout=Path.cwd(),
        registry_root=registry,
        governed_root=tmp_path,
    )


def test_unbound_checkpoint_remains_unlaunchable(tmp_path: Path) -> None:
    """The historical RED was not a valid new protocol: no approved step binding."""
    dispatcher = prepare(tmp_path)
    workspace = tmp_path / "workspace"
    (workspace / "FIRST.txt").write_text("FIRST\n")
    path = tmp_path / "program.json"
    loaded = load_program(path, governed_root=tmp_path)
    envelope = materialise_envelopes(
        loaded, tmp_path, candidate_head="0" * 40, candidate_tree="0" * 40
    )[0].model_copy(
        update={
            "replay_class": ReplayClass.CHECKPOINT_RESUMABLE,
            "checkpoint_policy": CheckpointPolicy(steps=("FIRST", "SECOND")),
        }
    )
    persist_envelope(tmp_path, envelope)
    persist_checkpoint(
        tmp_path,
        ContinuationCheckpoint(
            identity=ExecutionIdentity(
                task_id="work",
                worker_id="step-worker",
                session_id="fixture-session",
                attempt_id="fixture-first",
            ),
            envelope_digest=envelope.digest(),
            program_id="steps",
            sequence=1,
            last_completed_step="FIRST",
            next_action="execute SECOND",
            worktree_path=str(workspace),
            git_head="0" * 40,
            git_tree="0" * 40,
            replay_class=ReplayClass.CHECKPOINT_RESUMABLE,
        ),
    )
    result = dispatcher.tick()
    assert result.launched == 0
    assert not (workspace / "SECOND.txt").exists()
    assert (workspace / "FIRST.txt").read_text() == "FIRST\n"


def test_real_approved_steps_execute_once_and_seal(tmp_path: Path) -> None:
    from project_atlas.orchestration.program.continuation import load_checkpoint

    dispatcher = prepare(tmp_path, steps=True)
    result = dispatcher.tick()
    assert result.launched == 2, repr(result)
    assert result.report is not None and result.report.complete, repr(result)
    for step in ("FIRST", "SECOND"):
        assert (tmp_path / "workspace" / f"{step}.txt").read_text() == f"{step}\n"
    cp = load_checkpoint(tmp_path, "work")
    assert cp is not None and cp.terminal and cp.last_completed_step == "SECOND"
    assert len(cp.commands) == 2 and all(c.exit_status == 0 for c in cp.commands)
    assert cp.consumed_budget.launches == cp.consumed_budget.attempts == 2
    assert dispatcher.tick().launched == dispatcher.tick().launched == 0


def pause_after_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ResidentDispatcher:
    from project_atlas.orchestration.program import control, supervisor

    dispatcher = prepare(tmp_path, steps=True)
    original = supervisor.append_event

    def pause_on_boundary(root: Path, kind: str, body: dict[str, object]) -> object:
        result = original(root, kind, body)
        if kind == "STEP_COMPLETED" and body["step_id"] == "FIRST":
            control.pause(root, requested_by="fixture-operator")
        return result

    monkeypatch.setattr(supervisor, "append_event", pause_on_boundary)
    first = dispatcher.tick()
    assert first.launched == 1, repr(first)
    assert (tmp_path / "workspace/FIRST.txt").read_text() == "FIRST\n"
    assert not (tmp_path / "workspace/SECOND.txt").exists()
    monkeypatch.setattr(supervisor, "append_event", original)
    return dispatcher


def test_pause_resume_continues_same_task_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from project_atlas.orchestration.program import control

    dispatcher = pause_after_first(tmp_path, monkeypatch)
    assert dispatcher.tick().launched == 0
    control.resume(tmp_path, requested_by="fixture-operator")
    result = dispatcher.tick()
    assert result.launched == 1 and result.report is not None and result.report.complete, repr(
        result
    )
    assert (tmp_path / "workspace/FIRST.txt").read_text() == "FIRST\n"
    assert (tmp_path / "workspace/SECOND.txt").read_text() == "SECOND\n"


@pytest.mark.parametrize("fault", ["identity", "uncertainty", "budget", "last_step"])
def test_unsafe_step_boundary_never_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from project_atlas.orchestration.program import control
    from project_atlas.orchestration.program.continuation import load_checkpoint

    dispatcher = pause_after_first(tmp_path, monkeypatch)
    cp = load_checkpoint(tmp_path, "work")
    assert cp is not None
    changes: dict[str, object] = {"sequence": cp.sequence + 1}
    if fault == "identity":
        changes.update(process_pid=None, process_start_identity=None)
    elif fault == "uncertainty":
        changes["uncertainty"] = ("fixture injects unknown external effect",)
    elif fault == "budget":
        changes["consumed_budget"] = cp.consumed_budget.model_copy(update={"wall_seconds": 86400.0})
    else:
        changes["last_completed_step"] = "SECOND"
    persist_checkpoint(tmp_path, cp.model_copy(update=changes))
    control.resume(tmp_path, requested_by="fixture-operator")
    result = dispatcher.tick()
    assert result.launched == 0, repr(result)
    assert not (tmp_path / "workspace/SECOND.txt").exists()
    assert (tmp_path / "workspace/FIRST.txt").read_text() == "FIRST\n"


def test_program_authority_is_reloaded_between_step_dispatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from project_atlas.orchestration.program import supervisor

    dispatcher = prepare(tmp_path, steps=True)
    original = supervisor.append_event

    def change_approval(root: Path, kind: str, body: dict[str, object]) -> object:
        result = original(root, kind, body)
        if kind == "STEP_COMPLETED" and body["step_id"] == "FIRST":
            path = root / "program.json"
            payload = json.loads(path.read_text())
            payload["program"]["approval_reference"] = "fixture operator withdrew original approval"
            path.write_text(json.dumps(payload))
        return result

    monkeypatch.setattr(supervisor, "append_event", change_approval)
    result = dispatcher.tick()
    assert result.launched == 1, repr(result)
    assert not (tmp_path / "workspace/SECOND.txt").exists()


def test_declared_fallback_actually_executes_after_hard_block(tmp_path: Path) -> None:
    from project_atlas.orchestration.program.continuation import load_envelope
    from project_atlas.orchestration.program.continuation_projection import materialise_envelopes

    def configure(payload: dict[str, Any]) -> None:
        task = payload["program"]["tasks"][0]
        fallback = dict(
            task,
            task_id="fallback",
            title="authorized fallback",
            surface_id="fallback",
            surface_semantic="FALLBACK",
            mutation_paths=["fallback.txt"],
            acceptance=[
                {
                    "check_id": "fallback",
                    "kind": "FILE_EXISTS",
                    "path": "fallback.txt",
                    "description": "fallback ran",
                }
            ],
        )
        payload["program"]["tasks"].append(fallback)
        payload["profiles"]["impl"]["adapter_options"]["argv"] = [
            sys.executable,
            "-c",
            "import os,sys; from pathlib import Path; t=os.environ['ATLAS_PROGRAM_TASK']; "
            "Path(t+'.txt').open('a').write(t+'\\n'); "
            "sys.stderr.write('quota exhausted' if t=='work' else ''); "
            "sys.exit(23 if t=='work' else 0)",
        ]

    dispatcher = prepare(tmp_path, configure=configure)
    loaded = load_program(tmp_path / "program.json", governed_root=tmp_path)
    materialise_envelopes(loaded, tmp_path, candidate_head="0" * 40, candidate_tree="0" * 40)
    envelope = load_envelope(tmp_path, "work")
    assert envelope is not None
    persist_envelope(tmp_path, envelope.model_copy(update={"fallback_task_ids": ("fallback",)}))
    first = dispatcher.tick()
    second = dispatcher.tick()
    assert (tmp_path / "workspace/fallback.txt").exists(), (repr(first), repr(second))
    assert (tmp_path / "workspace/work.txt").read_text() == "work\n"
    assert (tmp_path / "workspace/fallback.txt").read_text() == "fallback\n"
    from project_atlas.orchestration.autonomy.lease_projection import active_rows, load_projection
    from project_atlas.orchestration.program.decisions import list_decisions
    from project_atlas.orchestration.program.store import state_dir

    assert len(list_decisions(tmp_path)) == 1
    assert active_rows(load_projection(state_dir(tmp_path))) == ()
    assert dispatcher.tick().launched == 0


def test_next_step_timeout_uses_remaining_observed_wall_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from project_atlas.orchestration.program import supervisor
    from project_atlas.orchestration.program.continuation import load_checkpoint

    def configure(payload: dict[str, Any]) -> None:
        payload["program"]["limits"]["max_task_seconds"] = 1
        first = payload["program"]["tasks"][0]["execution_steps"][0]
        first["argv"][-1] = "import time; time.sleep(0.15); " + first["argv"][-1]

    dispatcher = prepare(tmp_path, steps=True, configure=configure)
    original = supervisor.ProgramSupervisor._build_request
    observed = []

    def observe_request(self: Any, **kwargs: Any) -> Any:
        request = original(self, **kwargs)
        cp = load_checkpoint(self.root, "work")
        if kwargs["attempt"].step_id == "SECOND":
            assert cp is not None
            observed.append((request.timeout_seconds, cp.consumed_budget.wall_seconds))
        return request

    monkeypatch.setattr(supervisor.ProgramSupervisor, "_build_request", observe_request)
    result = dispatcher.tick()
    assert result.launched == 2, repr(result)
    assert len(observed) == 1
    timeout, consumed = observed[0]
    assert consumed >= 0.15
    assert 0 < timeout <= 1.0 - consumed


@pytest.mark.parametrize("cut_mode", ["cut", "cut-final"])
def test_abrupt_controller_exit_resumes_only_next_step_in_fresh_interpreter(
    tmp_path: Path,
    cut_mode: str,
) -> None:
    prepare(tmp_path, steps=True)
    controller = Path(__file__).with_name("_step_execution_controller.py")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    observations = []
    for mode in (cut_mode, "resume", "resume", "resume"):
        result = subprocess.run(
            [sys.executable, str(controller), str(tmp_path), str(Path.cwd()), mode],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        observations.append(
            {"exit_status": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        )
        (tmp_path / "controller-observations.json").write_text(json.dumps(observations, indent=2))
        if mode == cut_mode:
            assert result.returncode == 91, observations
            assert (tmp_path / "workspace/SECOND.txt").exists() is (cut_mode == "cut-final")
        else:
            assert result.returncode == 0, observations
    for step in ("FIRST", "SECOND"):
        assert (tmp_path / "workspace" / f"{step}.txt").read_text() == f"{step}\n", observations
    expected = [1, 0, 0] if cut_mode == "cut" else [0, 0, 0]
    assert [
        json.loads(o["stdout"].splitlines()[-1])["launches"] for o in observations[1:]
    ] == expected


@pytest.mark.parametrize("expired", [False, True])
def test_verifier_obeys_current_envelope_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expired: bool,
) -> None:
    from project_atlas.orchestration.program import supervisor
    from project_atlas.orchestration.program.continuation import load_envelope

    def configure(payload: dict[str, Any]) -> None:
        payload["program"]["tasks"][0].update(
            requires_independent_verification=True, verifier_profile_ref="verifier"
        )
        payload["profiles"]["verifier"] = {
            "agent_id": "fixture-verifier",
            "adapter": "local-command",
            "credential": "NOT_APPLICABLE",
            "capabilities": ["VERIFY"],
            "adapter_options": {
                "argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('VERIFIER.txt').write_text('observed\\n')",
                ]
            },
        }

    dispatcher = prepare(tmp_path, configure=configure)
    original = supervisor.append_event

    def expire_envelope(root: Path, kind: str, body: dict[str, object]) -> object:
        result = original(root, kind, body)
        if expired and kind == "AWAITING_INDEPENDENT_VERIFICATION":
            envelope = load_envelope(root, "work")
            assert envelope is not None
            persist_envelope(
                root, envelope.model_copy(update={"deadline_utc": "2000-01-01T00:00:00Z"})
            )
        return result

    monkeypatch.setattr(supervisor, "append_event", expire_envelope)
    result = dispatcher.tick()
    assert result.launched == (1 if expired else 2), repr(result)
    assert (tmp_path / "workspace/VERIFIER.txt").exists() is not expired


@pytest.mark.parametrize("fault", [None, "checkpoint_pair", "intent_pid", "attempt_pair"])
def test_interrupted_read_only_work_actually_restarts_after_owned_child_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str | None,
) -> None:
    from project_atlas.orchestration.program.adapters.base import pid_is_alive

    input_bytes = "immutable source input\n"
    diagnostic = tmp_path / "read-only-fixture-observations.txt"

    def configure(payload: dict[str, Any]) -> None:
        (tmp_path / "workspace/INPUT.txt").write_text(input_bytes)
        task = payload["program"]["tasks"][0]
        task["mutation_paths"] = []
        task["acceptance"] = [
            {
                "check_id": "readable",
                "kind": "FILE_EXISTS",
                "path": "INPUT.txt",
                "description": "source remains readable",
            }
        ]
        payload["profiles"]["impl"]["adapter_options"]["argv"] = [
            sys.executable,
            "-c",
            "import time; from pathlib import Path; time.sleep(0.2); "
            f"Path({str(diagnostic)!r}).open('a').write(Path('INPUT.txt').read_text())",
        ]

    dispatcher = prepare(tmp_path, configure=configure)
    controller = Path(__file__).with_name("_step_execution_controller.py")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cut = subprocess.run(
        [sys.executable, str(controller), str(tmp_path), str(Path.cwd()), "cut-read-only"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert cut.returncode == 91, (cut.stdout, cut.stderr)
    child = json.loads(cut.stdout.splitlines()[-1])
    deadline = time.monotonic() + 5.0
    while pid_is_alive(child["child_pid"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not pid_is_alive(child["child_pid"]), child
    if fault is not None:
        from project_atlas.orchestration.program import store
        from project_atlas.orchestration.program.adapters import local_command
        from project_atlas.orchestration.program.continuation import load_checkpoint

        cp = load_checkpoint(tmp_path, "work")
        assert cp is not None
        # Explicit contradiction injection, using only the exited test-owned
        # controller identity. The real child's launch record is preserved.
        controller_identity = json.loads(cut.stdout.splitlines()[0])
        pair = {
            "process_pid": controller_identity["pid"],
            "process_start_identity": controller_identity["start_identity"],
        }
        if fault == "checkpoint_pair":
            persist_checkpoint(
                tmp_path, cp.model_copy(update={"sequence": cp.sequence + 1, **pair})
            )
        elif fault == "attempt_pair":
            state = store.load_state(tmp_path)
            assert state is not None
            attempt = state.attempts[cp.identity.attempt_id]
            attempt.process_pid = pair["process_pid"]
            attempt.process_start_identity = pair["process_start_identity"]
            store.persist_state(tmp_path, state)
        else:
            intent = store.load_launch_intent(tmp_path, cp.identity.attempt_id)
            assert intent is not None
            store.record_launch_intent(
                tmp_path, attempt_id=cp.identity.attempt_id,
                pid=controller_identity["pid"], supervisor_pid=intent["supervisor_pid"],
                supervisor_instance_id=intent["supervisor_instance_id"],
                supervisor_start_identity=intent["supervisor_start_identity"],
            )

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("CONTRADICTORY_READONLY_REACHED_WORKER_SPAWN")

        monkeypatch.setattr(local_command, "run_child_to_completion", forbidden)
        assert dispatcher.tick().launched == 0
        assert diagnostic.read_text() == input_bytes
        after = load_checkpoint(tmp_path, "work")
        assert after is not None and not after.terminal
        if fault == "checkpoint_pair":
            assert after.process_pid == pair["process_pid"]
        return
    resumed = subprocess.run(
        [sys.executable, str(controller), str(tmp_path), str(Path.cwd()), "resume"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    (tmp_path / "read-only-controller.json").write_text(
        json.dumps(
            {
                "cut": cut.stdout,
                "cut_stderr": cut.stderr,
                "resume": resumed.stdout,
                "resume_stderr": resumed.stderr,
                "child": child,
                "signals_sent": 0,
            },
            indent=2,
        )
    )
    assert resumed.returncode == 0, (resumed.stdout, resumed.stderr)
    assert json.loads(resumed.stdout.splitlines()[-1])["launches"] == 1, resumed.stdout
    assert diagnostic.read_text() == input_bytes * 2
    assert (tmp_path / "workspace/INPUT.txt").read_text() == input_bytes


@pytest.mark.parametrize(
    "fault", ["earlier_acceptance", "earlier_exit", "earlier_missing", "wall_equal"]
)
def test_final_reconciliation_refuses_contradictory_prefix_or_spent_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    from project_atlas.orchestration.program import store, supervisor
    from project_atlas.orchestration.program.continuation import load_checkpoint, load_envelope

    dispatcher = prepare(tmp_path, steps=True)
    controller = Path(__file__).with_name("_step_execution_controller.py")
    cut = subprocess.run(
        [sys.executable, str(controller), str(tmp_path), str(Path.cwd()), "cut-final"],
        capture_output=True, text=True, timeout=20,
    )
    assert cut.returncode == 91, (cut.stdout, cut.stderr)
    cp = load_checkpoint(tmp_path, "work")
    state = store.load_state(tmp_path)
    assert cp is not None and state is not None
    assert cp.last_completed_step == "SECOND" and not cp.terminal
    first = next(a for a in state.attempts.values() if a.step_id == "FIRST")
    if fault == "earlier_acceptance":
        first.acceptance_passed = False
    elif fault == "earlier_exit":
        first.exit_status = 23
    elif fault == "earlier_missing":
        del state.attempts[first.attempt_id]
    else:
        envelope = load_envelope(tmp_path, "work")
        assert envelope is not None
        persist_checkpoint(tmp_path, cp.model_copy(update={
            "sequence": cp.sequence + 1,
            "consumed_budget": cp.consumed_budget.model_copy(
                update={"wall_seconds": envelope.budgets.max_wall_seconds}),
        }))
    store.persist_state(tmp_path, state)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("CONTRADICTORY_FINAL_BOUNDARY_REACHED_ACCEPTANCE")

    monkeypatch.setattr(supervisor, "evaluate_task", forbidden)
    assert dispatcher.tick().launched == 0
    after = load_checkpoint(tmp_path, "work")
    assert after is not None and not after.terminal


def test_unknown_workspace_revision_is_not_inferred_from_approval(tmp_path: Path) -> None:
    def configure(payload: dict[str, Any]) -> None:
        payload["program"].pop("allow_unversioned_fixture", None)

    dispatcher = prepare(tmp_path, configure=configure)
    result = dispatcher.tick()
    assert result.launched == 0, repr(result)
    assert not (tmp_path / "workspace/SECOND.txt").exists()


def test_checkpoint_budget_never_understates_durable_attempt_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from project_atlas.orchestration.program import control, store
    from project_atlas.orchestration.program.continuation import load_checkpoint

    dispatcher = pause_after_first(tmp_path, monkeypatch)
    cp = load_checkpoint(tmp_path, "work")
    assert cp is not None and cp.consumed_budget.wall_seconds > 0
    # Explicit inconsistent-counter injection; identity and successful receipt
    # remain production observations. Stronger durable consumption must win.
    persist_checkpoint(
        tmp_path,
        cp.model_copy(
            update={
                "sequence": cp.sequence + 1,
                "consumed_budget": cp.consumed_budget.model_copy(update={"wall_seconds": 0.0}),
            }
        ),
    )
    control.resume(tmp_path, requested_by="fixture-operator")
    result = dispatcher.tick()
    assert result.launched == 1, repr(result)
    state = store.load_state(tmp_path)
    final = load_checkpoint(tmp_path, "work")
    assert state is not None and final is not None and final.terminal
    assert final.consumed_budget.wall_seconds >= sum(
        a.duration_seconds or 0.0 for a in state.attempts.values()
    )


def test_worker_receives_fresh_bounded_continuation_context(tmp_path: Path) -> None:
    def configure(payload: dict[str, Any]) -> None:
        for step in payload["program"]["tasks"][0]["execution_steps"]:
            step["argv"][-1] += (
                "; import os,json; "
                "Path('contexts.jsonl').open('a').write(os.environ['ATLAS_PROGRAM_CONTINUATION']+'\\n')"
            )
        payload["program"]["tasks"][0]["mutation_paths"].append("contexts.jsonl")

    result = prepare(tmp_path, steps=True, configure=configure).tick()
    assert result.launched == 2 and result.report is not None and result.report.complete, repr(
        result
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "workspace/contexts.jsonl").read_text().splitlines()
    ]
    assert [r["next_step"] for r in rows] == ["FIRST", "SECOND"]
    assert [r["last_completed_step"] for r in rows] == [None, "FIRST"]
    assert all(r["task_id"] == "work" and r["program_id"] == "steps" for r in rows)
    assert rows[1]["commands_captured"] == 1
    assert all(len(json.dumps(r).encode()) <= 8192 for r in rows)
