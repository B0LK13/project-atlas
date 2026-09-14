"""Completion D/E: actual boundary/argv construction, never a service launch.

The real loader and path checks stay live. OS launch, identity/event writes and
installation sinks are trapped; these tests are not service acceptance.
"""

from __future__ import annotations

import io
import json
import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from project_atlas.orchestration.program import cli, continuation_cli, service
from project_atlas.orchestration.program.models import ProgramStopReason
from project_atlas.orchestration.program.path_safety import ContainmentError


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("forbidden service/OS effect reached")


@pytest.fixture(autouse=True)
def no_os_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(service, "write_own_identity", _forbidden)
    monkeypatch.setattr(service, "append_event", _forbidden)


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    governed = tmp_path / "governed"
    workspace = governed / "worktrees" / "task"
    workspace.mkdir(parents=True)
    program = governed / "programs" / "approved.json"
    program.parent.mkdir()
    program.write_text(json.dumps({
        "schema_version": 1,
        "program": {
            "program_id": "boundary-service", "objective": "construction only",
            "approved_by": "fixture", "approval_reference": "completion-D-E",
            "workspace_root": str(workspace), "base_pin": "0" * 40,
            "tasks": [{
                "task_id": "task", "title": "fixture", "instruction": "never launch",
                "profile_ref": "impl", "mutation_paths": ["result.txt"],
                "surface_id": "fixture", "surface_semantic": "FIXTURE",
                "capabilities_required": ["IMPLEMENT"],
                "acceptance": [{"check_id": "file", "kind": "FILE_EXISTS",
                                "description": "fixture result", "path": "result.txt"}],
            }],
        },
        "profiles": {"impl": {
            "agent_id": "fixture-agent", "adapter": "local-command",
            "credential": "NOT_APPLICABLE", "capabilities": ["IMPLEMENT"],
            "adapter_options": {"argv": ["DO-NOT-LAUNCH"]},
        }},
    }))
    return governed, governed / "state", program


def _args(action: str, governed: Path, state: Path, program: Path,
          registry: Path | None = None) -> Any:
    argv = ["program", "service", action, "--program", str(program),
            "--state-root", str(state), "--governed-root", str(governed)]
    if registry is not None:
        argv += ["--registry", str(registry)]
    return cli._build_parser().parse_args(argv)


def _trap_writes(monkeypatch: pytest.MonkeyPatch) -> dict[Path, str]:
    captured: dict[Path, str] = {}

    def write(path: Path, content: str, *args: Any, **kwargs: Any) -> int:
        captured[path] = content
        return len(content)

    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    monkeypatch.setattr(Path, "chmod", lambda *a, **k: None)
    monkeypatch.setattr(Path, "write_text", write)
    monkeypatch.setattr(service, "_write_atomic", write)
    return captured


