"""AS-CODER-ALPHA-COMPAT-READ-001 -- vault-scoped compatibility REPORT READ."""

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
from project_atlas.compat_anchor import SNAPSHOT_ID, load_compatibility_anchor
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.compat_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_COMMAND,
    TRUTH_BOUNDARY,
    WebCompatReadError,
    read_compat_view,
    render_compat_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebCompatReadError, match="compat-read-vault-missing"):
        read_compat_view(tmp_path / "absent")


def test_empty_vault_projects_pin_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_compat_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "COMPAT_ANCHOR_PROJECTED"
    assert view["source_command"] == SOURCE_COMMAND
    assert view["source_packages"] == ["AS-2.0-COMPAT-001"]
    assert view["view"]["snapshot_id"] == SNAPSHOT_ID
    assert view["honesty"]["compat_is_authority"] is False
    assert view["honesty"]["anchor_is_truth_core"] is False
    assert view["honesty"]["certified_is_ga"] is False
    assert view["honesty"]["authentic_pilot"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_compat_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text
    assert "COMPAT != AUTHORITY" in text
    assert all(ord(char) < 128 for char in text)


def test_wrap_matches_existing_compat_loader(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    wrapped = read_compat_view(vault)
    existing = load_compatibility_anchor().as_dict()
    assert wrapped["view"] == existing


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    read_compat_view(vault)
    assert _snapshot(vault) == before
    assert not (vault / "generated").exists()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    first = read_compat_view(vault)
    second = read_compat_view(vault)
    assert first == second


def test_reader_module_does_not_write_or_reconcile() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/compat_read.py").read_text(encoding="utf-8")
    forbidden = (
        "persist_",
        "_atomic_write",
        "write_text",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
        "run_governed_experiment",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_compat_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.compat_view()
    assert view["package_id"] == PACKAGE_ID
    assert view["honesty"]["compat_state_written"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["compat", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PRESENT"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["compat", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_verify_remains_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["compat", "verify", "--json"]) == EXIT_OK
    verified = json.loads(capsys.readouterr().out)
    assert verified["snapshot_id"] == SNAPSHOT_ID
    assert "package_id" not in verified
    assert main(["compat", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["view"] == verified


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["compat", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert main(["compat", "report", "--vault", str(tmp_path / "absent"), "--json"]) == EXIT_ERROR


def test_cli_compat_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["compat", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["compat", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.compat.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.compat.write" not in listing["tools"]
    assert "atlas.opt-gate.read" not in listing["tools"]
    assert "atlas.fed.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]


def test_mcp_empty_vault_projects_pin(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.compat.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "PRESENT"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["certified_is_ga"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.compat.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.compat.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.compat.read", operator=bare)


def test_api_compat_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/compat/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["honesty"]["certified_is_ga"] is False
        req = Request(
            f"http://{host}:{port}/v1/compat/report",
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
    assert "AS-CODER-ALPHA-COMPAT-READ-001" not in authentic
    assert "AS-CODER-ALPHA-COMPAT-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-COMPAT-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
