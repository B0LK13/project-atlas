"""F01 / AT-013: disposable containment regression and positive controls."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from project_atlas.orchestration.program import approved_queue, continuation, store
from project_atlas.orchestration.program import resident as resident_module
from project_atlas.orchestration.program.adapters.claude_code import ClaudeCodeAdapter
from project_atlas.orchestration.program.capsule import build_capsule
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramError
from project_atlas.orchestration.program.path_safety import ContainmentError, child_path
from project_atlas.orchestration.program.reconciliation import reconcile_root
from project_atlas.orchestration.program.resident import ResidentDispatcher
from project_atlas.orchestration.program.store import write_evidence
from project_atlas.orchestration.program.supervisor import (
    ProgramSupervisor,
    build_default_adapters,
)


def _program(root: Path, workspace: Path) -> Path:
    path = root / "program.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "program": {
                    "program_id": "containment-fixture",
                    "objective": "F01 disposable control",
                    "approved_by": "fixture-operator",
                    "approval_reference": "F01 / AT-013",
                    "workspace_root": str(workspace),
                    "allow_unversioned_fixture": True,
                    "base_pin": "0" * 40,
                    "limits": {"max_cycles": 8, "idle_sleep_seconds": 0.0},
                    "tasks": [
                        {
                            "task_id": "fixture-task",
                            "title": "F01 control",
                            "instruction": "fixture",
                            "profile_ref": "fixture",
                            "mutation_paths": [],
                            "surface_id": "fixture",
                            "surface_semantic": "FIXTURE",
                            "capabilities_required": ["IMPLEMENT"],
                            "acceptance": [
                                {
                                    "check_id": "exit",
                                    "kind": "COMMAND",
                                    "argv": [sys.executable, "-c", "pass"],
                                    "description": "disposable interpreter exited",
                                }
                            ],
                        }
                    ],
                },
                "profiles": {
                    "fixture": {
                        "agent_id": "fixture-worker",
                        "adapter": "local-command",
                        "credential": "NOT_APPLICABLE",
                        "capabilities": ["IMPLEMENT"],
                        "adapter_options": {"argv": [sys.executable, "-c", "print('F01 control')"]},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _raw_queue(queue: Path, program: Path, state: Path) -> None:
    queue.mkdir(parents=True, exist_ok=True)
    entry = approved_queue.QueueEntry(
        program_id="containment-fixture",
        program_path=str(program),
        program_sha256=hashlib.sha256(program.read_bytes()).hexdigest(),
        state_root=str(state),
        admitted_by="fixture-operator",
        reference="F01",
    )
    (queue / approved_queue.QUEUE_NAME).write_text(
        approved_queue.ApprovedWorkQueue(entries={entry.program_id: entry}).model_dump_json(),
        encoding="utf-8",
    )


def test_dispatcher_refuses_queue_outside_default_governed_root(tmp_path: Path) -> None:
    governed = tmp_path / "governed"
    outside = tmp_path / "outside"
    governed.mkdir()
    outside.mkdir()
    with pytest.raises(ProgramError):
        ResidentDispatcher(root=governed, queue_root=outside, checkout=governed)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("name", ["../escaped.json", "nested/../../escaped.json"])
def test_evidence_refuses_traversal_components(tmp_path: Path, name: str) -> None:
    with pytest.raises(ProgramError):
        write_evidence(tmp_path / "governed", name, {"fixture": True})


def test_evidence_refuses_symlinked_state_directory(tmp_path: Path) -> None:
    governed = tmp_path / "governed"
    outside = tmp_path / "outside"
    governed.mkdir()
    outside.mkdir()
    (governed / ".atlas").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProgramError):
        write_evidence(governed, "escaped.json", {"fixture": True})
    assert list(outside.iterdir()) == []


def test_relative_registry_binding_survives_chdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    program = _program(tmp_path, workspace)
    monkeypatch.chdir(tmp_path)
    dispatcher = ResidentDispatcher(
        root=tmp_path,
        queue_root=tmp_path / "queue",
        checkout=tmp_path,
        registry_root=Path("registry"),
    )
    supervisor = ProgramSupervisor(load_program(program), registry_root=Path("registry"))
    monkeypatch.chdir(workspace)
    assert dispatcher.registry_root == tmp_path / "registry"
    assert supervisor.registry_root == tmp_path / "registry"


@pytest.mark.parametrize("consumer", ["dispatch", "capsule", "reconcile"])
def test_queue_cannot_select_outside_state(tmp_path: Path, consumer: str) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    workspace = governed / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    program = _program(governed, workspace)
    queue = governed / "queue"
    _raw_queue(queue, program, outside)
    if consumer == "dispatch":
        result = ResidentDispatcher(root=governed, queue_root=queue, checkout=governed).tick()
        assert result.launched == 0
        assert result.queue_error_code == "PROGRAM_PATH_CONTAINMENT"
    elif consumer == "capsule":
        with pytest.raises(ProgramError):
            build_capsule(governed, for_worker_id="fixture", queue_root=queue)
    else:
        with pytest.raises(ProgramError):
            reconcile_root(governed, our_worker_id="fixture", queue_root=queue)
    assert list(outside.iterdir()) == []


def test_queued_program_cannot_select_outside_workspace(tmp_path: Path) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    program = _program(governed, outside)
    queue = governed / "queue"
    _raw_queue(queue, program, governed / "state")
    result = ResidentDispatcher(root=governed, queue_root=queue, checkout=governed).tick()
    assert result.launched == 0
    assert not (governed / "state").exists()
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "reader",
    [
        store.load_state,
        store.read_events,
        continuation.list_envelopes,
        continuation.list_checkpoints,
    ],
)
def test_state_readers_refuse_symlinked_state(tmp_path: Path, reader: object) -> None:
    governed = tmp_path / "governed"
    outside = tmp_path / "outside"
    governed.mkdir()
    outside.mkdir()
    (governed / ".atlas").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProgramError):
        reader(governed)  # type: ignore[operator]


def test_atomic_write_refuses_preplanted_temp_symlink(tmp_path: Path) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("untouched", encoding="utf-8")
    target = governed / "state.json"
    target.with_suffix(".json.tmp").symlink_to(outside)
    with pytest.raises(ProgramError):
        store.write_json_atomic(target, {"fixture": True})
    assert outside.read_text(encoding="utf-8") == "untouched"
    assert not target.exists()


def test_explicit_sibling_boundary_executes_approved_program_once(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    program = _program(tmp_path, workspace)
    queue = tmp_path / "queue"
    state = tmp_path / "state"
    dispatcher_root = tmp_path / "dispatcher"
    approved_queue.admit(
        queue,
        program_path=program,
        program_id="containment-fixture",
        state_root=state,
        admitted_by="fixture-operator",
        reference="F01",
        governed_root=tmp_path,
    )
    dispatcher = ResidentDispatcher(
        root=dispatcher_root,
        queue_root=queue,
        checkout=tmp_path,
        governed_root=tmp_path,
    )
    result = dispatcher.tick()
    assert result.launched == 1
    assert result.report is not None and result.report.complete
    assert dispatcher.tick().launched == 0
    assert (
        approved_queue.load_queue(queue, governed_root=tmp_path)
        .entries["containment-fixture"]
        .status
        is approved_queue.QueueEntryStatus.COMPLETE
    )
    capsule = build_capsule(
        dispatcher_root, for_worker_id="fixture-worker", queue_root=queue, governed_root=tmp_path
    )
    assert any(task.task_id == "fixture-task" for task in capsule.tasks)
    assert str(state) in capsule.state_roots_scanned
    verdicts = reconcile_root(
        state, our_worker_id="fixture-worker", queue_root=queue, governed_root=tmp_path
    )
    assert len(verdicts) == 1 and not verdicts[0].launchable


@pytest.mark.parametrize(
    "component",
    [
        "/absolute",
        "../escape",
        "ok/../escape",
        "C:/escape",
        "C:escape",
        "\\\\server\\share",
        "dir\\escape",
        "dir/stream:ads",
        "file:stream",
    ],
)
def test_untrusted_components_are_refused(tmp_path: Path, component: str) -> None:
    with pytest.raises(ContainmentError):
        child_path(tmp_path, component)


def test_absolute_evidence_component_is_refused_even_inside_root(tmp_path: Path) -> None:
    target = store.evidence_dir(tmp_path) / "target.json"
    with pytest.raises(ContainmentError):
        store.write_evidence(tmp_path, str(target), {"fixture": True})
    assert not target.exists()


@pytest.mark.parametrize("kind", ["state", "events", "envelope", "checkpoint", "queue"])
def test_readers_refuse_leaf_symlinks(tmp_path: Path, kind: str) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    root = tmp_path / "governed"
    paths = {
        "state": store.state_path(root),
        "events": store.events_path(root),
        "envelope": continuation.envelopes_dir(root) / "fixture.envelope.json",
        "checkpoint": continuation.checkpoints_dir(root) / "fixture.checkpoint.json",
        "queue": root / approved_queue.QUEUE_NAME,
    }
    path = paths[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside)
    readers = {
        "state": store.load_state,
        "events": store.read_events,
        "envelope": continuation.list_envelopes,
        "checkpoint": continuation.list_checkpoints,
        "queue": approved_queue.load_queue,
    }
    with pytest.raises(ContainmentError):
        readers[kind](root)
    assert outside.read_text(encoding="utf-8") == "{}"


def test_workspace_rebinding_after_load_refuses_before_state_write(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    program = _program(tmp_path, workspace)
    loaded = load_program(program)
    workspace.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ContainmentError):
        ProgramSupervisor(loaded, state_root=tmp_path / "state")
    assert not (tmp_path / "state").exists()
    assert list(outside.iterdir()) == []


def test_supervisor_rechecks_workspace_after_construction(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    supervisor = ProgramSupervisor(load_program(_program(tmp_path, workspace)))
    workspace.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ContainmentError):
        _ = supervisor.workspace


def test_explicit_outside_registry_stays_bound(tmp_path: Path) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    workspace = governed / "workspace"
    workspace.mkdir()
    registry = tmp_path / "operator-registry"
    dispatcher = ResidentDispatcher(
        root=governed, queue_root=governed / "queue", checkout=governed, registry_root=registry
    )
    supervisor = ProgramSupervisor(
        load_program(_program(governed, workspace)), registry_root=registry
    )
    assert dispatcher.registry_root == supervisor.registry_root == registry


@pytest.mark.parametrize("name", ["dispatcher/heartbeat.json", "decisions/bad.decision.json"])
def test_capsule_refuses_linked_auxiliary_state(tmp_path: Path, name: str) -> None:
    root = tmp_path / "governed"
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    target = store.state_dir(root) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside)
    with pytest.raises(ContainmentError):
        build_capsule(root, for_worker_id="fixture")


@pytest.mark.parametrize("slot", ["queue", "state", "program"])
@pytest.mark.parametrize("form", ["outside", "symlink", "traversal"])
def test_admission_refuses_escape_before_any_queue_write(
    tmp_path: Path,
    slot: str,
    form: str,
) -> None:
    governed = tmp_path / "governed"
    governed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    program = _program(governed, governed)
    outside_program = _program(outside, outside)
    queue, state = governed / "queue", governed / "state"
    external = outside_program if slot == "program" else outside
    if form == "outside":
        target = external
    elif form == "traversal":
        target = governed / ".." / "outside"
        if slot == "program":
            target /= "program.json"
    else:
        target = governed / "alias"
        target.symlink_to(external, target_is_directory=slot != "program")
    queue = target if slot == "queue" else queue
    state = target if slot == "state" else state
    program = target if slot == "program" else program
    before = outside_program.read_bytes()
    with pytest.raises(ContainmentError):
        approved_queue.admit(
            queue,
            program_path=program,
            program_id="containment-fixture",
            state_root=state,
            admitted_by="fixture",
            reference="F01",
            governed_root=governed,
        )
    assert not (governed / "queue").exists()
    assert not (outside / approved_queue.QUEUE_NAME).exists()
    assert outside_program.read_bytes() == before


def test_pinned_program_path_cannot_be_substituted_by_symlink(tmp_path: Path) -> None:
    program = _program(tmp_path, tmp_path)
    queue = tmp_path / "queue"
    approved_queue.admit(
        queue,
        program_path=program,
        program_id="containment-fixture",
        state_root=tmp_path / "state",
        admitted_by="fixture",
        reference="F01",
        governed_root=tmp_path,
    )
    copy = tmp_path / "copy.json"
    program.rename(copy)
    program.symlink_to(copy)
    result = ResidentDispatcher(root=tmp_path, queue_root=queue, checkout=tmp_path).tick()
    assert result.launched == 0
    assert result.queue_error_code == "PROGRAM_PATH_CONTAINMENT"
    assert not (tmp_path / "state").exists()


def test_reparse_attribute_is_refused_on_non_windows_test_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic reparse metadata control, not a native Windows execution proof."""
    import stat
    from types import SimpleNamespace

    real_lstat = Path.lstat
    target = tmp_path / "reparse"
    target.mkdir()

    def reparse_lstat(path: Path, *args: object, **kwargs: object) -> object:
        if path == target:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", reparse_lstat)
    with pytest.raises(ContainmentError):
        child_path(tmp_path, "reparse/child")


