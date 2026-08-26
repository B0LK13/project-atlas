"""AS-CODER-ALPHA-RUNTIME-READ-001 -- vault-scoped runtime REPORT READ."""

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
from project_atlas.web_api.runtime_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_COMMAND,
    TRUTH_BOUNDARY,
    WebRuntimeReadError,
    read_runtime_view,
    render_runtime_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_index(vault: Path, name: str = "concepts.jsonl") -> None:
    path = vault / "generated" / "indexes" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"record_id":"c1"}\n', encoding="utf-8")


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebRuntimeReadError, match="runtime-read-vault-missing"):
        read_runtime_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_runtime_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_RUNTIME_VIEW"
    assert view["source_command"] == SOURCE_COMMAND
    assert view["honesty"]["runtime_is_authority"] is False
    assert view["honesty"]["indexes_are_truth_core"] is False
    assert view["honesty"]["hybrid_invoked"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_runtime_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert "RUNTIME != AUTHORITY" in text
    assert all(ord(char) < 128 for char in text)


def test_present_indexes_are_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_index(vault)
    view = read_runtime_view(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["view"]["index_file_count"] == 1
    assert view["view"]["hybrid_invoked"] is False
    text = render_runtime_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text


def test_malformed_ops_only_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "runtime" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_runtime_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["honesty"]["unknown_is_healthy"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_index(vault)
    before = _snapshot(vault)
    read_runtime_view(vault)
    assert _snapshot(vault) == before


def test_reader_module_does_not_invoke_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/runtime_read.py").read_text(encoding="utf-8")
    forbidden = (
        "from project_atlas.runtime_22 import",
        "hybrid_retrieve(",
        "compile_context(",
        "write_context_compiler",
        "build_context_pack(",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
        "_atomic_write",
        "write_text(",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_runtime_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.runtime_view()
    assert view["status"] == "EMPTY"
    assert view["honesty"]["runtime_state_written"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["runtime", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["runtime", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_existing_runtime_commands_remain(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as hybrid:
        main(["runtime", "hybrid-retrieve", "--help"])
    assert hybrid.value.code == 0
    hybrid_help = capsys.readouterr().out
    assert "--project" in hybrid_help
    with pytest.raises(SystemExit) as compile_info:
        main(["runtime", "compile-context", "--help"])
    assert compile_info.value.code == 0
    compile_help = capsys.readouterr().out
    assert "--write" in compile_help


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["runtime", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert main(["runtime", "report", "--vault", str(tmp_path / "absent"), "--json"]) == EXIT_ERROR


def test_cli_runtime_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["runtime", "--help"])
    assert exit_info.value.code == 0
    parent = capsys.readouterr().out
    assert all(ord(char) < 128 for char in parent)
    with pytest.raises(SystemExit) as report_info:
        main(["runtime", "report", "--help"])
    assert report_info.value.code == 0
    report = capsys.readouterr().out
    assert all(ord(char) < 128 for char in report)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.runtime.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.runtime.write" not in listing["tools"]
    assert "atlas.compat.read" not in listing["tools"]
    assert "atlas.twin.read" not in listing["tools"]
    assert "atlas.context-pack.read" not in listing["tools"]


def test_mcp_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.runtime.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["hybrid_invoked"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.runtime.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.runtime.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.runtime.read", operator=bare)


def test_api_runtime_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/runtime/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["honesty"]["runtime_is_authority"] is False
        req = Request(
            f"http://{host}:{port}/v1/runtime/report",
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
    assert "AS-CODER-ALPHA-RUNTIME-READ-001" not in authentic
    assert "AS-CODER-ALPHA-RUNTIME-READ-001" not in reconciler
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-RUNTIME-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
