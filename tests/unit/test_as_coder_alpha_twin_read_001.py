"""AS-CODER-ALPHA-TWIN-READ-001 -- vault-scoped twin-fixture REPORT READ."""

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
from project_atlas.web_api.twin_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_COMMAND,
    TRUTH_BOUNDARY,
    WebTwinReadError,
    read_twin_view,
    render_twin_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_fixture(vault: Path, name: str = "harbor.json") -> None:
    path = vault / "generated" / "ops" / "twin-fixtures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_id": "AS-2.0-TWIN-FIXTURE-001",
                "projection_id": "harbor",
                "fixture_class": "disposable",
                "estate_pilot_passed": False,
                "twin_production_ready": False,
                "twin_001_status": "BLOCKED",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebTwinReadError, match="twin-read-vault-missing"):
        read_twin_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_twin_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_TWIN_VIEW"
    assert view["source_command"] == SOURCE_COMMAND
    assert view["honesty"]["fixture_is_pilot"] is False
    assert view["honesty"]["fixture_is_twin_production_ready"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_twin_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "TWIN FIXTURE != PILOT" in text
    assert all(ord(char) < 128 for char in text)


def test_present_fixture_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_fixture(vault)
    view = read_twin_view(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["view"]["artifact_count"] == 1
    assert view["view"]["estate_pilot_passed"] is False
    text = render_twin_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text


def test_invented_pilot_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "twin-fixtures" / "evil.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"estate_pilot_passed": True}) + "\n", encoding="utf-8")
    with pytest.raises(WebTwinReadError, match="estate-pilot-invented"):
        read_twin_view(vault)


def test_invented_production_ready_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "twin" / "evil.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"twin_production_ready": True}) + "\n", encoding="utf-8")
    with pytest.raises(WebTwinReadError, match="twin-production-ready-invented"):
        read_twin_view(vault)


def test_malformed_only_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "twin-fixtures" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_twin_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["honesty"]["unknown_is_healthy"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_fixture(vault)
    before = _snapshot(vault)
    read_twin_view(vault)
    assert _snapshot(vault) == before


def test_reader_module_does_not_build() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/twin_read.py").read_text(encoding="utf-8")
    forbidden = (
        "from project_atlas.twin_fixtures import",
        "from project_atlas.twin_production import",
        "from project_atlas.twin_fixture_scenarios import",
        "build_twin_projection_fixture(",
        "build_twin_production_projection(",
        "build_twin_fixture_scenario(",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
        "_atomic_write",
        "write_text(",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_twin_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.twin_view()
    assert view["status"] == "EMPTY"
    assert view["honesty"]["twin_state_written"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["twin-fixture", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["twin-fixture", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_build_remains_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(SystemExit) as build_help:
        main(["twin-fixture", "build", "--help"])
    assert build_help.value.code == 0
    text = capsys.readouterr().out
    assert "--projection-id" in text
    before = _snapshot(vault)
    assert main(["twin-fixture", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert _snapshot(vault) == before


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["twin-fixture", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert main(["twin-fixture", "report", "--vault", str(missing), "--json"]) == EXIT_ERROR


def test_cli_twin_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["twin-fixture", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["twin-fixture", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.twin.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.twin.write" not in listing["tools"]
    assert "atlas.compat.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]


def test_mcp_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.twin.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["fixture_is_pilot"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.twin.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.twin.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.twin.read", operator=bare)


def test_api_twin_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/twin-fixture/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["honesty"]["fixture_is_pilot"] is False
        req = Request(
            f"http://{host}:{port}/v1/twin-fixture/report",
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
    assert "AS-CODER-ALPHA-TWIN-READ-001" not in authentic
    assert "AS-CODER-ALPHA-TWIN-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-TWIN-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
