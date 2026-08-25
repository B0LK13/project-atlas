"""AS-CODER-ALPHA-CAPTURE-LIST-001 — vault-scoped session-capture list."""

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
from project_atlas.mcp_server import (
    CAPTURE_LIST_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.session_capture import (
    LIST_PACKAGE_ID,
    SessionCaptureError,
    capture_session,
    read_vault_session_captures,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _capture_snapshot(vault: Path) -> dict[str, str]:
    root = vault / "generated" / "ops" / "session-captures"
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _http_json(
    host: str,
    port: int,
    headers: dict[str, str],
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    req = Request(f"http://{host}:{port}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return exc.code, payload


def _seed_captures(vault: Path) -> None:
    capture_session(
        vault,
        "dark-factory",
        summary="Factory compile checkpoint",
        kind="milestone",
        decisions=["Keep UNKNOWN honest"],
        unknowns=["Need authentic estate"],
    )
    capture_session(
        vault,
        "harbor-portal",
        summary="SECRET-PORTAL-VALUE",
        kind="note",
        changes=["Portal capture only"],
    )


def test_empty_vault_does_not_invent_captures(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = read_vault_session_captures(vault)
    assert report["package_id"] == LIST_PACKAGE_ID
    assert report["capture_count"] == 0
    assert report["captures"] == []
    assert report["honesty"]["unknown_is_valid"] is True
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["capture_is_layer_b"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["zero_arg_vault_scope"] is True


def test_cross_project_filter_does_not_leak(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_captures(vault)
    factory = read_vault_session_captures(vault, project_id="dark-factory")
    assert factory["capture_count"] == 1
    assert factory["captures"][0]["project_id"] == "dark-factory"
    blob = json.dumps(factory, sort_keys=True)
    assert "SECRET-PORTAL-VALUE" not in blob
    assert "harbor-portal" not in blob
    assert factory["honesty"]["request_contains_project"] is True


def test_conversation_captures_are_not_session_captures(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    convo = vault / "generated" / "ops" / "conversation-captures"
    convo.mkdir(parents=True)
    (convo / "ccap-not-a-session.json").write_text(
        json.dumps({"capture_id": "ccap-not-a-session", "summary": "quarantine only"}),
        encoding="utf-8",
    )
    report = read_vault_session_captures(vault)
    assert report["captures"] == []


def test_malformed_project_is_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(SessionCaptureError):
        read_vault_session_captures(vault, project_id="../evil")
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError):
        svc.session_captures(project_id="..\\evil")


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.captures.list.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_mcp_empty_and_seeded(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    empty_report = invoke_mcp_tool(empty, "atlas.captures.list.read")
    assert empty_report["result"]["package_id"] == CAPTURE_LIST_PACKAGE_ID
    assert empty_report["result"]["captures"] == []
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_captures(vault)
    report = invoke_mcp_tool(vault, "atlas.captures.list.read")
    result = report["result"]
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["zero_arg_vault_scope"] is True
    assert result["honesty"]["request_contains_project"] is False
    ids = {row["project_id"] for row in result["captures"]}
    assert ids == {"dark-factory", "harbor-portal"}


def test_mcp_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_captures(vault)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.captures.list.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.captures.list.read", "args": {"project": "harbor-portal"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.captures.list.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.captures.list.read", operator=bare)


def test_http_captures_scope_and_writes(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_captures(vault)
    before = _capture_snapshot(vault)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        status, empty_filter = _http_json(
            str(host), int(port), hdrs, "/v1/captures?project=missing-project"
        )
        assert status == 200
        assert empty_filter["capture_count"] == 0
        status, factory = _http_json(
            str(host), int(port), hdrs, "/v1/captures?project=dark-factory"
        )
        assert status == 200
        assert factory["package_id"] == LIST_PACKAGE_ID
        assert factory["capture_count"] == 1
        assert "SECRET-PORTAL-VALUE" not in json.dumps(factory)
        status, all_rows = _http_json(str(host), int(port), hdrs, "/v1/captures")
        assert status == 200
        assert all_rows["capture_count"] == 2
        status, _bad = _http_json(
            str(host), int(port), hdrs, "/v1/captures?project=../evil"
        )
        assert status == 400
        status, _posted = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/captures",
            method="POST",
            body=b"{}",
        )
        assert status == 405
        meta_status, meta = _http_json(str(host), int(port), hdrs, "/v1/meta")
        assert meta_status == 200
        assert meta["captures_live"] is True
    finally:
        server.shutdown()
    assert _capture_snapshot(vault) == before
