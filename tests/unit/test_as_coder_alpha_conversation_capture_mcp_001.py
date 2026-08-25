"""AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001 — read-only conversation inventory."""

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
    CONVERSATION_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.conversation_captures import (
    WebConversationCaptureError,
    list_conversation_capture_inventory,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _row(*, capture_id: str, project_id: str, summary: str) -> dict[str, object]:
    return {
        "capture_id": capture_id,
        "project_id": project_id,
        "source_provider": "cursor",
        "summary": summary,
        "review_state": "captured",
        "authority": {"classification": "NON_CANONICAL"},
        "capture_items": [{"item_type": "observation", "text": summary}],
        "projection": {"path": f"generated/ops/conversation-captures/{capture_id}.md"},
    }


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    _write(
        vault / "generated" / "ops" / "conversation-captures" / "ccap-factory-aaaa.json",
        _row(
            capture_id="ccap-factory-aaaa",
            project_id="dark-factory-02ee94d0",
            summary="Factory observation",
        ),
    )
    _write(
        vault / "generated" / "ops" / "conversation-captures" / "ccap-portal-bbbb.json",
        _row(
            capture_id="ccap-portal-bbbb",
            project_id="harbor-portal",
            summary="SECRET-PORTAL-CAPTURE",
        ),
    )
    return vault


def test_conversation_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conversation.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_captures(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.conversation.read")
    result = report["result"]
    assert result["package_id"] == CONVERSATION_MCP_PACKAGE_ID
    assert result["capture_count"] == 0
    assert result["captures"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["submit_or_review"] is False
    assert result["honesty"]["truth_core_promotion"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    scoped = list_conversation_capture_inventory(vault, project_id="dark-factory-02ee94d0")
    assert scoped["capture_count"] == 1
    assert scoped["captures"][0]["project_id"] == "dark-factory-02ee94d0"
    blob = json.dumps(scoped, sort_keys=True)
    assert "SECRET-PORTAL-CAPTURE" not in blob
    assert scoped["captures"][0]["authority"] is False


def test_symlinked_capture_root_is_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    outside = tmp_path / "outside-captures"
    _write(
        outside / "ccap-evil.json",
        _row(capture_id="ccap-evil", project_id="evil", summary="ROOT-ESCAPE-CAPTURE"),
    )
    generated = vault / "generated" / "ops"
    generated.mkdir(parents=True)
    (generated / "conversation-captures").symlink_to(outside)
    report = list_conversation_capture_inventory(vault)
    assert report["capture_count"] == 0
    assert "ROOT-ESCAPE-CAPTURE" not in json.dumps(report)


def test_invalid_project_filter_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(WebConversationCaptureError):
        list_conversation_capture_inventory(vault, project_id="../etc")


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.conversation.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conversation.read", "args": {"review": "accept"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.conversation.read", operator=bare)


def test_cli_conversations_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    assert main(["capture", "conversations", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["capture_count"] == 2
    assert payload["honesty"]["submit_or_review"] is False
    assert _snapshot(vault) == before


def test_live_api_list_and_filter(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/conversation-captures", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            all_rows = json.loads(resp.read().decode("utf-8"))
        assert all_rows["capture_count"] == 2
        req = Request(
            f"http://{host}:{port}/v1/conversation-captures?project=dark-factory-02ee94d0",
            headers=hdrs,
        )
        with urlopen(req, timeout=2) as resp:
            scoped = json.loads(resp.read().decode("utf-8"))
        assert scoped["capture_count"] == 1
        assert "SECRET-PORTAL-CAPTURE" not in json.dumps(scoped)
        req = Request(
            f"http://{host}:{port}/v1/conversation-captures?project=../etc",
            headers=hdrs,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 400
    finally:
        server.shutdown()


def test_repeated_list_is_idempotent(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = list_conversation_capture_inventory(vault)
    second = list_conversation_capture_inventory(vault)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
