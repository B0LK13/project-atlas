"""Studio-reconnect proof for the A1 read-only route with Prime metadata.

A Studio "connection" is a read of ``control_view``. Two connections must
project IDENTICAL Prime ``runtime_metadata`` — closing the first viewer must
not stop, mark, or perturb the second read — and no state file may change in
content or mtime while the views are taken. This mirrors
``test_orchestration_program_control.test_closing_a_viewer_does_not_touch_the_supervisor``
with a Prime ``.prime-daemon.json`` bound into the attempt evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program import control
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.store import (
    evidence_dir,
    load_state,
    persist_state,
    state_dir,
)
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")


def _program(tmp_path: Path, workspace: Path) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "prime-studio-program",
            "objective": "studio reconnect coverage",
            "approved_by": "wesley",
            "approval_reference": "docs/orchestration/program/CONTROL.md",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 10, "idle_sleep_seconds": 0.0},
            "tasks": [
                {
                    "task_id": "alpha",
                    "title": "task alpha",
                    "instruction": "do it",
                    "profile_ref": "impl",
                    "mutation_paths": ["alpha.txt"],
                    "surface_id": "alpha",
                    "surface_semantic": "ALPHA",
                    "capabilities_required": ["IMPLEMENT"],
                    "acceptance": [
                        {
                            "check_id": "alpha-out",
                            "kind": "FILE_EXISTS",
                            "description": "alpha.txt exists",
                            "path": "alpha.txt",
                        }
                    ],
                }
            ],
        },
        "profiles": {
            "impl": {
                "agent_id": "control-agent",
                "adapter": "local-command",
                "credential": "NOT_APPLICABLE",
                "capabilities": ["IMPLEMENT"],
                "env_allowlist": [
                    "ATLAS_FIXTURE_MODE",
                    "ATLAS_PROGRAM_ATTEMPT",
                    "ATLAS_PROGRAM_TASK",
                ],
                "adapter_options": {"argv": [sys.executable, str(FIXTURE_WORKER)]},
            }
        },
    }
    path = tmp_path / "program.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


def _run(tmp_path: Path, program: Path) -> Any:
    supervisor = ProgramSupervisor(
        load_program(program), state_root=tmp_path / "state", sleeper=lambda _s: None
    )
    return supervisor.start()


_PRIME_METADATA: dict[str, Any] = {
    "candidate_sha": "a" * 40,
    "tree_sha": "b" * 40,
    "prime_session_id": None,
    "prime_active_session_id": "active-studio-1",
    "daemon_process_start_identity": "fixture-identity",
    "server_capabilities": ["attach_snapshot", "event_sequence"],
    "schema_revision": 7,
    "worker_generation": "gen-1",
    "last_event_cursor": {"generation": "gen-1", "sequence": 12},
    "child_registry": [],
    "child_registry_journal": None,
}


def _bind_prime_metadata(root: Path) -> None:
    """Attach a Prime daemon metadata document to the certified attempt."""
    state = load_state(root)
    assert state is not None
    attempt_id = state.tasks["alpha"].last_attempt_id
    assert attempt_id is not None
    name = f"{attempt_id}.prime-daemon.json"
    (evidence_dir(root) / name).write_text(
        json.dumps(_PRIME_METADATA, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state.attempts[attempt_id].evidence_paths = (
        *state.attempts[attempt_id].evidence_paths,
        name,
    )
    persist_state(root, state)


def _prime_projection(view: dict[str, Any]) -> dict[str, Any] | None:
    row = next(task for task in view["tasks"] if task["task_id"] == "alpha")
    return row["last_attempt"]["runtime_metadata"]


def _tree_state(root: Path) -> dict[str, tuple[int, bytes]]:
    base = state_dir(root)
    return {
        str(path.relative_to(base)): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def test_prime_runtime_metadata_projection_is_reconnect_stable(tmp_path: Path) -> None:
    """Two Studio connections over the A1 read-only route: identical Prime
    projections, the second read unaffected by the first viewer closing, and
    every state file byte- and mtime-identical before and after."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program(tmp_path, workspace)
    _run(tmp_path, program)
    root = tmp_path / "state"
    loaded = load_program(program)
    _bind_prime_metadata(root)
    before = _tree_state(root)

    first_view = control.control_view(root, loaded)
    first = _prime_projection(first_view)
    # The first viewer closes here: there is nothing to close, which is the
    # point — a view holds no connection and leaving cannot disturb the state.
    second_view = control.control_view(root, loaded)
    second = _prime_projection(second_view)

    assert first == second, "reconnect must project identical Prime metadata"
    assert first == _PRIME_METADATA

    after = _tree_state(root)
    assert after == before, "reading the view must not touch any state file"
    assert not (state_dir(root) / "supervisor.stop").is_file(), (
        "reading must never request a stop"
    )
