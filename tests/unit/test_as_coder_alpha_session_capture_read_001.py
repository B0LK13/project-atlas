"""AS-CODER-ALPHA-SESSION-CAPTURE-READ-001 — read-only session inventory."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_OK, main
from project_atlas.mcp_server import (
    SESSION_CAPTURE_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.session_capture import capture_session, list_captures
from project_atlas.web_api.conversation_captures import (
    list_conversation_capture_inventory,
)
from project_atlas.web_api.session_captures import (
    WebSessionCaptureError,
    _public_row,
    list_session_capture_inventory,
)


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
    capture_session(
        vault,
        "dark-factory-02ee94d0",
        summary="Factory milestone",
        kind="milestone",
    )
    capture_session(
        vault,
        "harbor-portal",
        summary="SECRET-PORTAL-SESSION",
        kind="decision",
    )
    return vault


def test_session_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.session-capture.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_captures(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.session-capture.read")
    result = report["result"]
    assert result["package_id"] == SESSION_CAPTURE_MCP_PACKAGE_ID
    assert result["capture_count"] == 0
    assert result["captures"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["unknown_equals_healthy"] is False
    assert result["honesty"]["record_or_write"] is False
    assert result["honesty"]["truth_core_promotion"] is False
    assert result["honesty"]["conversation_surface"] is False
    assert result["honesty"]["owner_gate_grant"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    scoped = list_session_capture_inventory(vault, project_id="dark-factory-02ee94d0")
    assert scoped["capture_count"] == 1
    assert scoped["captures"][0]["project_id"] == "dark-factory-02ee94d0"
    blob = json.dumps(scoped, sort_keys=True)
    assert "SECRET-PORTAL-SESSION" not in blob
    assert scoped["captures"][0]["authority"] is False


def test_conversation_receipts_are_not_session_captures(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    conv_dir = vault / "generated" / "ops" / "conversation-captures"
    conv_dir.mkdir(parents=True)
    (conv_dir / "ccap-not-session.json").write_text(
        json.dumps(
            {
                "capture_id": "ccap-not-session",
                "project_id": "harbor-portal",
                "summary": "CONVERSATION-LEAK",
                "source_provider": "cursor",
                "review_state": "captured",
                "authority": {"classification": "NON_CANONICAL"},
                "capture_items": [{"item_type": "observation", "text": "x"}],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    session = list_session_capture_inventory(vault)
    conversation = list_conversation_capture_inventory(vault)
    assert session["capture_count"] == 0
    assert "CONVERSATION-LEAK" not in json.dumps(session)
    assert conversation["capture_count"] == 1


def test_symlinked_capture_root_is_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    outside = tmp_path / "outside-captures"
    outside.mkdir()
    (outside / "capture-evil.json").write_text(
        json.dumps(
            {
                "capture_id": "capture-evil",
                "project_id": "evil",
                "kind": "note",
                "source": "explicit",
                "summary": "ROOT-ESCAPE-SESSION",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    generated = vault / "generated" / "ops"
    generated.mkdir(parents=True)
    (generated / "session-captures").symlink_to(outside)
    report = list_session_capture_inventory(vault)
    assert report["capture_count"] == 0
    assert "ROOT-ESCAPE-SESSION" not in json.dumps(report)
    assert list_captures(vault) == []


def test_symlinked_capture_file_is_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    capture_session(vault, "harbor-portal", summary="REAL-SESSION")
    outside = tmp_path / "evil.json"
    outside.write_text(
        json.dumps(
            {
                "capture_id": "capture-evil",
                "project_id": "evil",
                "kind": "note",
                "source": "explicit",
                "summary": "FILE-ESCAPE-SESSION",
            }
        ),
        encoding="utf-8",
    )
    root = vault / "generated" / "ops" / "session-captures"
    (root / "capture-evil.json").symlink_to(outside)
    report = list_session_capture_inventory(vault)
    blob = json.dumps(report)
    assert "FILE-ESCAPE-SESSION" not in blob
    assert report["capture_count"] == 1
    assert report["captures"][0]["summary"] == "REAL-SESSION"


def test_public_row_drops_escaped_paths(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    capture_session(vault, "harbor-portal", summary="REAL-SESSION")
    raw = list_captures(vault)
    raw[0]["path"] = "/etc/passwd"
    raw.append(
        {
            "capture_id": "capture-dotdot",
            "project_id": "evil",
            "kind": "note",
            "source": "explicit",
            "summary": "DOTDOT-PATH",
            "path": "../escape.json",
        }
    )
    assert _public_row(raw[0]) is None
    assert _public_row(raw[1]) is None
    report = list_session_capture_inventory(vault)
    assert all(
        not str(row.get("path") or "").startswith("/") for row in report["captures"]
    )
    assert "DOTDOT-PATH" not in json.dumps(report)
    assert "decisions" not in report["captures"][0]
    assert "changes" not in report["captures"][0]
    assert "next_work" not in report["captures"][0]
    assert "unknowns" not in report["captures"][0]


def test_invalid_project_filter_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(WebSessionCaptureError):
        list_session_capture_inventory(vault, project_id="../etc")


def test_invalid_vault_error_does_not_echo_path(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-vault"
    with pytest.raises(WebSessionCaptureError, match="vault is not a directory"):
        list_session_capture_inventory(missing)
    try:
        list_session_capture_inventory(missing)
    except WebSessionCaptureError as exc:
        assert str(missing) not in str(exc)


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.session-capture.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.session-capture.read", "args": {"record": True}}
            ),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.session-capture.read", operator=bare)


def test_cli_list_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    assert main(["capture", "list", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["captures"]) == 2
    assert _snapshot(vault) == before


def test_live_api_list_and_filter(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/session-captures", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            all_rows = json.loads(resp.read().decode("utf-8"))
        assert all_rows["capture_count"] == 2
        req = Request(
            f"http://{host}:{port}/v1/session-captures?project=dark-factory-02ee94d0",
            headers=hdrs,
        )
        with urlopen(req, timeout=2) as resp:
            scoped = json.loads(resp.read().decode("utf-8"))
        assert scoped["capture_count"] == 1
        assert "SECRET-PORTAL-SESSION" not in json.dumps(scoped)
        req = Request(
            f"http://{host}:{port}/v1/session-captures?project=../etc",
            headers=hdrs,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 400
    finally:
        server.shutdown()


def test_repeated_list_is_idempotent(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = list_session_capture_inventory(vault)
    second = list_session_capture_inventory(vault)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
