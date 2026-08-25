"""AS-CODER-ALPHA-DOCTOR-MCP-001 — vault-scoped read-only doctor projection."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_OK, main
from project_atlas.mcp_server import (
    DOCTOR_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.doctor import WebDoctorError, list_doctor


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    vault.mkdir()
    (vault / "index.md").write_text("# vault\n", encoding="utf-8")
    charter = vault / "00-system" / "vault-charter.md"
    charter.parent.mkdir(parents=True)
    charter.write_text("# charter\n", encoding="utf-8")
    (vault / "generated" / "indexes").mkdir(parents=True)
    return vault


def test_doctor_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.doctor.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_is_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.doctor.read")
    result = report["result"]
    assert result["package_id"] == DOCTOR_MCP_PACKAGE_ID
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["unknown_equals_healthy"] is False
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["owner_gate_grant"] is False
    assert result["authority"] is False
    names = {row["name"]: row["status"] for row in result["checks"]}
    assert names["vault:present"] == "ok"
    assert names["vault:index.md"] == "warn"
    assert names["vault:generated-indexes"] == "unknown"
    assert result["rollup"] in {"warn", "error", "unknown"}
    assert result["rollup"] != "ok"


def test_does_not_echo_absolute_vault_path(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = list_doctor(vault)
    blob = json.dumps(report, sort_keys=True)
    assert str(vault.resolve()) not in blob
    assert report["honesty"]["owner_gate_grant"] is False


def test_invalid_vault_fail_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(WebDoctorError, match="vault is not a directory") as exc:
        list_doctor(missing)
    assert str(missing.resolve()) not in str(exc.value)


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.doctor.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.doctor.read", "args": {"grant": "owner"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.doctor.read", "project": "harbor-api"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.doctor.read", operator=bare)


def test_cli_doctor_remains_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    assert main(["doctor", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["rollup"] == "ok"
    assert _snapshot(vault) == before


def test_live_api_doctor(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/doctor", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == DOCTOR_MCP_PACKAGE_ID
        assert body["honesty"]["owner_gate_grant"] is False
        assert body["honesty"]["unknown_equals_healthy"] is False
        assert str(vault.resolve()) not in json.dumps(body)
    finally:
        server.shutdown()


def test_repeated_doctor_is_idempotent(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = list_doctor(vault)
    second = list_doctor(vault)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
