"""AS-CODER-ALPHA-OBSIDIAN-READ-001 — vault-scoped living-note inventory."""

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
    OBSIDIAN_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.obsidian import WebObsidianError, list_obsidian_notes


def _write(path: Path, text: str) -> None:
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


def _living(*, project_id: str, human: str = "") -> str:
    return (
        "---\n"
        f"project_id: {project_id}\n"
        "authority_level: derived\n"
        "---\n\n"
        f"# Living knowledge — {project_id}\n\n"
        "<!-- atlas:generated:start -->\n\n"
        "## Purpose\n"
        "Known purpose\n\n"
        "<!-- atlas:generated:end -->\n\n"
        "<!-- BEGIN HUMAN: notes -->\n"
        f"{human}"
        "<!-- END HUMAN: notes -->\n"
    )


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    _write(
        vault
        / "generated"
        / "obsidian"
        / "projects"
        / "dark-factory-02ee94d0"
        / "project-living.md",
        _living(project_id="dark-factory-02ee94d0", human="Factory human note\n"),
    )
    _write(
        vault
        / "generated"
        / "obsidian"
        / "projects"
        / "harbor-portal"
        / "project-living.md",
        _living(project_id="harbor-portal", human="SECRET-PORTAL-NOTE\n"),
    )
    return vault


def test_obsidian_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.obsidian.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_notes(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.obsidian.read")
    result = report["result"]
    assert result["package_id"] == OBSIDIAN_MCP_PACKAGE_ID
    assert result["note_count"] == 0
    assert result["notes"] == []
    assert result["available"] is False
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["materialize_or_write"] is False
    assert result["honesty"]["plugin_shipped"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    scoped = list_obsidian_notes(vault, project_id="dark-factory-02ee94d0")
    assert scoped["note_count"] == 1
    row = scoped["notes"][0]
    assert row["project_id"] == "dark-factory-02ee94d0"
    assert row["has_human_notes"] is True
    assert row["authority"] is False
    blob = json.dumps(scoped, sort_keys=True)
    assert "SECRET-PORTAL-NOTE" not in blob
    assert "harbor-portal" not in blob


def test_does_not_echo_human_note_text(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = list_obsidian_notes(vault)
    blob = json.dumps(report, sort_keys=True)
    assert "SECRET-PORTAL-NOTE" not in blob
    assert "Factory human note" not in blob
    assert report["note_count"] == 2


def test_symlink_escape_and_malformed_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    outside = tmp_path / "outside.md"
    _write(outside, _living(project_id="evil", human="leak\n"))
    root = vault / "generated" / "obsidian" / "projects"
    evil = root / "evil"
    evil.mkdir(parents=True)
    (evil / "project-living.md").symlink_to(outside)
    _write(root / "not-a-project" / "readme.txt", "nope")
    _write(root / "../escape.md", "escape")
    report = list_obsidian_notes(vault)
    assert report["note_count"] == 0
    assert report["notes"] == []


def test_symlinked_obsidian_root_is_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    outside = tmp_path / "outside-obsidian"
    _write(
        outside / "evil" / "project-living.md",
        _living(project_id="evil", human="ROOT-ESCAPE-NOTE\n"),
    )
    generated = vault / "generated" / "obsidian"
    generated.mkdir(parents=True)
    (generated / "projects").symlink_to(outside)
    report = list_obsidian_notes(vault)
    assert report["note_count"] == 0
    assert report["notes"] == []
    blob = json.dumps(report, sort_keys=True)
    assert "ROOT-ESCAPE-NOTE" not in blob
    assert str(outside.resolve()) not in blob


def test_invalid_project_filter_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(WebObsidianError):
        list_obsidian_notes(vault, project_id="../etc")


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.obsidian.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    payload = json.loads(first)
    assert payload["result"]["note_count"] == 2
    ids = [row["project_id"] for row in payload["result"]["notes"]]
    assert ids == sorted(ids)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.obsidian.read", "args": {"project": "x"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.obsidian.read", operator=bare)


def test_cli_obsidian_list_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    assert main(["obsidian", "list", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["note_count"] == 2
    assert payload["honesty"]["materialize_or_write"] is False
    assert _snapshot(vault) == before


def test_live_api_list_and_filter(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/obsidian", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            all_rows = json.loads(resp.read().decode("utf-8"))
        assert all_rows["note_count"] == 2
        assert all_rows["honesty"]["materialize_or_write"] is False
        req = Request(
            f"http://{host}:{port}/v1/obsidian?project=dark-factory-02ee94d0",
            headers=hdrs,
        )
        with urlopen(req, timeout=2) as resp:
            scoped = json.loads(resp.read().decode("utf-8"))
        assert scoped["note_count"] == 1
        assert scoped["notes"][0]["project_id"] == "dark-factory-02ee94d0"
        assert "SECRET-PORTAL-NOTE" not in json.dumps(scoped)
        req = Request(
            f"http://{host}:{port}/v1/obsidian?project=../etc",
            headers=hdrs,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 400
    finally:
        server.shutdown()


def test_repeated_list_is_idempotent(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = list_obsidian_notes(vault)
    second = list_obsidian_notes(vault)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
