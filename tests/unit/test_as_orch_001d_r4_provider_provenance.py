"""AS-ORCH-001D-R4 production MDA provider provenance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.orchestration_control_plane import (
    MDA_FIXTURE,
    bind_test_mda_pipeline,
    explicit_test_mda_provider,
    install_managed_control_plane,
)
from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _workspace,
)

from project_atlas.agent_control.runtime import (
    ControlPlaneError,
    MdaProvider,
    prepare_event_pipeline,
    resolve_mda_command,
    resolve_production_mda_provider,
    scoped_mda_environment,
)
from project_atlas.orchestration.agent_transport import ProcessRunRequest
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import DispatchStatus, run_dispatch_once


def _write_mda(directory: Path, *, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "mda"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        f"    print({version!r})\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _assert_pipeline_unavailable(exc: ControlPlaneError) -> None:
    assert exc.code == "PIPELINE_UNAVAILABLE"


def test_production_resolver_fails_closed_when_env_and_path_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(ControlPlaneError) as caught:
        resolve_mda_command()
    _assert_pipeline_unavailable(caught.value)


def test_explicit_real_looking_trusted_provider_is_accepted(tmp_path: Path) -> None:
    trusted = _write_mda(tmp_path / "opt" / "bin", version="mda 1.2.3")
    provider = resolve_production_mda_provider(
        environ={"ATLAS_MDA_COMMAND": str(trusted)},
        which=lambda _name: None,
    )
    assert provider.source == "operator_config"
    assert provider.command == trusted.resolve()
    assert provider.version == "mda 1.2.3"
    assert len(provider.path_digest) == 64
    assert "mock" not in provider.version.lower()


def test_path_real_provider_is_accepted(tmp_path: Path) -> None:
    trusted = _write_mda(tmp_path / "opt" / "bin", version="mda 1.4.0")
    provider = resolve_production_mda_provider(
        environ={},
        which=lambda name: str(trusted) if name == "mda" else None,
    )
    assert provider.source == "PATH"
    assert provider.command == trusted.resolve()
    assert provider.version == "mda 1.4.0"


def test_repository_fixture_rejected_as_operator_config() -> None:
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(MDA_FIXTURE)},
            which=lambda _name: None,
        )
    _assert_pipeline_unavailable(caught.value)


def test_repository_fixture_rejected_from_path() -> None:
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={},
            which=lambda name: str(MDA_FIXTURE) if name == "mda" else None,
        )
    _assert_pipeline_unavailable(caught.value)


def test_production_resolver_never_auto_selects_repo_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(ControlPlaneError) as caught:
        resolved = resolve_mda_command()
        raise AssertionError(f"fixture leaked into production: {resolved}")
    _assert_pipeline_unavailable(caught.value)
    assert MDA_FIXTURE.is_file()


def test_mock_version_is_rejected_in_production(tmp_path: Path) -> None:
    mock = _write_mda(tmp_path / "opt" / "bin", version="mda 0.2.9-mock")
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(mock)},
            which=lambda _name: None,
        )
    _assert_pipeline_unavailable(caught.value)


def test_explicit_test_harness_provider_is_not_production_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = explicit_test_mda_provider()
    assert provider.source == "test_injection"
    assert "mock" in provider.version.lower()
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(ControlPlaneError):
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(MDA_FIXTURE)},
            which=lambda _name: None,
        )
    with pytest.raises(ControlPlaneError) as caught:
        prepare_event_pipeline()
    _assert_pipeline_unavailable(caught.value)


def test_environment_restored_after_successful_event(tmp_path: Path) -> None:
    trusted = _write_mda(tmp_path / "opt" / "bin", version="mda 1.2.3")
    provider = MdaProvider(
        command=trusted,
        source="operator_config",
        version="mda 1.2.3",
        path_digest="a" * 64,
    )
    os.environ["ATLAS_MDA_COMMAND"] = "prior-operator-value"
    try:
        with scoped_mda_environment(provider):
            assert os.environ["ATLAS_MDA_COMMAND"] == str(trusted)
        assert os.environ["ATLAS_MDA_COMMAND"] == "prior-operator-value"
    finally:
        os.environ.pop("ATLAS_MDA_COMMAND", None)


def test_environment_restored_after_failing_event(tmp_path: Path) -> None:
    trusted = _write_mda(tmp_path / "opt" / "bin", version="mda 1.2.3")
    provider = MdaProvider(
        command=trusted,
        source="operator_config",
        version="mda 1.2.3",
        path_digest="a" * 64,
    )
    os.environ.pop("ATLAS_MDA_COMMAND", None)
    with (
        pytest.raises(RuntimeError, match="pipeline-boom"),
        scoped_mda_environment(provider),
    ):
        assert os.environ["ATLAS_MDA_COMMAND"] == str(trusted)
        raise RuntimeError("pipeline-boom")
    assert "ATLAS_MDA_COMMAND" not in os.environ


def test_prepare_event_pipeline_is_production_only_and_does_not_mutate_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )
    explicit_test_mda_provider()
    with pytest.raises(ControlPlaneError) as caught:
        prepare_event_pipeline()
    _assert_pipeline_unavailable(caught.value)
    assert "ATLAS_MDA_COMMAND" not in os.environ


def test_mock_provider_cannot_create_canonical_completion_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("ATLAS_MDA_COMMAND", str(MDA_FIXTURE))
    stage_result(_payload(), root=workspace)
    runner = ScriptedRunner(_ok_outcome())
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "PIPELINE_UNAVAILABLE"
    assert receipt.process_started is False
    assert receipt.source_acknowledged is False
    assert receipt.result_staged is False
    assert receipt.next_handoff_autodispatched is False
    assert receipt.target_receipt_id is None
    assert list((workspace / ".atlas" / "receipts").glob("ASR-*.json")) == []
    assert runner.requests == []


def test_missing_provider_fails_before_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = install_managed_control_plane(tmp_path)
    (workspace / "AGENTS.md").write_text("# Atlas\n", encoding="utf-8")
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "project-atlas"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )
    stage_result(_payload(), root=workspace)
    runner = ScriptedRunner(_ok_outcome())
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "PIPELINE_UNAVAILABLE"
    assert receipt.process_started is False
    assert runner.requests == []


def test_cursor_child_does_not_inherit_test_mda(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind_test_mda_pipeline(monkeypatch)
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("ATLAS_MDA_COMMAND", str(MDA_FIXTURE))
    monkeypatch.setenv("CURSOR_API_KEY", "secret")
    stage_result(_payload(), root=workspace)
    seen: dict[str, object] = {}

    def on_run(request: ProcessRunRequest) -> None:
        env = request.env
        seen["has_mda"] = "ATLAS_MDA_COMMAND" in env
        seen["has_mock"] = "MDA_MOCK_MODE" in env
        seen["has_cursor"] = env.get("CURSOR_API_KEY") == "secret"
        raise RuntimeError("stop-before-submit")

    with pytest.raises(RuntimeError, match="stop-before-submit"):
        run_dispatch_once(
            root=workspace,
            runner=ScriptedRunner(_ok_outcome(), on_run=on_run),
        )
    assert seen["has_mda"] is False
    assert seen["has_mock"] is False
    assert seen["has_cursor"] is True


def test_runtime_has_no_production_fixture_fallback() -> None:
    text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "project_atlas"
        / "agent_control"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    assert "os.environ[MDA_ENV_VAR] = str(mda)" not in text
    assert 'os.environ["ATLAS_MDA_COMMAND"] = str(mda)' not in text
    assert "if fixture.is_file():" not in text


def test_fixture_on_path_is_not_used_by_production_resolver() -> None:
    with pytest.raises(ControlPlaneError) as caught:
        resolve_production_mda_provider(
            environ={},
            which=lambda name: str(MDA_FIXTURE) if name == "mda" else None,
        )
    _assert_pipeline_unavailable(caught.value)
