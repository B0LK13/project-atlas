"""AS-CODER-ALPHA-INBOX-MCP-001 — vault-scoped inbox list MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.knowledge_inbox import build_knowledge_inbox_receipt
from project_atlas.mcp_server import (
    INBOX_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
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


def _capture(vault: Path, *, capture_id: str, project_id: str, summary: str) -> None:
    _write(
        vault / "generated" / "ops" / "conversation-captures" / f"{capture_id}.json",
        {
            "capture_id": capture_id,
            "project_id": project_id,
            "summary": summary,
            "review_state": "captured",
            "capture_items": [{"item_type": "observation", "text": summary}],
            "inbox": {"status": "quarantined", "promoted_to_authority": False},
        },
    )
    build_knowledge_inbox_receipt(
        vault,
        record_id=capture_id,
        status="quarantined",
        item_count=1,
    )


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    (vault / "projects" / "beta").mkdir(parents=True)
    _capture(vault, capture_id="ccap-a", project_id="alpha", summary="SECRET-ALPHA-INBOX")
    _capture(vault, capture_id="ccap-b", project_id="beta", summary="SECRET-BETA-INBOX")
    return vault


def test_inbox_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.inbox.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_inbox(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    result = invoke_mcp_tool(vault, "atlas.inbox.read")["result"]
    assert result["package_id"] == INBOX_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["owner_capability_granted"] is False


def test_missing_inbox_is_unknown_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    inbox = invoke_mcp_tool(vault, "atlas.inbox.read")["result"]["projects"][0]["inbox"]
    assert inbox["available"] is True
    assert inbox["count"] == 0
    assert inbox["items"] == []
    assert inbox["promoted_to_authority"] is False
    assert inbox["honesty"]["inbox_is_authority"] is False
    assert inbox["unknown"] == "UNKNOWN (no inbox items for project)"


def test_cross_project_isolation_and_no_promote(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.inbox.read")
    assert _snapshot(vault) == before
    rows = {row["project_id"]: row["inbox"] for row in report["result"]["projects"]}
    alpha = json.dumps(rows["alpha"], sort_keys=True)
    assert "SECRET-ALPHA-INBOX" in alpha
    assert "SECRET-BETA-INBOX" not in alpha
    assert rows["alpha"]["count"] == 1
    assert rows["alpha"]["items"][0]["promoted_to_authority"] is False
    assert rows["beta"]["count"] == 1
    assert "SECRET-BETA-INBOX" in json.dumps(rows["beta"], sort_keys=True)


def test_zero_arg_and_mcp_read(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    line = json.dumps({"tool": "atlas.inbox.read"}, sort_keys=True)
    assert handle_mcp_request_line(vault, line) == handle_mcp_request_line(vault, line)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.inbox.read", "args": {"project": "alpha"}}),
        )
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.inbox.read", operator=bare)
