"""AS-CODER-ALPHA-FED-READ-001 -- vault-scoped federation REPORT READ."""

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
from project_atlas.web_api.fed_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebFedReadError,
    read_fed_view,
    render_fed_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_lens(vault: Path, name: str = "alpha.json") -> None:
    path = vault / "generated" / "ops" / "federation" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_id": "AS-2.0-FED-002",
                "lens_id": "alpha",
                "federation_id": "demo-fed",
                "cross_vault_promote": False,
                "members_visible": ["harbor-api"],
                "authority": {"level": "derived"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebFedReadError, match="fed-read-vault-missing"):
        read_fed_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_fed_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_FED_VIEW"
    assert view["view"]["artifact_count"] == 0
    assert view["honesty"]["fed_is_authority"] is False
    assert view["honesty"]["fed_is_cross_vault_promote"] is False
    assert view["honesty"]["empty_is_healthy"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_fed_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_present_consume_only_lens_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_lens(vault)
    view = read_fed_view(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "FED_VIEW_PROJECTED"
    assert view["view"]["artifact_count"] == 1
    assert view["view"]["cross_vault_promote"] is False
    assert view["honesty"]["fed_is_authority"] is False
    text = render_fed_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text


def test_malformed_only_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "federation" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_fed_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["reason_code"] == "UNKNOWN_FED_VIEW"
    assert view["honesty"]["unknown_is_healthy"] is False


def test_cross_promote_artifact_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "federation" / "evil.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"cross_vault_promote": True, "federation_id": "x"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WebFedReadError, match="fed-read-cross-promote-forbidden"):
        read_fed_view(vault)


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_lens(vault)
    before = _snapshot(vault)
    read_fed_view(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_lens(vault)
    assert read_fed_view(vault) == read_fed_view(vault)


def test_reader_module_does_not_build_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/fed_read.py").read_text(encoding="utf-8")
    forbidden = (
        "from project_atlas.federation_lens",
        "from project_atlas.federation import",
        "build_federation_read_lens(",
        "build_join_inventory(",
        "persist_",
        "_atomic_write",
        "write_text(",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_fed_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.fed_view()
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["federation", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["federation", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["federation", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert main(["federation", "report", "--vault", str(missing), "--json"]) == EXIT_ERROR


def test_cli_federation_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["federation", "--help"])
    assert exit_info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)
    with pytest.raises(SystemExit) as report_info:
        main(["federation", "report", "--help"])
    assert report_info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.fed.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.fed.write" not in listing["tools"]
    assert "atlas.compat.read" not in listing["tools"]
    assert "atlas.opt-gate.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]


def test_mcp_empty_vault_is_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.fed.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.fed.read", "args": {"promote": True}}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.fed.read", operator=bare)


def test_api_fed_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/fed/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["status"] == "EMPTY"
        req = Request(
            f"http://{host}:{port}/v1/fed/report",
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
    assert "AS-CODER-ALPHA-FED-READ-001" not in authentic
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-FED-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