def test_same_root_default_boundary_remains_executable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    program = _program(tmp_path, workspace)
    approved_queue.admit(
        tmp_path, program_path=program, program_id="containment-fixture", state_root=tmp_path,
        admitted_by="fixture", reference="F01 same-root control",
    )
    dispatcher = ResidentDispatcher(root=tmp_path, queue_root=tmp_path, checkout=tmp_path)
    result = dispatcher.tick()
    assert result.launched == 1
    assert result.report is not None and result.report.complete
    assert dispatcher.tick().launched == 0


def test_registry_leaf_link_is_refused_by_operator_reader(tmp_path: Path) -> None:
    from project_atlas.orchestration.program.enrollment import load_registry, registry_path

    registry = tmp_path / "registry"
    outside = tmp_path / "outside.json"
    outside.write_text('{"agents": {}}')
    target = registry_path(registry)
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    before = outside.read_bytes()
    with pytest.raises(ContainmentError):
        load_registry(registry)
    assert outside.read_bytes() == before


@pytest.mark.parametrize("reader", ["load", "list", "answer", "withdraw", "blocked"])
def test_decision_leaf_link_is_refused_at_shared_boundary(tmp_path: Path, reader: str) -> None:
    from project_atlas.orchestration.program import decisions

    root = tmp_path / "governed"
    request, created = decisions.raise_decision(
        root, program_id="fixture", task_id="task", kind=decisions.DecisionKind.PERMISSION,
        subject="fixture", question="fixture permission", requested_action="nothing",
        worker_id="fixture", session_id="fixture-session",
    )
    assert created
    target = decisions._path_for(root, request.decision_id)
    outside = tmp_path / "outside.json"
    target.rename(outside)
    target.symlink_to(outside)
    before = outside.read_bytes()
    with pytest.raises(ContainmentError):
        if reader == "load":
            decisions.load_decision(root, request.decision_id)
        elif reader == "list":
            decisions.list_decisions(root)
        elif reader == "answer":
            decisions.record_answer(root, request.decision_id, answered_by="fixture", answer="no")
        elif reader == "withdraw":
            decisions.withdraw_decision(root, request.decision_id, reason="fixture")
        else:
            decisions.blocked_task_ids(root)
    assert outside.read_bytes() == before


