"""AS-CODER-ALPHA-LENS-MCP-001 — vault-scoped overview/decisions/unknown/changed MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    CHANGED_PACKAGE_ID,
    DECISIONS_PACKAGE_ID,
    OVERVIEW_PACKAGE_ID,
    UNKNOWN_PACKAGE_ID,
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


def _project_note(project_id: str, source_id: str) -> str:
    semantic = {
        "project_id": project_id,
        "sources": [{"path": "README.md", "source_id": source_id}],
        "coverage": [],
    }
    return (
        f"---\ntype: Project\ntitle: {project_id}\n---\n\n# {project_id}\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n"
    )


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    _write_text(vault / "projects" / "alpha" / "project.md", _project_note("alpha", "source-alpha"))
    _write_text(vault / "projects" / "beta" / "project.md", _project_note("beta", "source-beta"))
    _write_text(
        vault / "sources" / "imported-documents" / "source-alpha.md",
        "# Alpha\n\nPersistent factory compile SECRET-ALPHA.\n",
    )
    _write_text(
        vault / "sources" / "imported-documents" / "source-beta.md",
        "# Beta\n\nPortal UI SECRET-BETA.\n",
    )
    _write_text(
        vault / "projects" / "alpha" / "decisions.md",
        "# Decisions\n\n## Adopt Postgres 16 SECRET-ALPHA-DEC\n",
    )
    _write_text(
        vault / "projects" / "beta" / "decisions.md",
        "# Decisions\n\n## Keep Redis 7 SECRET-BETA-DEC\n",
    )
    _write(
        vault / "review" / "conflicts" / "alpha.json",
        {"entries": [{"id": "c-a", "status": "pending", "summary": "SECRET-ALPHA-CONFLICT"}]},
    )
    _write(
        vault / "review" / "conflicts" / "beta.json",
        {"entries": [{"id": "c-b", "status": "pending", "summary": "SECRET-BETA-CONFLICT"}]},
    )
    _write(
        vault / "generated" / "ops" / "connect-inventory.prev.json",
        {"by_path": {"docs/alpha.md": "aaa", "docs/shared.md": "old"}},
    )
    _write(
        vault / "generated" / "ops" / "connect-inventory.json",
        {"by_path": {"docs/alpha.md": "aaa", "docs/beta.md": "bbb", "docs/shared.md": "new"}},
    )
    return vault


LENS_TOOLS = (
    "atlas.overview.read",
    "atlas.decisions.read",
    "atlas.unknown.read",
    "atlas.changed.read",
)


def test_lens_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    for tool in LENS_TOOLS:
        assert tool in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.vault.write" not in listing["tools"]


def test_empty_vault_does_not_invent_lenses(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    expected = {
        "atlas.overview.read": (OVERVIEW_PACKAGE_ID, "overviews"),
        "atlas.decisions.read": (DECISIONS_PACKAGE_ID, "projects"),
        "atlas.unknown.read": (UNKNOWN_PACKAGE_ID, "projects"),
        "atlas.changed.read": (CHANGED_PACKAGE_ID, "projects"),
    }
    for tool, (package_id, rows_key) in expected.items():
        report = invoke_mcp_tool(vault, tool)
        result = report["result"]
        assert result["package_id"] == package_id
        assert result["project_count"] == 0
        assert result[rows_key] == []
        assert result["honesty"]["unknown_is_valid"] is True
        assert result["honesty"]["mcp_is_authority"] is False
        assert result["honesty"]["owner_capability_granted"] is False
        assert result["honesty"]["portfolio_implicit_all"] is False


def test_missing_evidence_is_unknown_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    overview = invoke_mcp_tool(vault, "atlas.overview.read")["result"]["overviews"][0][
        "overview"
    ]
    assert overview["available"] is True
    assert overview["status"] == "unknown"
    assert overview["summary"] is None
    assert overview["honesty"]["unknown_is_valid"] is True
    assert overview["honesty"]["fabricated_fields"] is False

    decisions = invoke_mcp_tool(vault, "atlas.decisions.read")["result"]["projects"][0][
        "decisions"
    ]
    assert decisions["status"] == "unknown"
    assert decisions["decision_count"] == 0
    assert decisions["summary"] is None

    unknown = invoke_mcp_tool(vault, "atlas.unknown.read")["result"]["projects"][0][
        "unknown"
    ]
    assert unknown["available"] is True
    assert unknown["rollup"] in {"unknown", "clear"}
    assert unknown["honesty"]["unknown_is_valid"] is True

    changed = invoke_mcp_tool(vault, "atlas.changed.read")["result"]["projects"][0][
        "changed"
    ]
    assert changed["available"] is False
    assert changed["status"] == "unknown"
    assert changed["rollup"] == "baseline"
    assert changed["delta"]["prior_baseline"] is False
    assert changed["honesty"]["fabricated_fields"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    overviews = {
        row["project_id"]: row["overview"]
        for row in invoke_mcp_tool(vault, "atlas.overview.read")["result"]["overviews"]
    }
    alpha_ov = json.dumps(overviews["alpha"], sort_keys=True)
    assert "SECRET-ALPHA" in alpha_ov
    assert "SECRET-BETA" not in alpha_ov
    assert "SECRET-BETA" in json.dumps(overviews["beta"], sort_keys=True)

    decisions = {
        row["project_id"]: row["decisions"]
        for row in invoke_mcp_tool(vault, "atlas.decisions.read")["result"]["projects"]
    }
    alpha_dec = json.dumps(decisions["alpha"], sort_keys=True)
    assert "SECRET-ALPHA-DEC" in alpha_dec
    assert "SECRET-BETA-DEC" not in alpha_dec
    assert decisions["alpha"]["decision_count"] >= 1
    assert decisions["beta"]["decision_count"] >= 1

    unknowns = {
        row["project_id"]: row["unknown"]
        for row in invoke_mcp_tool(vault, "atlas.unknown.read")["result"]["projects"]
    }
    assert unknowns["alpha"]["signals"]["unresolved_conflicts"] == 1
    assert unknowns["beta"]["signals"]["unresolved_conflicts"] == 1
    assert unknowns["alpha"]["rollup"] == "conflict"
    assert "SECRET-BETA-CONFLICT" not in json.dumps(unknowns["alpha"], sort_keys=True)


def test_changed_derives_inventory_without_write_or_rotate(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.changed.read")
    assert _snapshot(vault) == before
    assert not list((vault / "generated" / "answers").glob("ans-changed-*.json"))
    rows = {row["project_id"]: row["changed"] for row in report["result"]["projects"]}
    changed = rows["alpha"]
    assert changed["available"] is True
    assert changed["delta"]["prior_baseline"] is True
    assert changed["delta"]["added_count"] >= 1
    assert changed["delta"]["modified_count"] >= 1
    assert changed["honesty"]["canonical_write"] is False
    assert changed["honesty"]["owner_capability_granted"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    for tool in LENS_TOOLS:
        line = json.dumps({"tool": tool}, sort_keys=True)
        first = handle_mcp_request_line(vault, line)
        second = handle_mcp_request_line(vault, line)
        assert first == second
        with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "args": {"project": "alpha"}}),
            )
        with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "project": "alpha"}),
            )
    assert _snapshot(vault) == before


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    for tool in LENS_TOOLS:
        with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
            invoke_mcp_tool(vault, tool, operator=bare)


def test_determinism_and_sorted_project_ids(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    for tool in LENS_TOOLS:
        a = invoke_mcp_tool(vault, tool)
        b = invoke_mcp_tool(vault, tool)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        result = a["result"]
        rows = result.get("overviews") or result.get("projects") or []
        ids = [row["project_id"] for row in rows]
        assert ids == sorted(ids)


def test_unknown_mcp_does_not_resolve_conflicts(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = (vault / "review" / "conflicts" / "alpha.json").read_text(encoding="utf-8")
    report = invoke_mcp_tool(vault, "atlas.unknown.read")
    after = (vault / "review" / "conflicts" / "alpha.json").read_text(encoding="utf-8")
    assert before == after
    unknown = next(
        row["unknown"]
        for row in report["result"]["projects"]
        if row["project_id"] == "alpha"
    )
    assert unknown["signals"]["unresolved_conflicts"] == 1
    assert unknown["honesty"]["lens_is_authority"] is False
