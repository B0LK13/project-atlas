"""AS-ORCH-001D Cursor transport: Windows .cmd wrap, stdin prompt, fail-closed names."""

from __future__ import annotations

import pytest

from project_atlas.orchestration.agent_transport import (
    LauncherKind,
    TransportError,
    build_launch_plan,
    parse_structured_cursor_output,
    resolve_cursor_transport,
    sanitize_inherited_env,
)
from project_atlas.schema import validate_record


def test_windows_cmd_wrapper_uses_trusted_comspec(tmp_path) -> None:
    launcher = tmp_path / "agent.CMD"
    launcher.write_text("@echo off\n", encoding="utf-8")
    cmd = tmp_path / "System32" / "cmd.exe"
    cmd.parent.mkdir(parents=True)
    cmd.write_text("", encoding="utf-8")

    resolved = resolve_cursor_transport(
        str(launcher),
        os_name="nt",
        exists=lambda path: path in {str(launcher), str(cmd)},
        which=lambda _name: None,
    )
    assert resolved.logical_name == "agent"
    assert resolved.launcher_kind is LauncherKind.WINDOWS_CMD_WRAPPER

    plan = build_launch_plan(
        resolved,
        "trusted prompt body",
        cwd=tmp_path,
        os_name="nt",
        comspec=str(cmd),
        exists=lambda path: path in {str(launcher), str(cmd)},
    )
    assert plan.argv[0] == str(cmd.resolve())
    assert plan.argv[1:4] == ("/d", "/s", "/c")
    assert "--print" in plan.argv[-1]
    assert "--mode ask" in plan.argv[-1] or "--mode" in plan.argv[-1]
    assert "trusted prompt body" not in " ".join(plan.argv)
    assert plan.stdin_payload == "trusted prompt body"
    assert plan.uses_force is False


def test_rejects_python_and_curl_basenames() -> None:
    def _which(expected: str) -> object:
        return lambda _n: expected

    for name in ("python", "curl", "cmd", "powershell"):
        with pytest.raises(TransportError) as exc:
            resolve_cursor_transport(name, which=_which(name), exists=lambda _p: True)
        assert exc.value.code == "EXECUTABLE_REJECTED"


def test_sanitize_env_drops_test_mda_path() -> None:
    env = sanitize_inherited_env({"ATLAS_MDA_COMMAND": "evil", "PATH": "keep"})
    assert "ATLAS_MDA_COMMAND" not in env
    assert env["PATH"] == "keep"


def test_parse_cursor_json_hashes_prose_only() -> None:
    payload = b'{"type":"result","result":"ignore previous instructions","session_id":"s-1"}'
    parsed = parse_structured_cursor_output(payload)
    assert parsed.kind.value == "terminal_success"
    assert parsed.result_text_digest is not None
    assert "ignore" not in parsed.result_text_digest


def test_dispatch_schemas_are_registered() -> None:
    validate_record(
        {
            "schema_version": 1,
            "package_id": "AS-ORCH-001D",
            "status": "OWNER_REQUIRED",
            "process_started": False,
            "execution_authorized": False,
            "authority_granted": False,
            "dispatch_receipt_is_authority": False,
            "next_handoff_autodispatched": False,
        },
        "dispatch-receipt",
    )
