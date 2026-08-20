"""AS-CODER-ALPHA-MCP-LENS-PARITY-001 — project-scoped MCP lens tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    LENS_PACKAGE_ID,
    PROJECT_SCOPED_TOOLS,
    WRITE_CONTROLS,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)

FACTORY = "dark-factory-02ee94d0"
PORTAL = "harbor-portal"
FACTORY_TOKEN = "FACTORY-ONLY-TOKEN"
PORTAL_TOKEN = "SECRET-PORTAL-VALUE"
PORTAL_SECRET = "sk-SECRET-PORTAL-MATCHED-CONTENT"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
    (vault / "projects" / FACTORY).mkdir(parents=True)
    (vault / "projects" / PORTAL).mkdir(parents=True)
    _write(
        vault / "sources" / "manifests" / "source-manifest.json",
        {
            "sources": [
                {
                    "path": "docs/factory.md",
                    "source_id": "src-factory",
                    "likely_project": FACTORY,
                },
                {
                    "path": "docs/portal.md",
                    "source_id": "src-portal",
                    "likely_project": PORTAL,
                    "exclusion_reason": "sensitive-metadata-only",
                },
            ]
        },
    )
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {"sources": []},
    )
    _write(
        vault / "generated" / "reports" / "secret-findings.json",
        {
            "findings": [
                {
                    "path": "docs/portal.md",
                    "source_id": "src-portal",
                    "matched": PORTAL_SECRET,
                }
            ]
        },
    )
    _write(
        vault / "review" / "conflicts" / f"{FACTORY}.json",
        {
            "entries": [
                {
                    "conflict_id": FACTORY_TOKEN,
                    "conflict_type": "competing-claim",
                    "field": "datastore",
                }
            ]
        },
    )
    _write(
        vault / "review" / "conflicts" / f"{PORTAL}.json",
        {
            "entries": [
                {
                    "conflict_id": PORTAL_TOKEN,
                    "conflict_type": "competing-claim",
                    "field": "datastore",
                }
            ]
        },
    )
    return vault


def _invoke(vault: Path, tool_id: str, project_id: str) -> dict[str, object]:
    return invoke_mcp_tool(vault, tool_id, project_id=project_id)


def test_lens_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    for tool_id in sorted(PROJECT_SCOPED_TOOLS):
        assert tool_id in listing["tools"]
    assert listing["write_tools"] == []
    assert listing["write_controls"] == 0
    assert WRITE_CONTROLS == 0
    assert set(listing["project_scoped_tools"]) == set(PROJECT_SCOPED_TOOLS)


def test_unknown_tool_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(McpServerError, match="mcp-tool-denied"):
        invoke_mcp_tool(vault, "atlas.unknown.fabricate", project_id=FACTORY)
    with pytest.raises(McpServerError, match="mcp-tool-denied"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.vault.write", "project": FACTORY}),
        )


def test_project_scope_required(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    for tool_id in sorted(PROJECT_SCOPED_TOOLS):
        with pytest.raises(McpServerError, match="mcp-project-required"):
            invoke_mcp_tool(vault, tool_id)
        with pytest.raises(McpServerError, match="mcp-project-required"):
            handle_mcp_request_line(vault, json.dumps({"tool": tool_id}))


def test_zero_arg_tools_still_reject_project(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.brief.read", "project": FACTORY}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        invoke_mcp_tool(vault, "atlas.brief.read", project_id=FACTORY)


def test_mcp_is_not_authority(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    for tool_id in sorted(PROJECT_SCOPED_TOOLS):
        report = _invoke(vault, tool_id, FACTORY)
        result = report["result"]
        assert isinstance(result, dict)
        honesty = result["honesty"]
        assert isinstance(honesty, dict)
        assert honesty["mcp_is_authority"] is False
        assert honesty["lens_is_authority"] is False
        assert honesty["unknown_is_valid"] is True
        assert result["authority"] == "derived"
        assert result["mcp_package"] == LENS_PACKAGE_ID
        assert report["write_controls"] == 0


def test_write_controls_zero_and_no_vault_writes(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    for tool_id in sorted(PROJECT_SCOPED_TOOLS):
        line = json.dumps({"tool": tool_id, "project": FACTORY}, sort_keys=True)
        first = handle_mcp_request_line(vault, line)
        second = handle_mcp_request_line(vault, line)
        assert first == second
        assert _snapshot(vault) == before


def test_secret_echo_no(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    dumped = json.dumps(_invoke(vault, "atlas.source-health.read", PORTAL), sort_keys=True)
    assert PORTAL_SECRET not in dumped
    result = _invoke(vault, "atlas.source-health.read", PORTAL)["result"]
    assert isinstance(result, dict)
    honesty = result["honesty"]
    assert isinstance(honesty, dict)
    assert honesty["secrets_echoed"] is False


def test_cross_project_leak_count_zero(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    leaks = 0
    factory_blob = json.dumps(
        {
            "source-health": _invoke(vault, "atlas.source-health.read", FACTORY),
            "attention": _invoke(vault, "atlas.attention.read", FACTORY),
            "next": _invoke(vault, "atlas.next.read", FACTORY),
        },
        sort_keys=True,
    )
    if PORTAL_TOKEN in factory_blob or PORTAL_SECRET in factory_blob:
        leaks += 1
    portal_blob = json.dumps(
        _invoke(vault, "atlas.attention.read", PORTAL), sort_keys=True
    )
    if FACTORY_TOKEN in portal_blob:
        leaks += 1
    assert leaks == 0
    attention = _invoke(vault, "atlas.attention.read", FACTORY)["result"]
    assert isinstance(attention, dict)
    assert attention["project_id"] == FACTORY
    assert FACTORY_TOKEN in json.dumps(attention)


def test_cli_json_shape_parity(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    health = _invoke(vault, "atlas.source-health.read", FACTORY)["result"]
    assert isinstance(health, dict)
    assert health["schema"] == "atlas.coder-alpha.source-health.v1"
    assert health["project_id"] == FACTORY
    assert "health_state" in health
    attention = _invoke(vault, "atlas.attention.read", FACTORY)["result"]
    assert isinstance(attention, dict)
    assert attention["schema"] == "atlas.coder-alpha.attention.v1"
    assert "care_about" in attention
    nxt = _invoke(vault, "atlas.next.read", FACTORY)["result"]
    assert isinstance(nxt, dict)
    assert nxt["schema"] == "atlas.coder-alpha.next-receipt.v1"
    assert nxt["projects"] == [FACTORY]
    assert nxt["answers_written"] == []
    assert nxt["honesty"]["next_is_command"] is False
    assert nxt["honesty"]["read_only"] is True


def test_path_traversal_project_rejected(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    probes = (
        "../harbor-portal",
        "..\\harbor-portal",
        "harbor/../portal",
        "C:/Windows/System32",
        "/etc/passwd",
        "%2e%2e/harbor-portal",
    )
    for probe in probes:
        with pytest.raises(McpServerError, match="mcp-project-path-traversal"):
            invoke_mcp_tool(vault, "atlas.attention.read", project_id=probe)


def test_forbidden_keys_still_rejected(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {
                    "tool": "atlas.attention.read",
                    "project": FACTORY,
                    "args": {"write": True},
                }
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.source-health.read", "project": FACTORY, "path": "../x"}
            ),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(
            vault, "atlas.attention.read", operator=bare, project_id=FACTORY
        )


def test_determinism(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    for tool_id in sorted(PROJECT_SCOPED_TOOLS):
        a = _invoke(vault, tool_id, FACTORY)
        b = _invoke(vault, tool_id, FACTORY)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_package_doc_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    doc = root / "docs" / "AS-CODER-ALPHA-MCP-LENS-PARITY-001.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "MCP != AUTHORITY" in text or "MCP LENS != AUTHORITY" in text
    assert "WRITE_CONTROLS=0" in text
    assert "SECRET_ECHO=NO" in text
    assert "#370" in text
