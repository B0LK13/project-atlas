"""Run the zero-model supervisor chain in a fresh explicitly supplied root.

Run with the candidate's non-editable installation. Source scripts are inputs;
the script verifies that project_atlas itself is imported from site-packages.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import project_atlas
from project_atlas.orchestration.program import approved_queue, control, resident
from project_atlas.orchestration.program.capsule import build_capsule, render_capsule
from project_atlas.orchestration.program.continuation import (
    ContinuationCheckpoint,
    ExecutionIdentity,
    list_checkpoints,
    load_checkpoint,
    load_envelope,
    persist_checkpoint,
)
from project_atlas.orchestration.program.enrollment import AgentStatus, assign, enroll, set_status
from project_atlas.orchestration.program.adapters.base import pid_is_alive
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.reconciliation import reconcile_root
from project_atlas.orchestration.program.store import load_state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--allow-source", action="store_true")
    parser.add_argument(
        "--scenario", choices=["complete", "revoked", "uncertain"], default="complete"
    )
    args = parser.parse_args()
    module = Path(project_atlas.__file__).resolve()
    assert args.allow_source or "site-packages" in module.parts, str(module)
    root = args.root.absolute()
    assert not root.exists(), "demo requires a new root; never overwrite prior evidence"
    root.mkdir(parents=True)
    workspace = root / "workspace"
    workspace.mkdir()
    state, queue, registry = root / "state", root / "queue", root / "registry"
    worker = args.checkout / "scripts/atlas_takeover_worker.py"
    revision = (
        subprocess.check_output(
            ["git", "-C", str(args.checkout), "show", "-s", "--format=%H %T"], text=True
        )
        .strip()
        .split()
    )
    tasks = []
    for task in ("first", "second"):
        tasks.append(
            {
                "task_id": task,
                "title": task,
                "instruction": "write the fixture result",
                "profile_ref": "impl",
                "mutation_paths": [f"{task}.txt"],
                "surface_id": task,
                "surface_semantic": task.upper(),
                "capabilities_required": ["IMPLEMENT"],
                "depends_on": [] if task == "first" else ["first"],
                "acceptance": [
                    {
                        "check_id": task,
                        "kind": "FILE_EXISTS",
                        "description": "fixture result",
                        "path": f"{task}.txt",
                    }
                ],
            }
        )
    program = root / "program.json"
    program.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "program": {
                    "program_id": "takeover-demo",
                    "objective": "pause and complete approved work",
                    "approved_by": "fixture-operator",
                    "approval_reference": "TAKEOVER-001",
                    "workspace_root": str(workspace),
                    "allow_unversioned_fixture": True,
                    "base_pin": revision[0],
                    "limits": {
                        "max_cycles": 30,
                        "idle_sleep_seconds": 0.01,
                        "max_concurrent_workers": 1,
                    },
                    "tasks": tasks,
                },
                "profiles": {
                    "impl": {
                        "agent_id": "placeholder",
                        "adapter": "local-command",
                        "credential": "NOT_APPLICABLE",
                        "capabilities": ["IMPLEMENT"],
                        "env_allowlist": ["ATLAS_PROGRAM_TASK", "ATLAS_PROGRAM_ATTEMPT"],
                        "adapter_options": {"argv": [sys.executable, str(worker)]},
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    loaded = load_program(program)
    enroll(
        registry,
        agent_id="demo-worker",
        role="impl",
        adapter="local-command",
        workspace_root=workspace,
        enrolled_by="fixture-operator",
    )
    assign(registry, agent_id="demo-worker", program_path=program, assigned_by="fixture-operator")
    approved_queue.admit(
        queue,
        program_path=program,
        program_id="takeover-demo",
        state_root=state,
        admitted_by="fixture-operator",
        reference="TAKEOVER-001",
        governed_root=root,
    )

    def dispatcher():
        return resident.ResidentDispatcher(
            root=state,
            queue_root=queue,
            checkout=args.checkout,
            registry_root=registry,
            governed_root=root,
            tick_seconds=0.5,
            wake_quantum_seconds=0.05,
        )

    phases: list[dict] = []

    def run_phase():
        command = [
            sys.executable,
            "-m",
            "project_atlas.orchestration.program.cli",
            "program",
            "dispatcher",
            "--action",
            "run",
            "--state-root",
            str(state),
            "--queue-root",
            str(queue),
            "--governed-root",
            str(root),
            "--registry",
            str(registry),
            "--checkout",
            str(args.checkout),
            "--tick-seconds",
            "0.5",
            "--max-ticks",
            "1",
            "--max-seconds",
            "20",
        ]
        completed = subprocess.run(
            command, cwd=root, text=True, capture_output=True, timeout=30, check=False
        )
        assert completed.returncode == 0, (completed.stdout, completed.stderr)
        payload = json.loads(completed.stdout)
        phases.append({"argv": command, "exit": completed.returncode, "output": payload})
        return SimpleNamespace(launched=payload["launches"], output=payload)

    errors: list[str] = []

    def pause_after_first():
        try:
            deadline = time.monotonic() + 15
            while not (workspace / "first.txt").exists():
                if time.monotonic() > deadline:
                    raise AssertionError("first worker never executed")
                time.sleep(0.01)
            control.pause(state, requested_by="demo-operator", loaded=loaded)
            resident.request_pause(state, requested_by="demo-operator")
        except Exception as exc:
            errors.append(repr(exc))

    watcher = threading.Thread(target=pause_after_first)
    watcher.start()
    first = run_phase()
    watcher.join(timeout=20)
    assert not watcher.is_alive() and not errors, errors
    assert first.launched == 1, first
    assert not (workspace / "second.txt").exists()
    digest = hashlib.sha256((workspace / "first.txt").read_bytes()).hexdigest()
    restarted = dispatcher()
    paused = run_phase()
    assert paused.launched == 0
    if args.scenario == "revoked":
        set_status(registry, agent_id="demo-worker", status=AgentStatus.SUSPENDED)
    elif args.scenario == "uncertain":
        # Explicit fault injection, never misreported as observed execution.
        envelope = load_envelope(state, "second")
        assert envelope is not None
        prior = load_checkpoint(state, "second")
        persist_checkpoint(
            state,
            ContinuationCheckpoint(
                identity=ExecutionIdentity(
                    task_id="second",
                    worker_id="demo-worker",
                    session_id="fixture-interrupted-session",
                    attempt_id="fixture-uncertain-attempt",
                ),
                envelope_digest=envelope.digest(),
                program_id="takeover-demo",
                sequence=(prior.sequence + 1 if prior is not None else 1),
                next_action="reconcile injected uncertain execution",
                worktree_path=str(workspace),
                git_head=revision[0],
                git_tree=revision[1],
                replay_class=envelope.replay_class,
                uncertainty=("FAULT INJECTION: external effect outcome unknown",),
            ),
        )
    control.resume(state, requested_by="demo-operator", loaded=loaded)
    resident.clear_pause(state)
    finished = run_phase()
    expected = 1 if args.scenario == "complete" else 0
    assert finished.launched == expected, finished
    assert (workspace / "second.txt").exists() == bool(expected)
    assert hashlib.sha256((workspace / "first.txt").read_bytes()).hexdigest() == digest
    replay = run_phase()
    assert replay.launched == 0
    persisted = load_state(state)
    assert persisted is not None and persisted.total_launches == 1 + expected
    checkpoints = list_checkpoints(state)
    assert any(cp.identity.task_id == "first" and cp.terminal for cp in checkpoints)
    if expected:
        assert len(checkpoints) == 2 and all(cp.terminal for cp in checkpoints)
    reconciled = reconcile_root(
        state, our_worker_id="demo-observer", queue_root=queue, governed_root=root
    )
    if args.scenario != "revoked":
        assert all(not item.launchable for item in reconciled)
    worker_pids = [
        json.loads(line)["pid"]
        for file in workspace.glob("*.txt")
        for line in file.read_text().splitlines()
    ]
    assert worker_pids and all(not pid_is_alive(pid) for pid in worker_pids)
    dispatcher_pids = [p["output"]["status"]["heartbeat"]["pid"] for p in phases]
    assert len(set(dispatcher_pids)) == 4
    assert all(not pid_is_alive(pid) for pid in dispatcher_pids)
    capsule = render_capsule(
        build_capsule(state, for_worker_id="demo-observer", queue_root=queue, governed_root=root)
    )
    (root / "capsule.md").write_text(capsule, encoding="utf-8")
    result = {
        "head": revision[0],
        "tree": revision[1],
        "checkout_changes": subprocess.check_output(
            ["git", "-C", str(args.checkout), "status", "--porcelain"], text=True
        ).splitlines(),
        "module": str(module),
        "python": sys.executable,
        "registry": str(restarted.registry_root),
        "launches": [first.launched, paused.launched, finished.launched, replay.launched],
        "total_launches": persisted.total_launches,
        "checkpoint_count": len(checkpoints),
        "terminal_checkpoints": sum(cp.terminal for cp in checkpoints),
        "reconciliation": [asdict(v) for v in reconciled],
        "model_calls": 0,
        "tested_adapter": "local-command",
        "scenario": args.scenario,
        "owned_worker_pids": worker_pids,
        "dispatcher_pids": dispatcher_pids,
        "phases": phases,
        "owned_worker_survivors": [],
        "checkpoint_capture": [cp.capture.model_dump(mode="json") for cp in checkpoints],
        "runtime_compatibility_claim": "bounded local-command fixture only",
        "pid": os.getpid(),
        "result": "PASS",
    }
    (root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
