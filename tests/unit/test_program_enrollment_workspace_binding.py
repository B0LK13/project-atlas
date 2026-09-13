"""Current enrollment workspace is a binding, not an informational hint."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_program_authority_verifier_binding import (
    _enrol_pair,
    _profile,
    _supervisor,
    _verified_task,
    _write_program,
)

from project_atlas.orchestration.program import enrollment, supervisor
from project_atlas.orchestration.program.adapters import local_command
from project_atlas.orchestration.program.models import ProgramError
from project_atlas.orchestration.program.profiles import AdapterKind


def prepare(root: Path) -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    workspace.mkdir()
    registry = root / "registry"
    program = _write_program(root, workspace, tasks=[_verified_task("alpha")], profiles={
        "implementer": _profile("impl-placeholder"),
        "verifier": _profile("verifier-placeholder", capabilities=["VERIFY"]),
    })
    _enrol_pair(registry, workspace, program)
    return workspace, registry, program


def replace_workspace(root: Path, registry: Path, agent_id: str, fault: str) -> None:
    other = root / "other"
    other.mkdir(exist_ok=True)
    if fault == "relative":
        value = "workspace"
    elif fault == "symlink":
        link = root / "workspace-alias"
        link.symlink_to(root / "workspace", target_is_directory=True)
        value = str(link)
    else:
        value = str(other)
    roster = enrollment.load_registry(registry)
    roster.agents[agent_id].workspace_root = value
    enrollment.persist_registry(registry, roster)


@pytest.mark.parametrize("agent_id", ["impl-a", "verif-b"])
@pytest.mark.parametrize("fault", [None, "other", "relative", "symlink"])
def test_initial_binding_requires_exact_registered_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent_id: str, fault: str | None,
) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    workspace, registry, program = prepare(tmp_path)
    if fault is None:
        report = _supervisor(tmp_path, program, registry).start()
        assert report.complete and report.launches_this_run == 2
        assert (workspace / "alpha.txt").exists()
        return
    replace_workspace(tmp_path, registry, agent_id, fault)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("MISMATCHED_WORKSPACE_REACHED_WORKER_SPAWN")

    monkeypatch.setattr(local_command, "run_child_to_completion", forbidden)
    with pytest.raises(ProgramError) as caught:
        _supervisor(tmp_path, program, registry).start()
    assert caught.value.code == "ENROLLMENT_WORKSPACE_MISMATCH"
    assert not list(workspace.glob("*.txt"))
    assert not list((tmp_path / "other").iterdir())


@pytest.mark.parametrize("agent_id", ["impl-a", "verif-b"])
@pytest.mark.parametrize("fault", ["other", "relative", "symlink"])
def test_workspace_rechecked_after_real_implementation_before_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent_id: str, fault: str,
) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    workspace, registry, program = prepare(tmp_path)
    instance = _supervisor(tmp_path, program, registry)
    original = supervisor.append_event

    def change_after_implementation(root: Path, kind: str, body: dict[str, Any]) -> Any:
        result = original(root, kind, body)
        if kind == "AWAITING_INDEPENDENT_VERIFICATION":
            replace_workspace(tmp_path, registry, agent_id, fault)

            def forbidden(*args: Any, **kwargs: Any) -> Any:
                raise AssertionError("STALE_WORKSPACE_REACHED_VERIFIER_SPAWN")

            monkeypatch.setattr(local_command, "run_child_to_completion", forbidden)
        return result

    monkeypatch.setattr(supervisor, "append_event", change_after_implementation)
    report = instance.start()
    assert not report.complete and report.launches_this_run == 1
    assert (workspace / "alpha.txt").exists()
    assert not list((tmp_path / "other").iterdir())


def test_enroll_does_not_hide_a_symlink_before_recording_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(ProgramError):
        enrollment.enroll(tmp_path / "registry", agent_id="alias-worker", role="impl",
                          adapter="local-command", workspace_root=link, enrolled_by="fixture")
    assert not enrollment.load_registry(tmp_path / "registry").agents


@pytest.mark.parametrize("agent_id", ["impl-a", "verif-b"])
@pytest.mark.parametrize(
    "fault", ["narrowing", "runtime", "duplicate_role", "identity", "description"]
)
def test_fresh_dispatch_does_not_reuse_changed_authority_contributions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent_id: str, fault: str,
) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    workspace, registry, program = prepare(tmp_path)
    instance = _supervisor(tmp_path, program, registry)
    original = supervisor.append_event

    def change_after_implementation(root: Path, kind: str, body: dict[str, Any]) -> Any:
        result = original(root, kind, body)
        if kind == "AWAITING_INDEPENDENT_VERIFICATION":
            roster = enrollment.load_registry(registry)
            current = roster.agents[agent_id]
            if fault == "narrowing":
                current.profile_narrowing = {"allowed_tools": ["Read"]}
            elif fault == "runtime":
                current.adapter = AdapterKind.CODEX
                current.runtime_substitution_authorized = True
            elif fault == "duplicate_role":
                roster.agents["duplicate"] = current.model_copy(update={"agent_id": "duplicate"})
            elif fault == "identity":
                current.agent_id = "different-principal"
            else:
                current.description = "metadata-only update retains the same authority"
            enrollment.persist_registry(registry, roster)
            if fault != "description":
                def forbidden(*args: Any, **kwargs: Any) -> Any:
                    raise AssertionError("STALE_AUTHORITY_REACHED_VERIFIER_SPAWN")
                monkeypatch.setattr(local_command, "run_child_to_completion", forbidden)
        return result

    monkeypatch.setattr(supervisor, "append_event", change_after_implementation)
    report = instance.start()
    assert report.complete is (fault == "description")
    assert report.launches_this_run == (2 if fault == "description" else 1)
    assert (workspace / "alpha.txt").exists()
