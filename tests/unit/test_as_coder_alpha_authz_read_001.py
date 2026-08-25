"""AS-CODER-ALPHA-AUTHZ-READ-001 -- vault-scoped authz REPORT READ."""

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
from project_atlas.authz import (
    DEFAULT_OPERATOR_CAPS,
    AuthzError,
    OperatorProfile,
    default_operator,
    elevated_operator,
)
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.authz_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_ROUTE,
    TRUTH_BOUNDARY,
    WebAuthzReadError,
    read_authz_profile,
    render_authz_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebAuthzReadError, match="authz-read-vault-missing"):
        read_authz_profile(tmp_path / "absent")


def test_present_vault_projects_existing_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_authz_profile(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "PROFILE_PROJECTED"
    assert view["source_route"] == SOURCE_ROUTE
    assert view["source_packages"] == ["AS-2.1-AUTHZ-001"]
    profile = view["profile"]
    expected = default_operator()
    assert profile == {
        "package_id": "AS-2.1-AUTHZ-001",
        "operator_id": expected.operator_id,
        "capabilities": sorted(expected.capabilities),
        "authority": False,
        "write_enabled": False,
    }
    assert profile["capabilities"] == sorted(DEFAULT_OPERATOR_CAPS)
    assert view["honesty"]["authz_is_authority"] is False
    assert view["honesty"]["profile_is_grant"] is False
    assert view["honesty"]["capability_list_is_owner_gate"] is False
    assert view["honesty"]["WRITE_ENABLED"] is False
    assert view["honesty"]["write_enabled"] is False
    assert view["honesty"]["mcp_is_authority"] is False
    assert view["honesty"]["owner_capability_granted"] is False
    assert view["honesty"]["owner_authority_invented"] is False
    assert view["honesty"]["merge_authority_invented"] is False
    assert view["honesty"]["security_authority_invented"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    assert view["honesty"]["D149_TOUCHED"] == "NO"
    assert view["privileged_capabilities_granted"] == []
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_authz_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text
    assert "AUTHZ != AUTHORITY" in text
    assert "PROFILE != GRANT" in text
    assert "CAPABILITY_LIST != OWNER_GATE" in text
    assert "WRITE_ENABLED=false" in text
    assert all(ord(char) < 128 for char in text)


def test_elevated_profile_is_not_a_grant(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    elev = elevated_operator(
        "elev-reader",
        extra={"vault.write", "autonomy.l3", "web.action"},
    )
    view = read_authz_profile(vault, operator=elev)
    assert view["profile"]["write_enabled"] is False
    assert view["profile"]["authority"] is False
    assert "vault.write" in view["profile"]["capabilities"]
    assert view["privileged_capabilities_listed"] == [
        "autonomy.l3",
        "vault.write",
        "web.action",
    ]
    assert view["privileged_capabilities_granted"] == []
    assert view["honesty"]["profile_is_grant"] is False
    assert view["honesty"]["capability_list_is_owner_gate"] is False
    assert view["honesty"]["WRITE_ENABLED"] is False
    assert view["honesty"]["owner_capability_granted"] is False
    assert view["honesty"]["merge_authorized"] is False
    assert view["honesty"]["security_authority_granted"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_authz_profile(vault)
    assert view["reason_code"] == "PROFILE_PROJECTED"
    assert _snapshot(vault) == before
    assert not (vault / "generated").exists()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    first = read_authz_profile(vault)
    second = read_authz_profile(vault)
    assert first == second
    encoded = json.dumps(first, indent=2, sort_keys=True)
    assert encoded == json.dumps(second, indent=2, sort_keys=True)


def test_vault_bind_does_not_import_sibling_projects(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_view = read_authz_profile(left)
    right_view = read_authz_profile(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "PRESENT"
    assert left_view["profile"] == right_view["profile"]
    assert left_view["honesty"]["WRITE_ENABLED"] is False


def test_reader_module_does_not_grant_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/authz_read.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "elevated_operator",
        "mint_api_session",
        "write_authz_audit_receipt",
        "require_cli_elevated_operator",
        "_atomic_write",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "OWNER_GATE = True",
        "merge_authorized\": True",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_authz_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.authz_profile()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "PRESENT"
    assert view["profile"]["write_enabled"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["authz", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PRESENT"
    assert report["honesty"]["WRITE_ENABLED"] is False
    assert main(["authz", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["authz", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["authz", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_cli_authz_names_are_free() -> None:
    from project_atlas.cli import build_parser

    parser = build_parser()
    report = parser.parse_args(["authz", "report", "--vault", "/tmp/vault"])
    assert report.command == "authz"
    assert report.authz_command == "report"
    show = parser.parse_args(["authz", "show", "--vault", "/tmp/vault"])
    assert show.authz_command == "show"


def test_cli_authz_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["authz", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["authz", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)
    with pytest.raises(SystemExit) as show_info:
        main(["authz", "show", "--help"])
    assert show_info.value.code == 0
    show = capsys.readouterr().out
    assert all(ord(char) < 128 for char in show)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.authz.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.authz.write" not in listing["tools"]
    assert "atlas.obs.read" not in listing["tools"]


def test_mcp_empty_vault_projects_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.authz.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "PRESENT"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["write_applied"] is False
    assert result["honesty"]["WRITE_ENABLED"] is False
    assert result["profile"]["write_enabled"] is False
    assert result["profile"]["authority"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.authz.read", "args": {"elevate": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.authz.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.authz.read", operator=bare)


def test_api_existing_authz_projection_unchanged(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/authz", headers=auth), timeout=2
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == "AS-2.1-AUTHZ-001"
        assert body["authority"] is False
        assert body["write_enabled"] is False
        assert "api.read" in body["capabilities"]
        with urlopen(
            Request(f"http://{host}:{port}/v1/authz/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["status"] == "PRESENT"
        assert report["profile"] == body
        assert report["honesty"]["owner_capability_granted"] is False
        assert report["honesty"]["WRITE_ENABLED"] is False
        assert report["honesty"]["profile_is_grant"] is False
        assert report["honesty"]["capability_list_is_owner_gate"] is False
    finally:
        server.shutdown()


def test_api_authz_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/authz/report",
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
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-AUTHZ-READ-001" not in authentic
    assert "AS-CODER-ALPHA-AUTHZ-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-AUTHZ-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
