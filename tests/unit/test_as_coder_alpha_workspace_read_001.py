"""AS-CODER-ALPHA-WORKSPACE-READ-001 -- vault-scoped workspace REPORT READ."""

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
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.workspace_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_ROUTE,
    TRUTH_BOUNDARY,
    WebWorkspaceReadError,
    read_workspace_view,
    render_workspace_text,
)
from project_atlas.web_mission_workspace import build_workspace_view


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _add_project(vault: Path, project_id: str) -> None:
    (vault / "projects" / project_id).mkdir(parents=True)


def _write_ops_snapshot(vault: Path, *, estate: str = "degraded") -> None:
    path = vault / "generated" / "ops" / "health-snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "rollup": {"estate": estate},
                "truth_plane": "operational",
                "authority_plane": "none",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebWorkspaceReadError, match="workspace-read-vault-missing"):
        read_workspace_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_workspace_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_WORKSPACE_VIEW"
    assert view["source_route"] == SOURCE_ROUTE
    assert view["source_packages"] == ["AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001"]
    assert view["view"]["package_id"] == "AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001"
    assert view["view"]["project_count"] == 0
    assert view["view"]["empty_projects"] is True
    assert view["view"]["empty_knowledge"] is True
    assert view["view"]["authentic_pilot"] is False
    assert view["view"]["pilot_estate_rows"] == []
    assert view["honesty"]["workspace_is_authority"] is False
    assert view["honesty"]["view_is_truth_core"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["honesty"]["unknown_is_healthy"] is False
    assert view["honesty"]["mcp_is_authority"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["workspace_state_written"] is False
    assert view["honesty"]["pilot_invented"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_workspace_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "WORKSPACE != AUTHORITY" in text
    assert "VIEW != TRUTH CORE" in text
    assert "EMPTY != HEALTHY" in text
    assert all(ord(char) < 128 for char in text)


def test_projects_without_ops_snapshot_are_unknown_not_healthy(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    view = read_workspace_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "UNKNOWN_WORKSPACE_VIEW"
    assert view["view"]["project_count"] == 1
    assert view["view"]["read_plane"] == "unread"
    assert view["view"]["rollup"] == "unknown"
    assert view["honesty"]["unknown_is_healthy"] is False
    assert view["honesty"]["workspace_is_authority"] is False
    text = render_workspace_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text


def test_present_ops_snapshot_projects_view_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    _add_project(vault, "north-star")
    _write_ops_snapshot(vault, estate="degraded")
    view = read_workspace_view(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "WORKSPACE_VIEW_PROJECTED"
    assert view["view"]["project_count"] == 2
    assert view["view"]["read_plane"] == "ops_snapshot"
    assert view["honesty"]["workspace_is_authority"] is False
    assert view["honesty"]["view_is_truth_core"] is False
    assert view["honesty"]["authentic_pilot"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY
    text = render_workspace_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text


def test_healthy_ops_rollup_is_still_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    _write_ops_snapshot(vault, estate="healthy")
    view = read_workspace_view(vault)
    assert view["status"] == "PRESENT"
    assert view["view"]["rollup"] == "healthy"
    assert view["honesty"]["workspace_is_authority"] is False
    assert view["honesty"]["view_is_truth_core"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    encoded = json.dumps(view, sort_keys=True)
    assert "HEALTHY" not in encoded or view["honesty"]["empty_is_healthy"] is False
    text = render_workspace_text(view)
    assert "[HEALTHY]" not in text


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_workspace_view(vault)
    assert view["reason_code"] == "EMPTY_WORKSPACE_VIEW"
    assert _snapshot(vault) == before
    assert not (vault / "generated").exists()


def test_read_of_present_view_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    _write_ops_snapshot(vault)
    before = _snapshot(vault)
    read_workspace_view(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    first = read_workspace_view(vault)
    second = read_workspace_view(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_wrap_matches_existing_get_v1_workspace(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    wrapped = read_workspace_view(vault)
    existing = build_workspace_view(vault)
    assert wrapped["view"] == existing
    assert existing["package_id"] == "AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001"


def test_vault_bind_does_not_import_sibling_projects(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _add_project(left, "harbor-api")
    left_view = read_workspace_view(left)
    right_view = read_workspace_view(right)
    assert left_view["status"] == "UNKNOWN"
    assert right_view["status"] == "EMPTY"
    assert left_view["view"]["project_count"] == 1
    assert right_view["view"]["project_count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_write_or_reconcile() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/workspace_read.py").read_text(encoding="utf-8")
    forbidden = (
        "persist_workspace",
        "workspace_reconciler",
        "authentic_estate",
        "_atomic_write",
        "write_text",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_workspace_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.workspace_view()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["honesty"]["workspace_state_written"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["workspace", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["workspace", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["workspace", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert main(["workspace", "report", "--vault", str(tmp_path / "absent"), "--json"]) == EXIT_ERROR


def test_cli_workspace_names_are_free() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    report = parser.parse_args(["workspace", "report", "--vault", "/tmp/vault"])
    assert report.command == "workspace"
    assert report.workspace_command == "report"
    show = parser.parse_args(["workspace", "show", "--vault", "/tmp/vault"])
    assert show.workspace_command == "show"


def test_cli_workspace_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["workspace", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["workspace", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["workspace", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.workspace.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.workspace.write" not in listing["tools"]
    assert "atlas.obs.read" not in listing["tools"]
    assert "atlas.mission.read" not in listing["tools"]


def test_mcp_empty_vault_is_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.workspace.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert result["honesty"]["empty_is_healthy"] is False
    assert result["view"]["authentic_pilot"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.workspace.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.workspace.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.workspace.read", operator=bare)


def test_api_existing_workspace_projection_unchanged(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["workspace_live"] is True
        with urlopen(Request(f"http://{host}:{port}/v1/workspace", headers=auth), timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == "AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001"
        assert body["authentic_pilot"] is False
        assert body["pilot_estate_rows"] == []
        with urlopen(
            Request(f"http://{host}:{port}/v1/workspace/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["status"] == "UNKNOWN"
        assert report["view"] == body
        assert report["honesty"]["owner_capability_granted"] is False
        assert report["honesty"]["WRITE_APPLIED"] is False
        assert report["honesty"]["workspace_is_authority"] is False
        assert report["honesty"]["view_is_truth_core"] is False
    finally:
        server.shutdown()


def test_api_workspace_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/workspace/report",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_and_atlas3_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (root / "src/project_atlas/orchestration/autonomy/authentic_estate.py").read_text(
        encoding="utf-8"
    )
    reconciler = (root / "src/project_atlas/orchestration/sdk/mission_reconciler.py").read_text(
        encoding="utf-8"
    )
    assert "AS-CODER-ALPHA-WORKSPACE-READ-001" not in authentic
    assert "AS-CODER-ALPHA-WORKSPACE-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-WORKSPACE-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