def test_command_projection_refuses_transcript_leaf_link(tmp_path: Path) -> None:
    from project_atlas.orchestration.program.continuation_projection import _capture_commands
    from project_atlas.orchestration.program.store import AttemptRecord, evidence_dir

    root = tmp_path / "governed"
    directory = evidence_dir(root)
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"argv": ["NEVER_OBSERVED_COMMAND"], "exit_status": 0}')
    (directory / "fixture.transcript.json").symlink_to(outside)
    attempt = AttemptRecord(
        attempt_id="fixture", task_id="task", attempt_number=1, idempotency_key="fixture",
        profile_id="fixture", agent_id="fixture", adapter="local-command",
        profile_digest="0" * 64, base_pin="0" * 40,
        evidence_paths=("fixture.transcript.json",),
    )
    with pytest.raises(ContainmentError):
        _capture_commands(root, attempt)


@pytest.mark.parametrize("outside", [False, True])
def test_artifact_projection_refuses_planted_link(tmp_path: Path, outside: bool) -> None:
    from project_atlas.orchestration.program.continuation_projection import _capture_artifacts
    from project_atlas.orchestration.program.models import AcceptanceCheck, AcceptanceKind
    from project_atlas.orchestration.program.store import AttemptRecord

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = (tmp_path if outside else workspace) / "source.txt"
    target.write_text("fixture")
    (workspace / "result.txt").symlink_to(target)
    task = load_program(_program(tmp_path, workspace)).program.tasks[0]
    task = task.model_copy(update={"acceptance": (AcceptanceCheck(
        check_id="result", kind=AcceptanceKind.FILE_EXISTS, path="result.txt",
        description="fixture artifact",
    ),)})
    attempt = AttemptRecord(
        attempt_id="fixture", task_id=task.task_id, attempt_number=1, idempotency_key="fixture",
        profile_id="fixture", agent_id="fixture", adapter="local-command",
        profile_digest="0" * 64, base_pin="0" * 40,
        acceptance_detail=({"check_id": "result", "passed": True},),
    )
    with pytest.raises(ContainmentError):
        _capture_artifacts(task, attempt, workspace)
    assert target.read_text() == "fixture"


