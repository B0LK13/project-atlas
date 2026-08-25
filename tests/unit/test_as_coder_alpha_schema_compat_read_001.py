"""AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001 — vault-scoped REPORT READ lens."""

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
from project_atlas.schema_compat import SchemaCompatError, read_report, scan_compat
from project_atlas.web_api.schema_compat import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebSchemaCompatError,
    read_schema_compat,
    render_schema_compat_text,
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
    with pytest.raises(WebSchemaCompatError, match="schema-compat-vault-missing"):
        read_schema_compat(tmp_path / "absent")


def test_missing_report_is_unknown_not_compatible(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert read_report(vault) is None
    view = read_schema_compat(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["report_present"] is False
    assert view["report"] is None
    assert view["reason_code"] == "REPORT_ABSENT"
    assert view["honesty"]["missing_is_compatible"] is False
    assert view["honesty"]["report_is_authority"] is False
    assert view["honesty"]["schema_compat_is_migration_apply"] is False
    assert view["honesty"]["lens_is_truth_core"] is False
    assert view["honesty"]["migration_applied"] is False
    text = render_schema_compat_text(view)
    assert "[UNKNOWN]" in text
    assert "[COMPATIBLE]" not in text
    assert "[HEALTHY]" not in text


def test_empty_report_file_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "schema-compat-report.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SchemaCompatError, match="malformed schema-compat report"):
        read_report(vault)
    with pytest.raises(WebSchemaCompatError, match="schema-compat-report-unreadable"):
        read_schema_compat(vault)


def test_present_report_is_visible_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    written = scan_compat(vault)
    view = read_schema_compat(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["report_present"] is True
    assert view["report_status"] == written["status"]
    assert view["report"] == written
    assert view["honesty"]["report_is_authority"] is False
    assert view["honesty"]["ok_is_migration_apply"] is False
    assert view["truth_boundary"] == TRUTH_BOUNDARY


def test_read_does_not_write_or_migrate(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    view = read_schema_compat(vault)
    assert view["reason_code"] == "REPORT_ABSENT"
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "schema-compat-report.json").exists()


def test_read_of_present_report_does_not_rewrite(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    scan_compat(vault)
    before = _snapshot(vault)
    read_schema_compat(vault)
    read_report(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    scan_compat(vault)
    first = read_schema_compat(vault)
    second = read_schema_compat(vault)
    assert first == second


def test_symlink_report_is_path_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside-report.json"
    outside.write_text('{"hijack": true}\n', encoding="utf-8")
    target = vault / "generated" / "ops" / "schema-compat-report.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(SchemaCompatError, match="not a regular file"):
        read_report(vault)
    with pytest.raises(WebSchemaCompatError, match="schema-compat-report-unreadable"):
        read_schema_compat(vault)


def test_vault_bind_does_not_import_sibling_report(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    scan_compat(left)
    left_view = read_schema_compat(left)
    right_view = read_schema_compat(right)
    assert left_view["status"] == "PRESENT"
    assert right_view["status"] == "UNKNOWN"
    assert right_view["report"] is None
    assert right_view["available"] is False


def test_appservice_schema_compat(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.schema_compat()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "UNKNOWN"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_missing_report(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["schema", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    assert main(["schema", "show", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["schema", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["schema", "report", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_schema_compat_write_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    help_text = build_parser().format_help()
    assert "schema" in help_text
    schema_help = build_parser().parse_args
    _ = schema_help
    parser = build_parser()
    schema = next(
        action
        for action in parser._subparsers._group_actions  # noqa: SLF001
        if action.dest == "command"
    )
    assert "schema" in (schema.choices or {})


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.schema.compat.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.schema.compat.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.schema.compat.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["schema_compat_is_migration_apply"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.schema.compat.read", "args": {"migrate": True}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.schema.compat.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.schema.compat.read", operator=bare)


def test_api_schema_compat_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    scan_compat(vault)
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
        assert meta["schema_compat_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/schema-compat", headers=auth),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "PRESENT"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
        assert body["honesty"]["migration_applied"] is False
    finally:
        server.shutdown()


def test_api_schema_compat_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/schema-compat",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_surfaces_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001" not in authentic
    assert "AS-CODER-ALPHA-SCHEMA-COMPAT-READ-001" not in reconciler
    assert "schema_compat" not in reconciler
