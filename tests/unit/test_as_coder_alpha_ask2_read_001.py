"""AS-CODER-ALPHA-ASK2-READ-001 -- vault-scoped Ask Atlas 2 REPORT READ."""

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
from project_atlas.web_api.ask2_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_COMMAND,
    TRUTH_BOUNDARY,
    WebAsk2ReadError,
    read_ask2_view,
    render_ask2_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _write_answer(vault: Path, *, name: str = "answer.json", **fields: object) -> None:
    path = vault / "generated" / "ops" / "ask" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "package_id": "AS-2.2-ASK2-001",
        "artifact_kind": "ask-atlas-2-answer",
        "status": "UNKNOWN",
        "authentic_pilot": False,
        **fields,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebAsk2ReadError, match="ask2-read-vault-missing"):
        read_ask2_view(tmp_path / "absent")


def test_empty_vault_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_ask2_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "EMPTY"
    assert view["available"] is False
    assert view["reason_code"] == "EMPTY_ASK2_VIEW"
    assert view["source_command"] == SOURCE_COMMAND
    assert view["honesty"]["ask2_report_is_answer"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["ask2_invoked"] is False
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_ask2_text(view)
    assert "[EMPTY]" in text
    assert "[HEALTHY]" not in text
    assert all(ord(char) < 128 for char in text)


def test_present_artifact_is_not_an_answer(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_answer(vault, answer_id="ask2-a", project_id="harbor-api")
    view = read_ask2_view(vault)
    assert view["status"] == "PRESENT"
    assert view["view"]["artifact_count"] == 1
    assert view["view"]["project_ids"] == ["harbor-api"]
    assert view["view"]["ask2_invoked"] is False
    assert view["honesty"]["ask2_report_is_answer"] is False
    assert "[HEALTHY]" not in render_ask2_text(view)


def test_invented_pilot_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_answer(vault, authentic_pilot=True)
    with pytest.raises(WebAsk2ReadError, match="authentic-pilot-invented"):
        read_ask2_view(vault)


def test_malformed_only_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    path = vault / "generated" / "ops" / "ask" / "broken.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n", encoding="utf-8")
    view = read_ask2_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["honesty"]["unknown_is_healthy"] is False


def test_mixed_valid_and_corrupt_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_answer(vault, name="good.json", answer_id="ask2-a", project_id="harbor-api")
    bad = vault / "generated" / "ops" / "ask" / "bad.json"
    bad.write_text("not-json\n", encoding="utf-8")
    view = read_ask2_view(vault)
    assert view["status"] == "UNKNOWN"
    assert view["available"] is False
    assert view["view"]["artifact_count"] == 1
    assert view["view"]["malformed_count"] == 1
    assert "[HEALTHY]" not in render_ask2_text(view)


def test_same_id_altered_payload_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_answer(vault, name="one.json", answer_id="ask2-dup", project_id="alpha")
    _write_answer(vault, name="two.json", answer_id="ask2-dup", project_id="beta")
    with pytest.raises(WebAsk2ReadError, match="ask2-read-id-collision"):
        read_ask2_view(vault)


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_answer(vault, answer_id="ask2-a")
    before = _snapshot(vault)
    read_ask2_view(vault)
    assert _snapshot(vault) == before


def test_reader_module_does_not_ask() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/ask2_read.py").read_text(encoding="utf-8")
    forbidden = (
        "from project_atlas.ask2 import",
        "ask_atlas_2(",
        "from project_atlas.hybrid_retrieval",
        "compile_context",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "_atomic_write",
        "write_text(",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_ask2_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert open_app_service(vault).ask2_view()["status"] == "EMPTY"
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["ask2-status", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "EMPTY"
    assert main(["ask2-status", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out) == report


def test_cli_ask2_lens_help_remains(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["ask2", "--help"])
    assert info.value.code == 0
    text = capsys.readouterr().out
    assert "--question" in text
    assert "--project" in text


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["ask2-status", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert main(["ask2-status", "report", "--vault", str(missing), "--json"]) == EXIT_ERROR


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["ask2-status", "report", "--help"])
    assert info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.ask2.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.query.read" not in listing["tools"]
    assert "atlas.graph.read" not in listing["tools"]


def test_mcp_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    result = invoke_mcp_tool(vault, "atlas.ask2.read")["result"]
    assert result["status"] == "EMPTY"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["ask2_invoked"] is False


def test_mcp_args_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ask2.read", "args": {"question": "what"}}),
        )


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.ask2.read", operator=bare)


def test_api_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        url = f"http://{host}:{port}/v1/ask2/report"
        with urlopen(Request(url, headers=auth), timeout=2) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        req = Request(
            f"http://{host}:{port}/v1/ask2/report",
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
    assert "AS-CODER-ALPHA-ASK2-READ-001" not in authentic