@pytest.mark.parametrize("suffix", [".started", ".transcript.json"])
def test_local_fixture_leaf_link_refuses_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    from project_atlas.orchestration.program.adapters import local_command
    from project_atlas.orchestration.program.adapters.base import AdapterRequest

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    loaded = load_program(_program(tmp_path, workspace))
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("preserve this fixture")
    (evidence / ("known-attempt" + suffix)).symlink_to(outside)
    request = AdapterRequest(
        program_id="fixture", task_id="fixture-task", attempt_id="known-attempt",
        attempt_number=1, idempotency_key="fixture", instruction="fixture",
        workspace=workspace, profile=loaded.effective_profile("fixture-task"),
        session_id="fixture", resume_session_id=None, timeout_seconds=1, evidence_dir=evidence,
    )

    def forbidden_child(*args: object, **kwargs: object) -> None:
        pytest.fail("a planted evidence leaf reached the child-launch boundary")

    monkeypatch.setattr(local_command, "run_child_to_completion", forbidden_child)
    with pytest.raises(ContainmentError):
        local_command.LocalCommandAdapter((sys.executable, "-c", "pass")).run(request)
    assert outside.read_text() == "preserve this fixture"


def test_pause_leaf_link_is_not_read_as_operator_authority(tmp_path: Path) -> None:
    from project_atlas.orchestration.sdk import host

    root = tmp_path / "governed"
    outside = tmp_path / "outside.json"
    outside.write_text('{"program_id":"fixture","requested_by":"foreign"}')
    target = host.host_state_dir(store.state_dir(root)) / host.SUPERVISOR_PAUSE_NAME
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(ContainmentError):
        host.read_supervisor_pause(store.state_dir(root), program_id="fixture")


