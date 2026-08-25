"""AS-CODER-ALPHA-OPS-EVENTS-READ-001 — vault-scoped ops-event stream read."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.ops_events import STREAM_RELATIVE, append_event
from project_atlas.ops_events_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    OpsEventsReadError,
    build_ops_events_read,
    render_ops_events_read_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _append(vault: Path, event_id: str = "OPS-EVT-CI-FAILED") -> dict[str, object]:
    return append_event(
        vault,
        event_id=event_id,
        payload={"workflow": "ci", "commit": "abc"},
        evidence_refs=["generated/ops/evidence/ci-status.json"],
        apply_caps=False,
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(OpsEventsReadError, match="ops-events-vault-missing"):
        build_ops_events_read(tmp_path / "absent")


def test_empty_vault_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_ops_events_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "STREAM_ABSENT"
    assert report["event_count"] == 0
    assert report["events"] == []
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["fabricated_events"] is False
    assert report["honesty"]["health_transition_recorded"] is False
    assert report["honesty"]["retention_applied"] is False
    text = render_ops_events_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[FRESH]" not in text


def test_empty_stream_file_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    stream = vault / STREAM_RELATIVE
    stream.parent.mkdir(parents=True)
    stream.write_text("", encoding="utf-8")
    report = build_ops_events_read(vault)
    assert report["status"] == "EMPTY"
    assert report["available"] is True
    assert report["reason_code"] == "STREAM_EMPTY"
    assert report["event_count"] == 0
    assert report["events"] == []
    assert report["status"] != "HEALTHY"
    assert report["honesty"]["empty_is_healthy"] is False


def test_recorded_events_are_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    event = _append(vault)
    report = build_ops_events_read(vault)
    assert report["status"] == "RECORDED"
    assert report["available"] is True
    assert report["event_count"] == 1
    assert report["returned_count"] == 1
    assert report["events"][0]["event_uid"] == event["event_uid"]
    assert report["events"][0]["authority_plane"] == "none"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["ops_events_are_authority"] is False
    assert report["status"] != "HEALTHY"
    assert report["status"] != "FRESH"


def test_corrupt_stream_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    stream = vault / STREAM_RELATIVE
    stream.parent.mkdir(parents=True)
    stream.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(OpsEventsReadError, match="corrupt JSONL"):
        build_ops_events_read(vault)


def test_limit_rejects_out_of_range(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(OpsEventsReadError, match="ops-events-limit-out-of-range"):
        build_ops_events_read(vault, limit=0)
    with pytest.raises(OpsEventsReadError, match="ops-events-limit-out-of-range"):
        build_ops_events_read(vault, limit=501)


def test_limit_returns_newest_events(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    first = _append(vault, "OPS-EVT-SYNC-STARTED")
    second = _append(vault, "OPS-EVT-SYNC-SUCCEEDED")
    third = _append(vault, "OPS-EVT-BACKUP-COMPLETED")
    report = build_ops_events_read(vault, limit=2)
    assert report["event_count"] == 3
    assert report["returned_count"] == 2
    assert report["truncated"] is True
    assert [row["event_uid"] for row in report["events"]] == [
        second["event_uid"],
        third["event_uid"],
    ]
    assert first["event_uid"] not in {row["event_uid"] for row in report["events"]}


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_ops_events_read(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _append(vault)
    first = build_ops_events_read(vault)
    second = build_ops_events_read(vault)
    assert first == second


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["ops-events", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_corrupt_stream_exits_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    stream = vault / STREAM_RELATIVE
    stream.parent.mkdir(parents=True)
    stream.write_text("{not-json\n", encoding="utf-8")
    assert main(["ops-events", "--vault", str(vault), "--json"]) == EXIT_ERROR


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.ops.events.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.ops.events.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_healthy"] is False
    assert result["events"] == []


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.events.read", "args": {"limit": 1}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.events.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.ops.events.read", operator=bare)


def test_api_ops_events_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _append(vault)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["ops_events_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/ops/events", headers=auth), timeout=2
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "RECORDED"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_ops_events_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        from urllib.error import HTTPError
        from urllib.request import Request as UrlRequest

        req = UrlRequest(
            f"http://{host}:{port}/v1/ops/events",
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
    """This package must not rewrite authentic-estate / owner-gate modules."""
    from pathlib import Path as P

    root = P(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-OPS-EVENTS-READ-001" not in authentic
    assert "AS-CODER-ALPHA-OPS-EVENTS-READ-001" not in reconciler
    assert "ops-events" not in reconciler


def test_web_demo_stub_does_not_fabricate_events() -> None:
    """Demo hook must stay UNKNOWN — no invented HEALTHY or recorded events."""
    from pathlib import Path as P

    hook = (
        P(__file__).resolve().parents[2] / "apps/web/src/hooks/useOpsEvents.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "events: []" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'status: "FRESH"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
