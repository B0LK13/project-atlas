"""AS-ORCH-001D-R6 Windows-safe MDA version-probe / launch-parity."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from tests.orchestration_control_plane import (
    MDA_FIXTURE,
    bind_test_mda_pipeline,
    explicit_test_mda_provider,
)
from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _request_prompt,
    _target_payload,
    _workspace,
)

from project_atlas.agent_control.runtime import (
    ControlPlaneError,
    ensure_control_plane_importable,
    mda_version_probe_argv,
    probe_mda_version,
    resolve_production_mda_provider,
)
from project_atlas.agent_control.trusted_argv import resolve_executable_argv
from project_atlas.orchestration.agent_transport import ProcessRunRequest
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import (
    DispatchStatus,
    run_dispatch_once,
    submit_target_result,
)


def _write_script(directory: Path, *, shebang: str, version: str, name: str = "mda") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        f"{shebang}\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        f"    print({version!r})\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _win32_createprocess_guard(script: Path):
    real_run = subprocess.run
    resolved = script.expanduser().resolve()

    def guarded(argv: object, *args: object, **kwargs: object):
        command = list(argv) if isinstance(argv, (list, tuple)) else [argv]
        if command and Path(str(command[0])).expanduser().resolve() == resolved:
            raise OSError(193, "WinError 193 %1 is not a valid Win32 application")
        return real_run(argv, *args, **kwargs)

    return guarded


def test_trusted_argv_implementation_is_shared() -> None:
    ensure_control_plane_importable()
    from internal.process_runner import resolve_executable_argv as sibling

    assert sibling is resolve_executable_argv


def test_r5_direct_shebang_createprocess_is_the_windows_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_script(
        tmp_path / "opt" / "bin",
        shebang="#!/usr/bin/env python3",
        version="mda 1.2.3",
    )
    monkeypatch.setattr(subprocess, "run", _win32_createprocess_guard(script))
    with pytest.raises(OSError, match="193"):
        subprocess.run(
            [str(script), "--version"],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
    assert probe_mda_version(script) == "mda 1.2.3"
    argv = mda_version_probe_argv(script)
    assert argv == [sys.executable, str(script.resolve()), "--version"]
    assert argv[0] != str(script)


def test_python_shebang_probe_uses_current_runtime(tmp_path: Path) -> None:
    for shebang in ("#!/usr/bin/env python3", "#!/usr/bin/python3"):
        script = _write_script(
            tmp_path / shebang.replace("/", "_").replace(" ", "_"),
            shebang=shebang,
            version="mda 9.9.9",
        )
        argv = resolve_executable_argv(str(script))
        assert argv == [sys.executable, str(script.resolve())]
        assert probe_mda_version(script) == "mda 9.9.9"


def test_explicit_fixture_version_probe_uses_trusted_python() -> None:
    argv = mda_version_probe_argv(MDA_FIXTURE)
    assert argv == [sys.executable, str(MDA_FIXTURE.resolve()), "--version"]
    provider = explicit_test_mda_provider()
    assert provider.source == "test_injection"
    assert "mock" in provider.version.lower()
    assert probe_mda_version(MDA_FIXTURE) == provider.version


def test_explicit_fixture_normalization_argv_matches_probe() -> None:
    ensure_control_plane_importable()
    from internal.normalization import NormalizationSettings, build_command

    raw = Path("/tmp/raw-event.md")
    settings = NormalizationSettings(
        mda_command=str(MDA_FIXTURE.resolve()),
        skill="atlas-governed-work",
        skill_dir=None,
        provider="test",
        timeout_seconds=10,
        retries=0,
        output_mode="sibling",
        output_dir=None,
        verify=True,
        record_command=True,
        enabled=True,
    )
    command = build_command(settings, raw)
    prefix = resolve_executable_argv(str(MDA_FIXTURE.resolve()))
    assert command[:2] == prefix
    assert command[:2] == [sys.executable, str(MDA_FIXTURE.resolve())]
    assert command[-1] == str(raw)
    assert "--in-place" not in command


def test_explicit_fixture_completes_canonical_test_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bind_test_mda_pipeline(monkeypatch)
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]
        submit_target_result(
            captured["id"],
            _target_payload(f"d.{captured['id']}"),
            root=workspace,
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.target_receipt_verified is True
    assert receipt.source_acknowledged is True


def test_production_still_rejects_repo_fixture_and_mock_version(tmp_path: Path) -> None:
    with pytest.raises(ControlPlaneError) as fixture:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(MDA_FIXTURE)},
            which=lambda _name: None,
        )
    assert fixture.value.code == "PIPELINE_UNAVAILABLE"
    mock = _write_script(
        tmp_path / "opt" / "bin",
        shebang="#!/usr/bin/env python3",
        version="mda 0.2.9-mock",
    )
    with pytest.raises(ControlPlaneError) as mocked:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(mock)},
            which=lambda _name: None,
        )
    assert mocked.value.code == "PIPELINE_UNAVAILABLE"


def test_production_accepts_authorized_python_shebang_helper(tmp_path: Path) -> None:
    trusted = _write_script(
        tmp_path / "opt" / "bin",
        shebang="#!/usr/bin/env python3",
        version="mda 1.8.0",
    )
    provider = resolve_production_mda_provider(
        environ={"ATLAS_MDA_COMMAND": str(trusted)},
        which=lambda _name: None,
    )
    assert provider.source == "operator_config"
    assert provider.version == "mda 1.8.0"
    assert provider.command == trusted.resolve()


def test_native_executable_probe_is_direct() -> None:
    native = Path(sys.executable)
    argv = mda_version_probe_argv(native)
    assert argv == [str(native), "--version"] or argv == [sys.executable, "--version"]
    assert argv[0] != native.name
    version = probe_mda_version(native)
    assert version


def test_missing_executable_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing-mda"
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(missing)},
            which=lambda _name: None,
        )
    assert caught.value.code == "PIPELINE_UNAVAILABLE"
    with pytest.raises(ControlPlaneError) as probe:
        probe_mda_version(missing)
    assert probe.value.code == "PIPELINE_UNAVAILABLE"


def test_non_python_shebang_is_not_substituted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "mda"
    script.write_text("#!/bin/sh\necho unsafe\n", encoding="utf-8")
    script.chmod(0o755)
    assert resolve_executable_argv(str(script)) == [str(script)]
    monkeypatch.setattr(subprocess, "run", _win32_createprocess_guard(script))
    with pytest.raises(ControlPlaneError) as caught:
        probe_mda_version(script)
    assert caught.value.code == "PIPELINE_UNAVAILABLE"


def test_malformed_and_unexpected_env_shebang_fail_closed(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.write_text("#!\n", encoding="utf-8")
    empty.chmod(0o755)
    assert resolve_executable_argv(str(empty)) == [str(empty)]
    smuggle = tmp_path / "smuggle"
    smuggle.write_text("#!/usr/bin/env not-python\n", encoding="utf-8")
    smuggle.chmod(0o755)
    with pytest.raises(ValueError, match="unexpected"):
        resolve_executable_argv(str(smuggle))
    with pytest.raises(ControlPlaneError) as caught:
        probe_mda_version(smuggle)
    assert caught.value.code == "PIPELINE_UNAVAILABLE"


def test_shebang_does_not_grant_production_authority(tmp_path: Path) -> None:
    fixtureish = tmp_path / "repo" / "tests" / "fixtures" / "bin"
    script = _write_script(fixtureish, shebang="#!/usr/bin/env python3", version="mda 1.0.0")
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(script)},
            which=lambda _name: None,
        )
    assert caught.value.code == "PIPELINE_UNAVAILABLE"