def test_control_pause_refuses_linked_host_directory_without_outside_write(tmp_path: Path) -> None:
    from project_atlas.orchestration.program import control
    from project_atlas.orchestration.sdk import host

    root = tmp_path / "governed"
    outside = tmp_path / "outside"
    outside.mkdir()
    store.persist_state(root, store.ProgramStateRecord(
        program_id="fixture", program_digest="a" * 64, base_pin="b" * 40
    ))
    target = host.host_state_dir(store.state_dir(root))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ContainmentError):
        control.pause(root, requested_by="fixture")
    assert list(outside.iterdir()) == []


def test_service_identity_link_is_refused_without_service_action(tmp_path: Path) -> None:
    from project_atlas.orchestration.program import service

    root = tmp_path / "governed"
    outside = tmp_path / "outside.json"
    outside.write_text('{"pid":0,"program_id":"foreign","program_path":"fixture"}')
    target = service.identity_path(root)
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(ContainmentError):
        service.read_identity(root)


@pytest.mark.parametrize("sink", ["temporary", "events"])
def test_planted_hardlink_never_modifies_outside_inode(tmp_path: Path, sink: str) -> None:
    root = tmp_path / "governed"
    outside = tmp_path / "outside.txt"
    outside.write_text("immutable fixture")
    target = store.state_path(root) if sink == "temporary" else store.events_path(root)
    target.parent.mkdir(parents=True)
    link = target.with_name(target.name + ".tmp") if sink == "temporary" else target
    os.link(outside, link)
    with pytest.raises(ContainmentError):
        if sink == "temporary":
            store.write_json_atomic(target, {"must_not_write_outside": True})
        else:
            store.append_event(root, "must_not_append_outside", {})
    assert outside.read_text() == "immutable fixture"


