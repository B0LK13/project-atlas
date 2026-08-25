"""AS-CODER-ALPHA-CONTEXT-PACK-READ-001 -- vault-scoped context-pack REPORT READ."""

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
from project_atlas.web_api.context_pack_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    WebContextPackReadError,
    read_context_pack_view,
    render_context_pack_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_pack(vault: Path, name: str = "alpha-context-pack.json") -> None:
    path = vault / "generated" / "context" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_id": "AS-2.0-CTX-001",
                "pack_id": "alpha",
                "fixture_safe": True,
                "estate_facts_invented": False,
                "provenance_pointers": [{"ref": "src:readme", "kind": "source"}],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebContextPackReadError, match="context-pack-read-vault-missing"):
        read_context_pack_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_context_pack_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_CONTEXT_PACK_VIEW"
    assert view["honesty"]["pack_is_estate_facts"] is False
    assert view["honesty"]["pack_is_truth_core"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_context_pack_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_present_pack_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_pack(vault)
    view = read_context_pack_view(vault)
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["view"]["artifact_count"] == 1
    assert view["view"]["estate_facts_invented"] is False
    text = render_context_pack_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text


def test_invented_estate_facts_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "context" / "evil.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"estate_facts_invented": True}) + "\n", encoding="utf-8")
    with pytest.raises(WebContextPackReadError, match="estate-facts-invented"):
        read_context_pack_view(vault)


def test_malformed_only_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "context" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_context_pack_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["honesty"]["unknown_is_healthy"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_pack(vault)
    before = _snapshot(vault)
    read_context_pack_view(vault)
    assert _snapshot(vault) == before


def test_reader_module_does_not_build() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/context_pack_read.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "from project_atlas.context_pack import",
        "from project_atlas.runtime_22 import",
        "build_context_pack(",
        "compile_context(",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
        "_atomic_write",
        "write_text(",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_context_pack_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.context_pack_view()
    assert view["status"] == "EMPTY"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["context-pack", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert main(["context-pack", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out) == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["context-pack", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert main(["context-pack", "report", "--vault", str(missing), "--json"]) == EXIT_ERROR


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["context-pack", "--help"])
    assert exit_info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.context-pack.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.compat.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]
    assert "atlas.twin.read" not in listing["tools"]


def test_mcp_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.context-pack.read")
    assert report["result"]["status"] == "EMPTY"
    assert report["result"]["honesty"]["mcp_is_authority"] is False


def test_mcp_args_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.context-pack.read", "args": {"pack": "x"}}),
        )


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.context-pack.read", operator=bare)


def test_api_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/context-pack/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        req = Request(
            f"http://{host}:{port}/v1/context-pack/report",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_d149_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    authentic = (root / "src/project_atlas/orchestration/autonomy/authentic_estate.py").read_text(
        encoding="utf-8"
    )
    assert "AS-CODER-ALPHA-CONTEXT-PACK-READ-001" not in authentic
