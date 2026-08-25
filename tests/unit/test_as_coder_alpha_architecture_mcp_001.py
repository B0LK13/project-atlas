"""AS-CODER-ALPHA-ARCHITECTURE-MCP-001 — vault-scoped architecture MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    ARCHITECTURE_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    (vault / "projects" / "alpha").mkdir(parents=True)
    (vault / "projects" / "beta").mkdir(parents=True)
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "ARCHITECTURE.md",
                    "source_id": "arch-alpha",
                    "likely_project": "alpha",
                },
                {
                    "path": "ARCHITECTURE.md",
                    "source_id": "arch-beta",
                    "likely_project": "beta",
                },
            ]
        },
    )
    _write_text(
        vault / "sources" / "imported-documents" / "arch-alpha.md",
        "# Architecture\n\n## Components\n\nCore compiler SECRET-ALPHA-ARCH\n",
    )
    _write_text(
        vault / "sources" / "imported-documents" / "arch-beta.md",
        "# Architecture\n\n## Components\n\nPortal shell SECRET-BETA-ARCH\n",
    )
    return vault


def test_architecture_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.architecture.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_architecture(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.architecture.read")
    result = report["result"]
    assert result["package_id"] == ARCHITECTURE_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["owner_capability_granted"] is False


def test_missing_architecture_evidence_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    row = invoke_mcp_tool(vault, "atlas.architecture.read")["result"]["projects"][0][
        "architecture"
    ]
    assert row["available"] is True
    assert row["status"] == "unknown"
    assert row["summary"] is None
    assert row["known_slot_count"] == 0
    assert row["honesty"]["unknown_is_valid"] is True
    assert row["honesty"]["fabricated_fields"] is False


def test_cross_project_isolation_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.architecture.read")
    assert _snapshot(vault) == before
    assert not list((vault / "generated" / "answers").glob("ans-architecture-*.json"))
    rows = {
        row["project_id"]: row["architecture"] for row in report["result"]["projects"]
    }
    alpha = json.dumps(rows["alpha"], sort_keys=True)
    assert "SECRET-ALPHA-ARCH" in alpha
    assert "SECRET-BETA-ARCH" not in alpha
    assert rows["alpha"]["status"] == "derived"
    assert rows["alpha"]["known_slot_count"] >= 1
    assert "SECRET-BETA-ARCH" in json.dumps(rows["beta"], sort_keys=True)
    assert rows["alpha"]["honesty"]["owner_capability_granted"] is False


def test_zero_arg_protocol(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    line = json.dumps({"tool": "atlas.architecture.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.architecture.read", "args": {"project": "alpha"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.architecture.read", operator=bare)