def test_cli_status_reads_sibling_layout_without_any_state_writes(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropping G between CLI and service reload rejects a valid same target."""
    governed, state, program = layout
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    report, code = cli.run_service(_args("status", governed, state, program))
    assert code == 0
    assert report["program_status"]["started"] is False
    assert report["service"] is None
    assert not state.exists()


def test_install_generated_commands_retain_boundary_and_absolute_registry(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated launcher losing G or rebinding registry on chdir is wrong."""
    governed, state, program = layout
    registry = governed.parent / "explicit-external-registry"
    registry.mkdir()
    monkeypatch.chdir(governed.parent)
    captured = _trap_writes(monkeypatch)
    report, code = cli.run_service(_args("install", governed, state, program, Path(registry.name)))
    assert code == 0 and report["activated"] is False
    script = captured[Path(report["launcher"])]
    command = script[script.index("exec ") + 5:].replace("\\\n", " ").strip()
    argv = shlex.split(command)
    args = cli._build_parser().parse_args(argv[argv.index("program"):-1])
    assert args.governed_root == governed
    assert args.state_root == state and args.program == program
    assert args.registry == registry
    unit = captured[Path(report["systemd_unit_file"])]
    stop = next(
        line.partition("=")[2] for line in unit.splitlines() if line.startswith("ExecStop=")
    )
    stop_argv = shlex.split(stop)
    stop_args = cli._build_parser().parse_args(stop_argv[stop_argv.index("program"):])
    assert stop_args.governed_root == governed
    assert stop_args.program == program and stop_args.state_root == state
    assert not state.exists(), "installation sinks must remain mocked"


def test_start_constructs_bound_child_argv_without_launch(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    governed, state, program = layout
    registry = governed.parent / "external-registry"
    registry.mkdir()
    monkeypatch.chdir(governed.parent)
    _trap_writes(monkeypatch)
    monkeypatch.setattr(service, "_bound_agents", lambda *a: ())
    monkeypatch.setattr(service, "clear_supervisor_stop", lambda *a: None)
    original_open = Path.open
    monkeypatch.setattr(Path, "open", lambda path, *a, **k: (
        io.StringIO() if path.name == "service.log" else original_open(path, *a, **k)
    ))

    class CapturedLaunch(Exception):
        pass

    observed: dict[str, Any] = {}

    def capture(argv: list[str], **kwargs: Any) -> Any:
        observed.update(argv=argv, cwd=kwargs["cwd"])
        raise CapturedLaunch

    monkeypatch.setattr(subprocess, "Popen", capture)
    with pytest.raises(CapturedLaunch):
        cli.run_service(_args("start", governed, state, program, Path(registry.name)))
    argv = observed["argv"]
    args = cli._build_parser().parse_args(argv[argv.index("program"):])
    assert args.governed_root == governed
    assert args.registry == registry and args.state_root == state
    assert args.program == program
    assert observed["cwd"] == str(governed / "worktrees/task")
    assert not state.exists()


@pytest.mark.parametrize("via_cli", [False, True])
def test_run_passes_boundary_to_each_supervisor_round(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, via_cli: bool,
) -> None:
    governed, state, program = layout
    observed: list[dict[str, Any]] = []
    identity = service.ServiceIdentity(
        123, "fixture-only", "boundary-service", str(program), "fixture"
    )
    monkeypatch.setattr(service, "write_own_identity", lambda *a: identity)
    monkeypatch.setattr(service, "append_event", lambda *a: None)

    class TrappedSupervisor:
        def __init__(self, loaded: Any, **kwargs: Any) -> None:
            observed.append(kwargs)

        def start(self) -> Any:
            return SimpleNamespace(stop_reason=ProgramStopReason.NO_ELIGIBLE_WORK,
                                   launches_this_run=0, complete=False)

    monkeypatch.setattr(service, "ProgramSupervisor", TrappedSupervisor)
    if via_cli:
        args = _args("run", governed, state, program)
        args.max_rounds = 2
        args.poll_seconds = 0
        args.allow_unregistered = True
        report, code = cli.run_service(args)
        assert code == 0
    else:
        report = service.run(state, program, governed_root=governed, max_rounds=2,
                             sleeper=lambda _: None)
    assert len(report["rounds"]) == len(observed) == 2
    assert all(item["governed_root"] == governed and item["state_root"] == state
               for item in observed)
    assert not state.exists()


@pytest.mark.parametrize("action", ["install", "start", "status", "run"])
@pytest.mark.parametrize("bad", ["state", "program_link", "workspace", "registry_link"])
def test_invalid_bindings_refused_before_any_effect(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, action: str, bad: str,
) -> None:
    governed, state, program = layout
    registry = None
    if bad == "state":
        state = governed.parent / "outside-state"
    elif bad == "program_link":
        link = program.with_name("linked.json")
        link.symlink_to(program)
        program = link
    elif bad == "workspace":
        raw = json.loads(program.read_text())
        raw["program"]["workspace_root"] = str(governed.parent)
        program.write_text(json.dumps(raw))
    else:
        target = governed / "registry-real"
        target.mkdir()
        registry = governed / "registry-link"
        registry.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    monkeypatch.setattr(Path, "write_text", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    monkeypatch.setattr(service, "clear_supervisor_stop", _forbidden)
    with pytest.raises(ContainmentError):
        getattr(service, action)(state, program, governed_root=governed, registry_root=registry)


@pytest.mark.parametrize("action", ["install", "start", "status", "run"])
def test_cli_does_not_preresolve_registry_link(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, action: str,
) -> None:
    governed, state, program = layout
    registry = governed / "registry"
    registry.symlink_to(governed, target_is_directory=True)
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    with pytest.raises(ContainmentError):
        cli.run_service(_args(action, governed, state, program, registry))


@pytest.mark.parametrize(
    "leaf", ["run-boundary-service.sh", "atlas-program-boundary-service.service"]
)
def test_install_checks_both_output_leaves_before_first_write(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, leaf: str,
) -> None:
    governed, state, program = layout
    directory = service.service_dir(state)
    directory.mkdir(parents=True)
    sentinel = governed.parent / "sentinel"
    sentinel.write_text("untouched")
    (directory / leaf).symlink_to(sentinel)
    monkeypatch.setattr(Path, "write_text", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    with pytest.raises(ContainmentError):
        service.install(state, program, governed_root=governed)
    assert sentinel.read_text() == "untouched"


def test_rollback_guidance_is_schema2_conditional_and_not_performed(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    governed, state, _ = layout
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    args = cli._build_parser().parse_args([
        "program", "continuation", "--state-root", str(state),
        "--governed-root", str(governed), "--action", "rollback",
    ])
    payload, code = continuation_cli.cmd_continuation(args)
    assert code == 0 and payload["performed"] is False
    assert payload["checkpoint_reader_schema"] == 2
    assert payload["automatic_migration"] is False
    assert payload["preconditions_verified"] is False
    assert payload["state_compatibility"] == "REQUIRES_COMPATIBLE_READER"
    procedure = "\n".join(payload["operator_procedure"])
    assert "--governed-root" in procedure and str(governed) in procedure
    assert "snapshot" in procedure.lower() and "compatible reader" in procedure.lower()
    assert "previous revision ignores" not in procedure
    assert not state.exists()


def test_default_boundary_stays_program_directory_not_common_ancestor(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    governed, state, program = layout
    legacy_program = governed / "approved.json"
    legacy_program.write_bytes(program.read_bytes())
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    assert service.status(state, legacy_program)["program_status"]["started"] is False
    with pytest.raises(ContainmentError):
        service.status(governed.parent / "outside-state", legacy_program)
    assert not state.exists()


def test_registry_required_before_service_identity_is_written(
    layout: tuple[Path, Path, Path],
) -> None:
    governed, state, program = layout
    with pytest.raises(service.ServiceError) as caught:
        service.run(state, program, governed_root=governed, allow_unregistered=False)
    assert caught.value.code == "REGISTRY_REQUIRED"
    assert not state.exists()


@pytest.mark.parametrize("action", ["install", "start", "status", "run"])
@pytest.mark.parametrize("leaf", ["service.json", "service.log"])
def test_service_leaf_links_rejected_before_effects(
    layout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, action: str, leaf: str,
) -> None:
    governed, state, program = layout
    directory = service.service_dir(state)
    directory.mkdir(parents=True)
    sentinel = governed / "sentinel"
    sentinel.write_text("unchanged")
    (directory / leaf).symlink_to(sentinel)
    monkeypatch.setattr(Path, "mkdir", _forbidden)
    monkeypatch.setattr(service, "_write_atomic", _forbidden)
    monkeypatch.setattr(service, "clear_supervisor_stop", _forbidden)
    with pytest.raises(ContainmentError):
        getattr(service, action)(state, program, governed_root=governed)
    assert sentinel.read_text() == "unchanged"
