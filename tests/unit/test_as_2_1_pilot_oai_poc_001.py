"""AS-2.1 pilot+OAI POC + live hardening tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import ApiServerError, serve_api
from project_atlas.authz import write_authz_audit_receipt
from project_atlas.mcp_server import list_mcp_tools
from project_atlas.openai_responses_poc import (
    READ_ONLY_TOOL_NAMES,
    OpenAIResponsesPocError,
    execute_read_only_tool,
    run_openai_responses_poc,
)
from project_atlas.pilot_auth_prep import (
    is_fixture_or_temp_marker,
    scan_known_pilot_roots,
    write_pilot_prep_report,
)
from project_atlas.web_actions import load_action_ledger


def test_fixture_marker_never_authentic(tmp_path: Path) -> None:
    fixture_root = tmp_path / "tests" / "fixtures" / "pilots" / "nebula"
    fixture_root.mkdir(parents=True)
    marker = fixture_root / ".atlas-project.yaml"
    marker.write_text("project_id: nebula\n", encoding="utf-8")
    assert is_fixture_or_temp_marker(marker) is True
    report = scan_known_pilot_roots(
        candidates=[fixture_root],
        include_workspace_scan=False,
    )
    assert report["authentic_found"] == 0
    assert report["fixture_or_temp_found"] == 1
    assert report["owner_blocked"] is True
    assert report["wake_event"] == "AUTHENTIC_ESTATE_ROOT_AVAILABLE"


def test_authz_audit_receipt(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    receipt = write_authz_audit_receipt(vault, receipt_id="audit-a")
    assert "oai.responses" in receipt["capabilities"]
    assert "vault.write" in receipt["denied_by_default"]
    assert receipt["authority"] is False


def test_mcp_list_tools() -> None:
    listing = list_mcp_tools()
    assert listing["live_mcp_read"] is True
    assert listing["write_tools"] == []
    assert "atlas.ops.health.read" in listing["tools"]


def test_api_actions_ledger_and_mcp_tools(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://{host}:{port}/v1/actions", timeout=2) as resp:
            ledger = json.loads(resp.read().decode("utf-8"))
        assert ledger["transactions"] == []
        with urlopen(f"http://{host}:{port}/v1/mcp/tools", timeout=2) as resp:
            tools = json.loads(resp.read().decode("utf-8"))
        assert tools["write_tools"] == []
        with urlopen(f"http://{host}:{port}/v1/meta", timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["max_post_bytes"] > 0
    finally:
        server.shutdown()


def test_api_rejects_oversized_post(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = b'{"action_id":"x","action_type":"refresh-status"}' + (b"a" * 70_000)
        req = Request(
            f"http://{host}:{port}/v1/actions",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        from urllib.error import HTTPError, URLError

        # Server answers 413 from Content-Length before reading the body and may
        # close the socket. On Windows urllib often surfaces ConnectionAbortedError
        # (WinError 10053) instead of HTTPError — both mean reject-closed.
        try:
            urlopen(req, timeout=5)
            pytest.fail("expected oversized POST rejection")
        except HTTPError as exc:
            assert exc.code == 413
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except URLError as exc:
            reason = exc.reason
            if isinstance(
                reason,
                (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, TimeoutError),
            ):
                pass
            else:
                raise
    finally:
        server.shutdown()


def test_api_non_local_bind_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(ApiServerError, match="non-local"):
        serve_api(vault, host="0.0.0.0", port=0)


def test_oai_poc_offline_ready(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = run_openai_responses_poc(
        vault,
        run_id="poc-off",
        prompt="Summarize vault health using read-only tools only.",
        force_offline=True,
    )
    assert report["experimental"] is True
    assert report["release_blocking"] is False
    assert report["llm_authority"] is False
    assert report["authentic_pilot_substitute"] is False
    assert report["smoke_status"] == "IMPLEMENTATION_READY_FOR_LIVE_SMOKE"
    assert report["write_tools"] == []
    assert set(report["read_only_tools"]) == set(READ_ONLY_TOOL_NAMES)
    assert report["quarantine"]["status"] == "quarantined"


def test_oai_poc_rejects_write_tool(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(OpenAIResponsesPocError, match="write-or-unknown"):
        execute_read_only_tool(vault, "atlas_vault_write")


def test_pilot_prep_full_scan_keys(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = write_pilot_prep_report(
        vault,
        report_id="prep-b",
        candidates=[tmp_path / "missing-estate"],
        include_workspace_scan=False,
    )
    assert "wake_event" in report
    assert report["pilot_pass"] is False
    _ = load_action_ledger(vault)
