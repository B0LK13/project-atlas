"""G4a -- the detached supervisor must not inherit the operator's shell.

PYTHONPATH precedes the editable install on sys.path and LD_PRELOAD precedes
Python altogether, so inheritance lets whoever typed `service start` choose
the code that runs while the recorded revision still describes the checkout.
The allow-list is checked in both directions: injection vectors are stripped,
and PATH survives -- an allow-list that grew too narrow would also "pass".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program import service
from project_atlas.orchestration.program.enrollment import (
    assign,
    enroll,
)
from project_atlas.orchestration.program.profiles import AdapterKind

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
PAUSING_WORKER = Path(__file__).with_name("_security_003_pausing_worker.py")
PROBE_WORKER = Path(__file__).with_name("_hardening_004_status_probe_worker.py")


def _profile(agent_id: str, *, argv: list[str] | None = None) -> dict[str, Any]:
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
            "ATLAS_SEC003_STATE_ROOT",
            "ATLAS_H004_STATE_ROOT",
            "ATLAS_H004_PROBE_OUT",
            "ATLAS_H004_PROGRAM",
        ],
        "adapter_options": {"argv": argv or [sys.executable, str(FIXTURE_WORKER)]},
    }


def _task(task_id: str, profile_ref: str, out: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": task_id,
        "instruction": "fixture",
        "profile_ref": profile_ref,
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


def _write_program(
    tmp_path: Path,
    workspace: Path,
    *,
    tasks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    name: str = "program.json",
) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "sec003",
            "objective": "security-003 regression",
            "approved_by": "test",
            "approval_reference": "SECURITY-003",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 12, "idle_sleep_seconds": 0.0},
            "tasks": tasks,
        },
        "profiles": profiles,
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)



def test_g4a_detached_supervisor_does_not_inherit_pythonpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G4a: de gedetachte supervisor mag de shell-omgeving niet erven.

    PYTHONPATH gaat voor de editable install, dus een geerfde PYTHONPATH laat
    andere code draaien dan de gepinde checkout -- zonder dat iets dat vastlegt.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("only", "implementer", "only.txt")],
        profiles={"implementer": _profile("program-placeholder")},
    )
    agent = enroll(
        registry,
        agent_id="real-implementer",
        role="implementer",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id=agent.agent_id, program_path=program, assigned_by="test")

    # HARDENING-004: a deny-list version of this fix stripped the PYTHON*
    # names and let LD_PRELOAD / LD_LIBRARY_PATH / PYTHONSAFEPATH through.
    # LD_PRELOAD injects before Python even starts, so it is the stronger
    # vector of the two. These names are here to keep an allow-list an
    # allow-list.
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONSAFEPATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LD_AUDIT",
    ):
        monkeypatch.setenv(name, f"/tmp/injected-{name.lower()}")

    captured: dict[str, Any] = {}

    class _FakeProcess:
        pid = 4242

        def poll(self) -> int | None:
            return None

    def _fake_popen(argv: list[str], **kwargs: Any) -> _FakeProcess:
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    # De start faalt verderop (het neppe proces schrijft nooit zijn identity),
    # maar de Popen-aanroep is dan al gedaan en dat is wat hier telt.
    with pytest.raises(service.ServiceError):
        service.start(
            tmp_path / "state",
            program,
            registry_root=registry,
        )

    env = captured.get("env")
    assert env is not None, (
        "service.start() gaf geen expliciete env mee aan Popen; de gedetachte "
        "supervisor erft de volledige shell-omgeving"
    )
    leaked = sorted(
        name
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONSTARTUP",
            "PYTHONSAFEPATH",
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "LD_AUDIT",
        )
        if name in env
    )
    assert not leaked, f"code-injectievectoren lekken naar de supervisor: {leaked}"
    # De supervisor moet wel bruikbaar blijven: zonder PATH start er niets.
    assert "PATH" in env, "de allow-list is te smal geworden; PATH ontbreekt"


# ------------------------------------------------------- HARDENING-005 extra


def test_g4a_service_identity_records_the_code_revision(tmp_path: Path) -> None:
    """G4a: een gepinde checkout pint de draaiende code niet -- leg hem vast."""
    provenance = service._code_provenance()
    assert provenance["interpreter"], "interpreter niet vastgelegd"
    assert provenance["package_path"], "package_path niet vastgelegd"
    assert provenance["code_revision"], "code_revision ontbreekt"
    assert provenance["code_revision"] == "unknown" or len(
        provenance["code_revision"]
    ) == 40, "een revisie is een volledige sha of eerlijk 'unknown'"
