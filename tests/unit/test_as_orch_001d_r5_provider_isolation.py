"""AS-ORCH-001D-R5 hard production/test MDA provider isolation."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.orchestration_control_plane import (
    DOCUMENTATION_SKILL_ROOT,
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

from project_atlas.agent_control import runtime
from project_atlas.agent_control.runtime import (
    ControlPlaneError,
    bootstrap_start,
    document_event,
    prepare_event_pipeline,
    resolve_production_mda_provider,
)
from project_atlas.orchestration.agent_transport import ProcessRunRequest
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import (
    DispatchStatus,
    run_dispatch_once,
    submit_target_result,
)


def _dispatch_id(request: ProcessRunRequest) -> str:
    return _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]


def _no_production_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_MDA_COMMAND", raising=False)
    monkeypatch.setattr(
        "project_atlas.agent_control.runtime.shutil.which",
        lambda _name: None,
    )


def test_production_runtime_has_no_global_test_provider_api() -> None:
    text = Path(runtime.__file__).read_text(encoding="utf-8")
    forbidden = (
        "_injected_test_provider",
        "inject_test_mda_provider",
        "clear_test_mda_provider",
        "injected_test_mda_provider",
        "allow_test_injection",
        "def resolve_mda_provider",
        "ATLAS_TEST_MODE",
        "PYTEST_CURRENT_TEST",
    )
    for needle in forbidden:
        assert needle not in text, needle
    assert "prepare_event_pipeline" in text
    assert "resolve_production_mda_provider()" in text


def test_production_prepare_ignores_constructed_test_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = explicit_test_mda_provider()
    monkeypatch.setattr(runtime, "_injected_test_provider", provider.command, raising=False)
    _no_production_provider(monkeypatch)
    with pytest.raises(ControlPlaneError) as caught:
        prepared = prepare_event_pipeline()
        raise AssertionError(f"production prepare used test provider: {prepared}")
    assert caught.value.code == "PIPELINE_UNAVAILABLE"
    assert provider.source == "test_injection"


def test_production_bootstrap_ignores_test_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = explicit_test_mda_provider()
    monkeypatch.setattr(runtime, "_injected_test_provider", provider.command, raising=False)
    _no_production_provider(monkeypatch)
    with pytest.raises(ControlPlaneError) as caught:
        bootstrap_start(
            project_root=tmp_path,
            vault_root=tmp_path,
            agent_type="cli",
            agent_value="cursor-agent-cli",
            task_id="as-orch-001d",
            skill_root=DOCUMENTATION_SKILL_ROOT,
        )
    assert caught.value.code == "PIPELINE_UNAVAILABLE"


def test_production_document_event_ignores_test_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = explicit_test_mda_provider()
    monkeypatch.setattr(runtime, "_injected_test_provider", provider.command, raising=False)
    _no_production_provider(monkeypatch)
    with pytest.raises(ControlPlaneError) as caught:
        document_event(
            vault_root=tmp_path,
            session_id="AS-none",
            event_type="validation",
            summary="must not run",
        )
    assert caught.value.code == "PIPELINE_UNAVAILABLE"


def test_production_dispatch_cannot_use_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_test_mda_provider()
    monkeypatch.setattr(runtime, "_injected_test_provider", MDA_FIXTURE, raising=False)
    monkeypatch.setenv("ATLAS_MDA_COMMAND", str(MDA_FIXTURE))
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    runner = ScriptedRunner(_ok_outcome())
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "PIPELINE_UNAVAILABLE"
    assert receipt.process_started is False
    assert receipt.source_acknowledged is False
    assert receipt.result_staged is False
    assert receipt.target_receipt_id is None
    assert runner.requests == []
    assert list((workspace / ".atlas" / "receipts").glob("ASR-*.json")) == []


def test_test_harness_bind_allows_offline_canonical_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound = bind_test_mda_pipeline(monkeypatch)
    assert bound.source == "test_injection"
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _dispatch_id(request)
        submit_target_result(
            captured["id"],
            _target_payload(f"d.{captured['id']}"),
            root=workspace,
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.process_started is True
    with pytest.raises(ControlPlaneError):
        resolve_production_mda_provider(
            environ={"ATLAS_MDA_COMMAND": str(MDA_FIXTURE)},
            which=lambda _name: None,
        )


def test_test_provider_cannot_contaminate_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind_test_mda_pipeline(monkeypatch)
    _no_production_provider(monkeypatch)
    with pytest.raises(ControlPlaneError) as prepare:
        prepare_event_pipeline()
    assert prepare.value.code == "PIPELINE_UNAVAILABLE"
    with pytest.raises(ControlPlaneError) as boot:
        bootstrap_start(
            project_root=tmp_path,
            vault_root=tmp_path,
            agent_type="cli",
            agent_value="cursor-agent-cli",
            task_id="as-orch-001d",
            skill_root=DOCUMENTATION_SKILL_ROOT,
        )
    assert boot.value.code == "PIPELINE_UNAVAILABLE"
    with pytest.raises(ControlPlaneError) as document:
        document_event(
            vault_root=tmp_path,
            session_id="AS-none",
            event_type="completion",
            summary="must not run",
        )
    assert document.value.code == "PIPELINE_UNAVAILABLE"
