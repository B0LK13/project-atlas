"""AS-CODER-ALPHA-REVIEW-MCP-001 — vault-scoped read-only review inventory."""

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
from project_atlas.mcp_server import (
    REVIEW_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.reviews import WebReviewError, list_reviews


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


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    _write(
        vault / "review" / "pending" / "dark-factory-02ee94d0.json",
        {
            "entries": [
                {
                    "review_id": "rev-factory-1",
                    "subject": "datastore",
                    "field": "engine",
                    "reason": "Factory conflict",
                    "status": "pending",
                }
            ]
        },
    )
    _write(
        vault / "review" / "pending" / "harbor-portal.json",
        {
            "entries": [
                {
                    "review_id": "rev-portal-1",
                    "subject": "ui",
                    "field": "theme",
                    "reason": "SECRET-PORTAL-REVIEW",
                    "status": "pending",
                }
            ]
        },
    )
    _write(
        vault / "state" / "human-decisions" / "dark-factory-02ee94d0.json",
        {
            "decisions": [
                {
                    "review_id": "rev-factory-old",
                    "decision": "accept",
                    "reason": "owner accepted factory",
                    "status": "resolved",
                }
            ]
        },
    )
    return vault


def test_review_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.review.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_reviews(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.review.read")
    result = report["result"]
    assert result["package_id"] == REVIEW_MCP_PACKAGE_ID
    assert result["pending_count"] == 0
    assert result["pending_reviews"] == []
    assert result["human_decisions"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["decide_or_promote"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    scoped = list_reviews(vault, project_id="dark-factory-02ee94d0")
    assert scoped["pending_count"] == 1
    assert scoped["pending_reviews"][0]["project_id"] == "dark-factory-02ee94d0"
    blob = json.dumps(scoped, sort_keys=True)
    assert "SECRET-PORTAL-REVIEW" not in blob
    assert scoped["human_decision_count"] == 1


def test_symlink_escape_and_malformed_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    outside = tmp_path / "outside.json"
    _write(outside, {"entries": [{"review_id": "rev-leak", "status": "pending"}]})
    pending = vault / "review" / "pending"
    pending.mkdir(parents=True)
    (pending / "evil.json").symlink_to(outside)
    _write(pending / "not-json.txt", {"entries": []})
    report = list_reviews(vault)
    assert report["pending_count"] == 0


def test_invalid_project_filter_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(WebReviewError):
        list_reviews(vault, project_id="../etc")


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.review.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.review.read", "args": {"decide": "accept"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.review.read", operator=bare)


def test_live_api_list_and_filter(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/reviews", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            all_rows = json.loads(resp.read().decode("utf-8"))
        assert all_rows["pending_count"] == 2
        assert all_rows["honesty"]["decide_or_promote"] is False
        req = Request(
            f"http://{host}:{port}/v1/reviews?project=dark-factory-02ee94d0",
            headers=hdrs,
        )
        with urlopen(req, timeout=2) as resp:
            scoped = json.loads(resp.read().decode("utf-8"))
        assert scoped["pending_count"] == 1
        assert "SECRET-PORTAL-REVIEW" not in json.dumps(scoped)
        req = Request(
            f"http://{host}:{port}/v1/reviews?project=../etc",
            headers=hdrs,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 400
    finally:
        server.shutdown()
