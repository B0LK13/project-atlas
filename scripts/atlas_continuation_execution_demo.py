"""Installed zero-model within-task chain; real cuts, fresh controllers, no replay.

The checkout supplies the versioned test-only self-exit controller; all Atlas
imports and actual worker dispatch use the specified noneditable interpreter.
No service action or signal is issued. Never use an existing root.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

import project_atlas
from project_atlas.orchestration.program import approved_queue
from project_atlas.orchestration.program.adapters.base import (
    pid_is_alive,
    process_start_identity,
)
from project_atlas.orchestration.program.capsule import build_capsule, render_capsule
from project_atlas.orchestration.program.continuation import load_checkpoint
from project_atlas.orchestration.program.enrollment import assign, enroll
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.store import load_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--cut", choices=("first", "final"), required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=True)
    pins = subprocess.check_output(
        ["git", "-C", str(checkout), "show", "-s", "--format=%H %T"], text=True
    ).split()
    assert pins == [args.head, args.tree], pins
    dirty = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain"], text=True
    )
    assert not dirty.strip(), dirty
    module = Path(project_atlas.__file__).resolve()
    assert "site-packages" in module.parts and not module.is_relative_to(checkout)
    metadata = importlib.metadata.distribution("project-atlas")
    direct = json.loads(metadata.read_text("direct_url.json") or "{}")
    assert direct.get("archive_info") and not direct.get("dir_info", {}).get("editable")
    root = args.root.absolute()
    assert not root.exists(), "a fresh disposable root is required"
    root.mkdir(parents=True)
    assert root.resolve() == root, "demo root must have no symlink ancestor"
    workspace = root / "workspace"
    workspace.mkdir()
    provenance = {
        "head": pins[0], "tree": pins[1], "source_clean": True,
        "executable": sys.executable, "module": str(module), "python": sys.version,
        "direct_url": direct, "pid": os.getpid(),
        "start_identity": process_start_identity(os.getpid()), "root": str(root),
    }
    (root / "pre-execution-provenance.json").write_text(json.dumps(provenance, indent=2))
    steps = []
    for name in ("FIRST", "SECOND"):
        code = (
            "import json,os; from pathlib import Path; "
            "from project_atlas.orchestration.program.adapters.base import process_start_identity; "
            f"Path('{name}.txt').open('a').write('{name}\\n'); "
            f"Path('{name}.identity.json').write_text(json.dumps({{"
            "'pid':os.getpid(),'start_identity':process_start_identity(os.getpid()),"
            "'context':json.loads(os.environ['ATLAS_PROGRAM_CONTINUATION'])}))"
        )
        steps.append({
            "step_id": name, "argv": [sys.executable, "-B", "-c", code],
            "acceptance": [{"check_id": name.lower(), "kind": "FILE_EXISTS",
                            "description": "observed result", "path": f"{name}.txt"}],
        })
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "installed-steps", "objective": "resume exact next approved step",
            "approved_by": "fixture-operator", "approval_reference": "CONTINUATION-002-DEMO",
            "workspace_root": str(workspace), "allow_unversioned_fixture": True,
            "base_pin": args.head,
            "limits": {"max_cycles": 20, "idle_sleep_seconds": 0.0,
                       "max_attempts_per_task": 2, "max_task_launches": 2},
            "tasks": [{
                "task_id": "work", "title": "bounded two-step task", "instruction": "continue",
                "profile_ref": "impl", "mutation_paths": ["FIRST.txt", "SECOND.txt",
                    "FIRST.identity.json", "SECOND.identity.json"],
                "surface_id": "work", "surface_semantic": "WORK", "execution_steps": steps,
                "acceptance": [{"check_id": "complete", "kind": "FILE_EXISTS",
                                "description": "second step output exists", "path": "SECOND.txt"}],
            }],
        },
        "profiles": {"impl": {
            "agent_id": "installed-step-worker", "adapter": "local-command",
            "credential": "NOT_APPLICABLE", "capabilities": ["IMPLEMENT"],
            "adapter_options": {"argv": [sys.executable, "-c", "raise SystemExit(99)"]},
        }},
    }
    path = root / "program.json"
    path.write_text(json.dumps(payload, indent=2))
    load_program(path, governed_root=root)
    registry = root / "registry"
    enroll(registry, agent_id="installed-step-worker", role="impl", adapter="local-command",
           workspace_root=workspace, enrolled_by="fixture-operator")
    assign(registry, agent_id="installed-step-worker", program_path=path,
           assigned_by="fixture-operator", governed_root=root)
    approved_queue.admit(root / "queue", program_path=path, program_id="installed-steps",
                         state_root=root, admitted_by="fixture-operator",
                         reference="installed bounded demo", governed_root=root)
    controller = checkout / "tests/unit/_step_execution_controller.py"
    child_env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    modes = ["cut" if args.cut == "first" else "cut-final", "resume", "resume", "resume"]
    observations = []
    for index, mode in enumerate(modes):
        argv = [sys.executable, "-B", str(controller), str(root), str(checkout), mode]
        result = subprocess.run(argv, env=child_env, cwd=root, capture_output=True,
                                text=True, timeout=30, check=False)
        observations.append({"argv": argv, "exit": result.returncode,
                             "stdout": result.stdout, "stderr": result.stderr})
        (root / "controller-observations.json").write_text(json.dumps(observations, indent=2))
        assert result.returncode == (91 if index == 0 else 0), observations
        if index == 0:
            assert (workspace / "SECOND.txt").exists() == (args.cut == "final")
    assert [json.loads(row["stdout"].splitlines()[-1])["launches"]
            for row in observations[1:]] == ([1, 0, 0] if args.cut == "first" else [0, 0, 0])
    workers = []
    for name in ("FIRST", "SECOND"):
        assert (workspace / f"{name}.txt").read_text() == name + "\n"
        workers.append(json.loads((workspace / f"{name}.identity.json").read_text()))
    cp = load_checkpoint(root, "work")
    state = load_state(root)
    assert cp is not None and cp.terminal and len(cp.commands) == 2
    assert state is not None and state.total_launches == 2 and len(state.attempts) == 2
    for command, step in zip(cp.commands, steps, strict=True):
        assert list(command.argv) == step["argv"] and command.exit_status == 0
    controllers = [json.loads(row["stdout"].splitlines()[0]) for row in observations]
    assert len({row["pid"] for row in controllers}) == 4
    assert all(row["start_identity"] not in (None, "", "unknown") for row in controllers + workers)
    assert all(not pid_is_alive(row["pid"]) for row in controllers + workers)
    (root / "capsule.md").write_text(render_capsule(build_capsule(
        root, for_worker_id="demo-observer", queue_root=root / "queue", governed_root=root)))
    summary = {**provenance, "result": "PASS", "cut": args.cut, "registry": str(registry),
               "controllers": controllers, "workers": workers, "total_launches": 2,
               "completed_restarts_launches": [0, 0], "signals_sent": 0,
               "owned_survivors": [], "model_calls": 0, "runtime_support": "local-command only",
               "workspace_pin": "explicit unversioned fixture, NOT observed workspace Git",
               "controller_sha256": hashlib.sha256(controller.read_bytes()).hexdigest()}
    (root / "result.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
