"""AS-CODER-ALPHA-CAPTURE-READ-001 -- vault-scoped session-capture REPORT READ."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.capture_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_COMMAND,
    TRUTH_BOUNDARY,
    WebCaptureReadError,
    read_capture_view,
    render_capture_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_capture(vault: Path, name: str = "capture-abc123.json") -> None:
    path = vault / "generated" / "ops" / "session-captures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package": "AS-CODER-ALPHA-CAPTURE-001",
                "capture_id": "capture-abc123",
                "project_id": "harbor-api",
                "kind": "note",
                "summary": "fixture note",
                "honesty": {"invented_facts": False},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebCaptureReadError, match="capture-read-vault-missing"):
        read_capture_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_capture_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_CAPTURE_VIEW"
    assert view["source_command"] == SOURCE_COMMAND
    assert view["honesty"]["capture_is_authority"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_capture_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_present_capture_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_capture(vault)
    view = read_capture_view(vault)
    assert view["status"] == "PRESENT"
    assert view["view"]["artifact_count"] == 1
    assert "[HEALTHY]" not in render_capture_text(view)


def test_invented_facts_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "session-captures" / "capture-evil.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"honesty": {"invented_facts": True}}) + "\n", encoding="utf-8")
    with pytest.raises(WebCaptureReadError, match="invented-facts"):
        read_capture_view(vault)


def test_malformed_only_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "session-captures" / "capture-bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_capture_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["honesty"]["unknown_is_healthy"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_capture(vault)
    before = _snapshot(vault)
    read_capture_view(vault)
    assert _snapshot(vault) == before


def test_reader_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/capture_read.py").read_text(encoding="utf-8")
    forbidden = (
        "from project_atlas.session_capture import",
        "capture_session(",
        "list_captures(",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "_atomic_write",
        "write_text(",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_capture_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert open_app_service(vault).capture_view()["status"] == "EMPTY"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["capture", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert main(["capture", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out) == report


def test_cli_list_remains(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["capture", "list", "--vault", str(vault), "--json"]) == EXIT_OK
    listed = json.loads(capsys.readouterr().out)
    assert listed["package"] == "AS-CODER-ALPHA-CAPTURE-001"
    assert "package_id" not in listed


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["capture", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert main(["capture", "report", "--vault", str(missing), "--json"]) == EXIT_ERROR


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["capture", "report", "--help"])
    assert info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.capture.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.connect.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]


def test_mcp_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    result = invoke_mcp_tool(vault, "atlas.capture.read")["result"]
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False


def test_mcp_args_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.capture.read", "args": {"project": "x"}}),
        )


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.capture.read", operator=bare)


def test_api_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        url = f"http://{host}:{port}/v1/capture/report"
        with urlopen(Request(url, headers=auth), timeout=2) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        req = Request(
            f"http://{host}:{port}/v1/capture/report",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (root / "src/project_atlas/orchestration/autonomy/authentic_estate.py").read_text(
        encoding="utf-8"
    )
    assert "AS-CODER-ALPHA-CAPTURE-READ-001" not in authentic
