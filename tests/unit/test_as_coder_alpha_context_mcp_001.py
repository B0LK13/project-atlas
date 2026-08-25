"""AS-CODER-ALPHA-CONTEXT-MCP-001 — zero-arg vault-scoped agent context MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    CONTEXT_PACKAGE_ID,
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


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    _write(
        vault / "generated" / "answers" / "ans-overview-dark-factory-02ee94d0.json",
        {"answer_id": "ans-overview-dark-factory-02ee94d0", "summary": "Factory compile"},
    )
    _write(
        vault / "generated" / "answers" / "ans-overview-harbor-portal.json",
        {
            "answer_id": "ans-overview-harbor-portal",
            "summary": "Portal UI",
            "secret_marker": "SECRET-PORTAL-VALUE",
        },
    )
    return vault


def test_context_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.context.read" in listing["tools"]
    assert "atlas.brief.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_contexts(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.context.read")
    result = report["result"]
    assert result["package_id"] == CONTEXT_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["contexts"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["canonical_write"] is False
    assert result["honesty"]["atlas_context_file"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False


def test_missing_lenses_stay_unknown_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.context.read")
    rows = report["result"]["contexts"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    context = rows[0]["context"]
    assert context["purpose"] == "UNKNOWN"
    assert context["honesty"]["unknown_is_valid"] is True
    assert context["honesty"]["fabricated_fields"] is False
    assert context["honesty"]["atlas_context_file"] is False
    assert "UNKNOWN stays UNKNOWN" in context["markdown"]


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.context.read")
    rows = {row["project_id"]: row["context"] for row in report["result"]["contexts"]}
    assert set(rows) == {"dark-factory-02ee94d0", "harbor-portal"}
    factory = json.dumps(rows["dark-factory-02ee94d0"], sort_keys=True)
    assert "SECRET-PORTAL-VALUE" not in factory
    assert "Portal UI" not in factory
    assert rows["harbor-portal"]["purpose"] == "Portal UI"
    assert "SECRET-PORTAL-VALUE" not in rows["dark-factory-02ee94d0"]["markdown"]
    assert "Factory compile" in rows["dark-factory-02ee94d0"]["markdown"]


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.context.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "agent-context").exists()
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.context.read", "args": {"project": "harbor-portal"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.context.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.context.read", operator=bare)


def test_determinism(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    a = invoke_mcp_tool(vault, "atlas.context.read")
    b = invoke_mcp_tool(vault, "atlas.context.read")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    ids = [row["project_id"] for row in a["result"]["contexts"]]
    assert ids == sorted(ids)


def test_does_not_touch_d149_owner_gates() -> None:
    source = Path(__file__).resolve().parents[2] / "src" / "project_atlas" / "mcp_server.py"
    text = source.read_text(encoding="utf-8")
    assert "refresh_authentic_o2_node_states" not in text
    assert "OWNER_GATE" not in text
    assert "AUTHENTIC_ESTATE_ROOT" not in text
