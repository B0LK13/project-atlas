"""Rollback-without-mission-loss pin for the Prime certified slice.

LIMITATION, named rather than hidden: the control surface exposes no dedicated
``rollback`` action — ``SUPPORTED_ACTIONS`` is pause/resume/cancel/reconcile.
Per the runbook, rollback removes only the candidate adapter/runtime
registration from the candidate branch, which is a branch-level operator act
outside this surface. This test therefore binds the mission-loss half of the
rollback contract to the strongest documented stop/removal action the control
surface does expose — cancel issued through ``atlas program control`` — and
pins that it never deletes or mutates mission evidence: the daemon journal,
the attempt metadata, and the knowledge-capture row all survive byte-intact.
No child-admission journal is configured in this fixture, so
``_valid_child_journal_lines`` has nothing to validate here; when present the
same byte-intactness assertion covers it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program import control
from project_atlas.orchestration.program.adapters.prime_agent import (
    PRIME_UPSTREAM_SHA,
    _valid_child_journal_lines,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramStopReason
from project_atlas.orchestration.program.store import evidence_dir, load_state
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _git(workspace, "init", "--quiet")
    _git(workspace, "config", "user.email", "fixture@example.invalid")
    _git(workspace, "config", "user.name", "Fixture")
    (workspace / "README.md").write_text("fixture workspace\n", encoding="utf-8")
    _git(workspace, "add", "README.md")
    _git(workspace, "commit", "--quiet", "-m", "seed")
    return workspace


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.setenv("ATLAS_FIXTURE_TARGET", "out.txt")


def _verifier_profile() -> dict[str, object]:
    return {
        "agent_id": "prime-independent-verifier",
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["VERIFY"],
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_FIXTURE_TARGET",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
        ],
        "adapter_options": {"argv": ["python3", str(FIXTURE_WORKER)]},
    }


def _prime_profile(tmp_path: Path, workspace: Path) -> dict[str, object]:
    fake = tmp_path / "prime-daemon-fixture.py"
    fake.write_text(
        """#!/usr/bin/env python3
import argparse, json, os, socket
parser = argparse.ArgumentParser()
parser.add_argument('--daemon-socket', required=True)
parser.add_argument('--cwd', required=True)
args, _ = parser.parse_known_args()
if os.path.exists(args.daemon_socket): os.unlink(args.daemon_socket)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(args.daemon_socket); server.listen(4)
while True:
    connection, _ = server.accept()
    with connection, connection.makefile('rb') as reader:
        try:
            connection.sendall((json.dumps({'type':'daemon_hello','protocol':{'name':'prime-agent.daemon','version':7},'serverCapabilities':['attach_snapshot','event_sequence']})+'\\n').encode())
        except BrokenPipeError:
            continue
        for raw in reader:
            envelope = json.loads(raw)
            command = envelope['command']
            data = None
            if command['type'] == 'create': data = {'activeSessionId':'fixture-session'}
            elif command['type'] == 'prompt_and_wait':
                open(os.path.join(args.cwd, 'prime-output.txt'), 'w').write('accepted by Atlas\\n')
            elif command['type'] == 'get_last_assistant_text':
                data = {'text':'fixture execution complete'}
            response = {
                'type':'response', 'id':envelope['id'],
                'command':command['type'], 'success':True,
            }
            if data is not None: response['data'] = data
            connection.sendall((json.dumps(response)+'\\n').encode())