def test_resident_supported_provider_profile_reaches_supervisor_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resident route must not reject an adapter it already implements."""
    program = _program(tmp_path, tmp_path)
    payload = json.loads(program.read_text())
    payload["profiles"]["fixture"].update(
        adapter="claude-code", credential="ANTHROPIC_API_KEY_ENV", adapter_options={}
    )
    payload["program"]["allow_unversioned_fixture"] = False
    program.write_text(json.dumps(payload))
    queue = tmp_path / "queue"
    _raw_queue(queue, program, tmp_path / "state")
    monkeypatch.setattr(
        resident_module,
        "_git_revision",
        lambda checkout: (
            "7b9ace01f0bc06931f1191f8912abda1f7935953",
            "2214d53a79094c16d96dd07a41341d3f701f1b69",
        ),
    )
    reached = False

    def provider_factory(*args: object, **kwargs: object) -> None:
        nonlocal reached
        reached = True
        raise RuntimeError("provider factory reached")

    dispatcher = ResidentDispatcher(
        root=tmp_path,
        queue_root=queue,
        checkout=tmp_path,
        supervisor_factory=provider_factory,
    )
    with pytest.raises(RuntimeError, match="provider factory reached"):
        dispatcher.tick()
    assert reached


def test_provider_profile_uses_shipped_claude_adapter_factory(tmp_path: Path) -> None:
    """The resident handoff targets the shipped adapter, not a shell fallback."""
    program = _program(tmp_path, tmp_path)
    payload = json.loads(program.read_text())
    payload["profiles"]["fixture"].update(
        adapter="claude-code", credential="ANTHROPIC_API_KEY_ENV", adapter_options={}
    )
    payload["program"]["allow_unversioned_fixture"] = False
    program.write_text(json.dumps(payload))
    loaded = load_program(program)
    adapters = build_default_adapters(loaded)
    assert isinstance(adapters["fixture"], ClaudeCodeAdapter)
