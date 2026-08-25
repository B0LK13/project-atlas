"""AS-CODER-ALPHA-OPT-GATE-READ-001 -- vault-scoped opt-gate REPORT READ."""

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
from project_atlas.opt_gate import ATLAS_OPT_WAKE_GATE
from project_atlas.web_api.opt_gate_read import (
    HONESTY_STATEMENTS,
    PACKAGE_ID,
    SOURCE_SURFACE,
    TRUTH_BOUNDARY,
    WebOptGateReadError,
    read_opt_gate_view,
    render_opt_gate_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebOptGateReadError, match="opt-gate-read-vault-missing"):
        read_opt_gate_view(tmp_path / "absent")


def test_empty_vault_projects_policies_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    view = read_opt_gate_view(vault)
    assert view["package_id"] == PACKAGE_ID
    assert view["status"] == "PRESENT"
    assert view["available"] is True
    assert view["reason_code"] == "OPT_GATE_POLICIES_PROJECTED"
    assert view["source_surface"] == SOURCE_SURFACE
    assert view["view"]["wake_gate"] == ATLAS_OPT_WAKE_GATE
    assert view["view"]["wake_gate"] == "CLOSED"
    assert view["honesty"]["opt_gate_is_opt"] is False
    assert view["honesty"]["promote_eligible_is_merged"] is False
    assert view["honesty"]["promote_eligible_is_deployed"] is False
    assert view["honesty"]["opt_woken"] is False
    assert view["honesty"]["experiment_run"] is False
    assert view["honesty"]["envelope_sealed"] is False
    assert view["honesty"]["WRITE_APPLIED"] is False
    assert view["honesty"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    encoded = json.dumps(view, sort_keys=True)
    for statement in HONESTY_STATEMENTS:
        assert statement in encoded
    text = render_opt_gate_text(view)
    assert "[PRESENT]" in text
    assert "[HEALTHY]" not in text
    assert "OPT-GATE != OPT" in text
    assert all(ord(char) < 128 for char in text)


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    read_opt_gate_view(vault)
    assert _snapshot(vault) == before
    assert not (vault / "generated").exists()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert read_opt_gate_view(vault) == read_opt_gate_view(vault)


def test_reader_module_does_not_run_or_wake() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/web_api/opt_gate_read.py").read_text(encoding="utf-8")
    forbidden = (
        "run_governed_experiment",
        "seal_experiment",
        "decide_promotion",
        "GovernedExperimentSession",
        "persist_",
        "_atomic_write",
        "write_text",
        "from project_atlas.ingestion",
        "knowledge_compiler",
        "from project_atlas.atlas3",
        "OWNER_GATE = True",
    )
    for name in forbidden:
        assert name not in source


def test_appservice_opt_gate_view(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    service = open_app_service(vault)
    view = service.opt_gate_view()
    assert view["package_id"] == PACKAGE_ID
    assert view["honesty"]["opt_gate_state_written"] is False
    with pytest.raises(AppServiceError, match="app-svc-vault-missing"):
        open_app_service(tmp_path / "absent")


def test_cli_json_report_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["opt-gate", "report", "--vault", str(vault), "--json"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PRESENT"
    assert report["honesty"]["WRITE_APPLIED"] is False
    assert main(["opt-gate", "show", "--vault", str(vault), "--json"]) == EXIT_OK
    show = json.loads(capsys.readouterr().out)
    assert show == report


def test_cli_report_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    assert main(["opt-gate", "report", "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert main(["opt-gate", "report", "--vault", str(tmp_path / "absent"), "--json"]) == EXIT_ERROR


def test_cli_opt_gate_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["opt-gate", "--help"])
    assert exit_info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)
    with pytest.raises(SystemExit) as report_info:
        main(["opt-gate", "report", "--help"])
    assert report_info.value.code == 0
    assert all(ord(char) < 128 for char in capsys.readouterr().out)


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.opt-gate.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.opt-gate.write" not in listing["tools"]
    assert "atlas.compat.read" not in listing["tools"]
    assert "atlas.fed.read" not in listing["tools"]
    assert "atlas.runtime.read" not in listing["tools"]


def test_mcp_empty_vault_projects_policies(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.opt-gate.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "PRESENT"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["opt_woken"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.opt-gate.read", "args": {"wake_opt": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.opt-gate.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.opt-gate.read", operator=bare)


def test_api_opt_gate_report_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/opt-gate/report", headers=auth),
            timeout=2,
        ) as resp:
            report = json.loads(resp.read().decode("utf-8"))
        assert report["package_id"] == PACKAGE_ID
        assert report["truth_boundary"] == TRUTH_BOUNDARY
        assert report["honesty"]["promote_eligible_is_merged"] is False
        req = Request(
            f"http://{host}:{port}/v1/opt-gate/report",
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
    assert "AS-CODER-ALPHA-OPT-GATE-READ-001" not in authentic
    atlas3 = root / "src/project_atlas/atlas3"
    if atlas3.exists():
        for path in atlas3.rglob("*"):
            if path.is_file():
                assert "AS-CODER-ALPHA-OPT-GATE-READ-001" not in path.read_text(
                    encoding="utf-8", errors="ignore"
                )