server.close()
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    runtime_manifest = tmp_path / "prime-runtime-manifest.json"
    runtime_manifest.write_text(
        json.dumps(
            {
                "upstream_sha": PRIME_UPSTREAM_SHA,
                "source_commit_verified": True,
                "executable": {
                    "path": str(fake.resolve()),
                    "sha256": hashlib.sha256(fake.read_bytes()).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "agent_id": "prime-fixture-agent",
        "adapter": "prime-agent",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "model": "fixture-model",
        "allowed_mutation_prefixes": ["prime-output.txt"],
        "limits": {"max_attempts": 1, "max_seconds": 30},
        "adapter_options": {
            "executable": str(fake),
            "daemon_socket": str(tmp_path / "prime.sock"),
            "provider": "fixture-provider",
            "sandbox_argv": [
                "/usr/bin/bwrap",
                "--die-with-parent",
                "--new-session",
                "--unshare-all",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/bin",
                "/bin",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind",
                "/lib64",
                "/lib64",
                "--ro-bind",
                "/etc",
                "/etc",
                "--bind",
                str(tmp_path),
                str(tmp_path),
                "--chdir",
                str(workspace),
            ],
            "runtime_manifest": str(runtime_manifest),
        },
    }


def _write_program(tmp_path: Path, workspace: Path) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "prime-rollback-program",
            "objective": "rollback without mission loss",
            "approved_by": "fixture-owner",
            "approval_reference": "docs/orchestration/program/PRIME-LOCAL-001-RUNBOOK.md",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 20, "idle_sleep_seconds": 0.0},
            "tasks": [
                {
                    "task_id": "prime-task",
                    "title": "fixture prime task",
                    "instruction": "write prime-output.txt",
                    "profile_ref": "implementer",
                    "mutation_paths": ["prime-output.txt"],
                    "surface_id": "surface-prime-task",
                    "surface_semantic": "SURFACE_PRIME_TASK",
                    "capabilities_required": ["IMPLEMENT"],
                    "requires_independent_verification": True,
                    "verifier_profile_ref": "verifier",
                    "acceptance": [
                        {
                            "check_id": "prime-task-output",
                            "kind": "FILE_EXISTS",
                            "description": "prime-output.txt exists",
                            "path": "prime-output.txt",
                        }
                    ],
                }
            ],
        },
        "profile_defaults": {
            "adapter": "local-command",
            "credential": "NOT_APPLICABLE",
        },
        "profiles": {
            "implementer": _prime_profile(tmp_path, workspace),
            "verifier": _verifier_profile(),
        },
    }
    path = tmp_path / "program.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_rollback_after_certification_preserves_mission_evidence(
    tmp_path: Path,
) -> None:
    """Cancel (the control surface's rollback-adjacent action) after a
    CERTIFIED Prime attempt deletes nothing: journal, metadata and capture row
    survive byte-intact. No dedicated rollback action exists in the control
    surface; see the module docstring."""
    workspace = _make_workspace(tmp_path)
    program = _write_program(tmp_path, workspace)
    loaded = load_program(program)
    root = tmp_path / "state"

    report = ProgramSupervisor(
        loaded, state_root=root, sleeper=lambda _s: None
    ).start()

    assert report.complete is True
    assert report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    state = load_state(root)
    assert state is not None
    assert state.tasks["prime-task"].state is NodeState.CERTIFIED

    evidence = evidence_dir(root)
    metadata_path = next(evidence.glob("*.prime-daemon.json"))
    journal_path = next(evidence.glob("*.prime-daemon.jsonl"))
    capture_path = evidence / "prime-knowledge-capture.jsonl"
    assert capture_path.is_file()
    assert list(evidence.glob("*.child-admission.jsonl")) == []
    before = _snapshot_tree(evidence)

    report_cancel = control.request_action(
        root, loaded, action="cancel", requested_by="operator"
    )

    assert report_cancel["cancel_requested"] is True
    state = load_state(root)
    assert state is not None
    assert state.cancel_requested is True
    assert _snapshot_tree(evidence) == before, (
        "the operator action must not delete or mutate mission evidence"
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    attempt_id = metadata["attempt_id"]
    assert metadata["policy_hash"] is None
    journal_lines = journal_path.read_text(encoding="utf-8").splitlines()
    assert any(line.strip() for line in journal_lines)
    capture_rows = [
        json.loads(line)
        for line in capture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(capture_rows) == 1
    (capture_row,) = capture_rows
    assert capture_row["event_id"] == f"KE-{attempt_id}"
    assert capture_row["sync_state"] == "pending_local_evidence_not_canonical"
    child_journals = list(evidence.glob("*.child-admission.jsonl"))
    if child_journals:
        assert _valid_child_journal_lines(
            child_journals[0].read_text(encoding="utf-8").splitlines(),
            mission_id=metadata["mission_id"],
            task_id=metadata["task_id"],
            attempt_id=attempt_id,
        )
