"""AS-CODER-ALPHA-CONFLICTS-MCP-001 — vault-scoped conflict index."""

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
    CONFLICTS_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.conflicts import list_vault_conflicts


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


def _conflict_entry(
    conflict_id: str,
    subject: str,
    field: str,
    left: str,
    right: str,
) -> dict[str, object]:
    return {
        "conflict_id": conflict_id,
        "subject": subject,
        "field": field,
        "conflict_type": "competing-claims",
        "claims": [
            {"claim": left, "source_id": "src-a"},
            {"claim": right, "source_id": "src-b"},
        ],
    }


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    _write(
        vault / "review" / "conflicts" / "dark-factory-02ee94d0.json",
        {
            "entries": [
                _conflict_entry(
                    "cf-factory",
                    "datastore",
                    "engine",
                    "PostgreSQL 15",
                    "PostgreSQL 16",
                )
            ]
        },
    )
    _write(
        vault / "review" / "conflicts" / "harbor-portal.json",
        {
            "entries": [
                _conflict_entry(
                    "cf-portal",
                    "auth",
                    "mode",
                    "password = 'not-a-real-secret-value'",
                    "oauth-portal-only",
                )
            ]
        },
    )
    return vault


def _http_json(
    host: str,
    port: int,
    headers: dict[str, str],
    path: str,
) -> tuple[int, dict[str, object]]:
    req = Request(f"http://{host}:{port}{path}", headers=headers, method="GET")
    try:
        with urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return exc.code, payload


def test_conflicts_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conflicts.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    result = report["result"]
    assert result["package_id"] == CONFLICTS_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["conflict_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["conflict_is_resolution"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False


def test_missing_conflict_file_is_empty_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = report["result"]["projects"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    assert rows[0]["conflict_count"] == 0
    assert rows[0]["conflicts"] == []
    assert rows[0]["honesty"]["unknown_is_valid"] is True
    assert rows[0]["honesty"]["fabricated_fields"] is False


def test_malformed_conflict_file_does_not_widen(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    path = vault / "review" / "conflicts" / "harbor-portal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    row = report["result"]["projects"][0]
    assert row["conflict_count"] == 0
    assert row["conflicts"] == []
    assert report["result"]["honesty"]["owner_capability_granted"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = {row["project_id"]: row for row in report["result"]["projects"]}
    assert set(rows) == {"dark-factory-02ee94d0", "harbor-portal", "sparse-proj"}
    factory = json.dumps(rows["dark-factory-02ee94d0"], sort_keys=True)
    assert "oauth-portal-only" not in factory
    assert "password = 'not-a-real-secret-value'" not in factory
    assert rows["dark-factory-02ee94d0"]["conflict_count"] == 1
    assert rows["harbor-portal"]["conflict_count"] == 1
    assert rows["sparse-proj"]["conflicts"] == []


def test_secret_shaped_claim_is_redacted(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    dump = json.dumps(report, sort_keys=True)
    assert "not-a-real-secret-value" not in dump
    portal = next(
        row
        for row in report["result"]["projects"]
        if row["project_id"] == "harbor-portal"
    )
    claims = [claim["claim"] for claim in portal["conflicts"][0]["claims"]]
    assert "[redacted: secret-shaped value]" in claims


def test_invalid_project_dir_is_skipped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "Not A Token").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    payload = list_vault_conflicts(vault)
    assert payload["skipped_invalid_ids"] == 1
    assert [row["project_id"] for row in payload["projects"]] == ["harbor-portal"]


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.conflicts.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.conflicts.read", "args": {"project": "harbor-portal"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.conflicts.read", operator=bare)


def test_determinism_and_ready_node_stable(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    a = invoke_mcp_tool(vault, "atlas.conflicts.read")
    b = invoke_mcp_tool(vault, "atlas.conflicts.read")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    ids = [row["project_id"] for row in a["result"]["projects"]]
    assert ids == sorted(ids)


def test_no_winner_and_no_owner_capability(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    dump = json.dumps(report, sort_keys=True)
    assert "winner" not in dump
    assert "resolved_to" not in dump
    assert '"owner_capability_granted": true' not in dump
    assert report["result"]["honesty"]["owner_capability_granted"] is False
    assert report["result"]["honesty"]["conflict_is_resolution"] is False


def test_http_vault_index_and_project_scope(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        status, index = _http_json(str(host), int(port), hdrs, "/v1/conflicts")
        assert status == 200
        assert index["package_id"] == CONFLICTS_PACKAGE_ID
        assert index["honesty"]["owner_capability_granted"] is False
        assert index["honesty"]["request_contains_project"] is False
        status, classic = _http_json(
            str(host),
            int(port),
            hdrs,
            "/v1/conflicts?project=harbor-portal",
        )
        assert status == 200
        assert classic["project_id"] == "harbor-portal"
        assert classic["conflict_count"] == 1
        assert "projects" not in classic
        status, bad = _http_json(
            str(host),
            int(port),
            hdrs,
            "/v1/conflicts?project=NotAToken",
        )
        assert status == 400
        assert "web-conflicts-project-id-invalid" in str(bad.get("error"))
    finally:
        server.shutdown()


def test_web_surfaces_are_wired() -> None:
    root = Path(__file__).resolve().parents[2]
    app = (root / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    nav = (root / "apps" / "web" / "src" / "components" / "ProdNav.tsx").read_text(
        encoding="utf-8"
    )
    page = (
        root / "apps" / "web" / "src" / "pages" / "production" / "ConflictsPage.tsx"
    ).read_text(encoding="utf-8")
    hook = (root / "apps" / "web" / "src" / "hooks" / "useLiveConflicts.ts").read_text(
        encoding="utf-8"
    )
    assert 'path="/conflicts"' in app
    assert 'to: "/conflicts"' in nav
    assert "useLiveConflicts" in page
    assert "ui_canonical=false" in page
    assert "does not pick a winner" in page
    assert 'liveApiFetch("/v1/conflicts")' in hook
    docs = (root / "docs" / "AS-CODER-ALPHA-CONFLICTS-MCP-001.md").read_text(
        encoding="utf-8"
    )
    assert "atlas.conflicts.read" in docs
    assert "owner_capability_granted" in docs


def test_package_does_not_touch_d149() -> None:
    root = Path(__file__).resolve().parents[2]
    estate = (root / "src" / "project_atlas" / "orchestration" / "autonomy").joinpath(
        "authentic_estate.py"
    )
    assert estate.is_file()
    text = estate.read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-CONFLICTS-MCP-001" not in text
