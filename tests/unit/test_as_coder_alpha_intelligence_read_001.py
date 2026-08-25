"""AS-CODER-ALPHA-INTELLIGENCE-READ-001 -- vault-scoped intelligence REPORT READ."""

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
from project_atlas.web_api.intelligence_read import (
    HONESTY_STATEMENTS,
    INTELLIGENCE_ROUTES,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebIntelligenceReadError,
    read_intelligence_index,
    render_intelligence_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _add_project(vault: Path, project_id: str) -> None:
    (vault / "projects" / project_id).mkdir(parents=True)


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebIntelligenceReadError, match="intel-read-vault-missing"):
        read_intelligence_index(tmp_path / "absent")


def test_missing_projects_are_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_intelligence_index(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "PROJECTS_ABSENT"
    assert view["projects"]["status"] == "MISSING"
    assert view["projects"]["count"] == 0
    assert [row["path"] for row in view["routes"]] == [row["path"] for row in INTELLIGENCE_ROUTES]
    assert view["honesty"]["intelligence_is_authority"] is False
    assert view["honesty"]["graph_is_authority"] is False
    assert view["honesty"]["derived_is_truth_core"] is False
    assert view["honesty"]["unknown_is_healthy"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["answers_computed"] is False
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_intelligence_text(view)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_empty_projects_are_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    view = read_intelligence_index(vault)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "PROJECTS_EMPTY"
    assert view["available"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["projects"]["status"] == "EMPTY"
    assert view["projects"]["count"] == 0
    text = render_intelligence_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text


def test_present_projects_index_routes_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    _add_project(vault, "north-star")
    view = read_intelligence_index(vault)
    assert view["status"] == "INDEXED"
    assert view["available"] is True
    assert view["reason_code"] == "ROUTES_INDEXED"
    assert view["projects"]["project_ids"] == ["harbor-api", "north-star"]
    assert view["honesty"]["intelligence_is_authority"] is False
    assert view["honesty"]["graph_is_authority"] is False
    assert view["honesty"]["derived_is_truth_core"] is False
    assert view["honesty"]["answers_computed"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY
    for route in view["routes"]:
        assert route["writes_layer_b"] is False
        assert route["is_authority"] is False
        assert route["graph_is_authority"] is False
        assert route["derived_is_truth_core"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_intelligence_index(vault)
    assert view["reason_code"] == "PROJECTS_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "projects").exists()


def test_read_of_present_projects_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    before = _snapshot(vault)
    read_intelligence_index(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    first = read_intelligence_index(vault)
    second = read_intelligence_index(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_symlink_project_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-project"
    outside.mkdir()
    target = vault / "projects" / "hijack"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(WebIntelligenceReadError, match="intel-read-not-regular-dir"):
        read_intelligence_index(vault)


def test_vault_bind_does_not_import_sibling_projects(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _add_project(left, "harbor-api")
    left_view = read_intelligence_index(left)
    right_view = read_intelligence_index(right)
    assert left_view["status"] == "INDEXED"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["projects"]["count"] == 0
    assert right_view["available"] is False


def test_reader_module_does_not_compute_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/intelligence_read.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "query_intelligence",
        "read_intelligence_evidence",
        "read_intelligence_conflicts",
        "read_intelligence_explain",
        "read_intelligence_query",
        "knowledge_compiler",
        "_atomic_write",
        "from project_atlas.intelligence",
        "from project_atlas.web_api.intelligence",
        "from project_atlas.ingestion",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_intelligence_index(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.intelligence_index()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_projects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["intelligence", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "UNKNOWN"
    assert main(["intelligence", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["intelligence", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["intelligence", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_cli_intelligence_names_are_free() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    report = parser.parse_args(["intelligence", "report", "--vault", "/tmp/vault"])
    assert report.command == "intelligence"
    assert report.intelligence_command == "report"
    show = parser.parse_args(["intelligence", "show", "--vault", "/tmp/vault"])
    assert show.intelligence_command == "show"


def test_cli_intelligence_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["intelligence", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["intelligence", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["intelligence", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.intelligence.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.intelligence.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.intelligence.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert result["honesty"]["unknown_is_healthy"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.intelligence.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.intelligence.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.intelligence.read", operator=bare)


def test_api_intelligence_index_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _add_project(vault, "harbor-api")
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2
        ) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["intelligence_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/intelligence", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "INDEXED"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["WRITE_APPLIED"] is False
        assert body["honesty"]["graph_is_authority"] is False
        assert body["honesty"]["derived_is_truth_core"] is False
    finally:
        server.shutdown()


def test_api_intelligence_index_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/intelligence",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_existing_intelligence_subroutes_still_require_project(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        for suffix in ("evidence", "conflicts", "explain", "query"):
            req = Request(
                f"http://{host}:{port}/v1/intelligence/{suffix}",
                headers=auth,
            )
            with pytest.raises(HTTPError) as exc:
                urlopen(req, timeout=2)
            assert exc.value.code == 400
            body = json.loads(exc.value.read().decode("utf-8"))
            assert body["error"] == "intel-api-project-id-required"
            assert body["package_id"] == "AS-2.0-API-001"
    finally:
        server.shutdown()


def test_d149_and_atlas3_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-INTELLIGENCE-READ-001" not in authentic
    assert "AS-CODER-ALPHA-INTELLIGENCE-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-INTELLIGENCE-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
