"""AS-CODER-ALPHA-CONNECT-STATUS-001 — vault-scoped connect receipt read."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect_status import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    build_connect_status,
    render_connect_status_text,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _valid_receipt() -> dict[str, object]:
    return {
        "schema": "atlas.connect.receipt.v1",
        "status": "connected",
        "vault_id": "vault-1",
        "project_root": "/tmp/sample",
        "bound_project_id": "sample",
        "projects": ["sample"],
        "documents_ingested": 4,
        "incremental": {"disposition": "full_compile"},
    }


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="connect-status-vault-missing"):
        build_connect_status(tmp_path / "absent")


def test_empty_vault_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_connect_status(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "CONNECT_RECEIPT_ABSENT"
    assert report["connect_receipt"]["presence"] == "absent"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["skip_is_truth_core"] is False
    assert report["honesty"]["fabricated_receipt"] is False
    text = render_connect_status_text(report)
    assert "[UNKNOWN]" in text
    assert "[FRESH]" not in text


def test_recorded_receipt_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "ops" / "connect-receipt.json", _valid_receipt())
    report = build_connect_status(vault)
    assert report["status"] == "RECORDED"
    assert report["available"] is True
    assert report["connect_receipt"]["bound_project_id"] == "sample"
    assert report["connect_receipt"]["documents_ingested"] == 4
    assert report["connect_receipt"]["incremental_disposition"] == "full_compile"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["connect_status_is_authority"] is False
    assert report["status"] != "FRESH"


def test_unreadable_receipt_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "connect-receipt.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    report = build_connect_status(vault)
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "CONNECT_RECEIPT_UNREADABLE"
    assert report["connect_receipt"]["presence"] == "unreadable"


def test_non_object_receipt_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "ops" / "connect-receipt.json", ["not", "an", "object"])
    report = build_connect_status(vault)
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "CONNECT_RECEIPT_UNREADABLE"


def test_incremental_skip_is_operational_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "ops" / "connect-receipt.json", _valid_receipt())
    _write(
        vault / "generated" / "ops" / "incremental-connect-receipt.json",
        {
            "schema": "atlas.coder-alpha.incremental-connect.v1",
            "disposition": "no_change_skip",
            "authority": "operational_not_truth_core",
        },
    )
    report = build_connect_status(vault)
    assert report["incremental_receipt"]["presence"] == "ok"
    assert report["incremental_receipt"]["disposition"] == "no_change_skip"
    assert report["incremental_receipt"]["operational_only"] is True
    assert report["honesty"]["skip_is_truth_core"] is False


def test_unreadable_incremental_does_not_look_like_clean_skip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "ops" / "connect-receipt.json", _valid_receipt())
    inc = vault / "generated" / "ops" / "incremental-connect-receipt.json"
    inc.write_text("[]", encoding="utf-8")
    report = build_connect_status(vault)
    assert report["incremental_receipt"]["presence"] == "unreadable"
    assert report["reason_code"] == "INCREMENTAL_RECEIPT_UNREADABLE"
    assert report["honesty"]["skip_is_truth_core"] is False


def test_malformed_fields_are_dropped_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "ops" / "connect-receipt.json",
        {
            "status": 12,
            "vault_id": "",
            "projects": [1, "", "ok"],
            "documents_ingested": "four",
        },
    )
    report = build_connect_status(vault)
    assert report["connect_receipt"]["status"] is None
    assert report["connect_receipt"]["vault_id"] is None
    assert report["connect_receipt"]["projects"] == ["ok"]
    assert report["connect_receipt"]["documents_ingested"] is None


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_connect_status(vault)
    assert _snapshot(vault) == before


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["connect-status", "--vault", str(vault), "--json"]) == EXIT_OK


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.connect.status.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.connect.status.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_fresh"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.connect.status.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.connect.status.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.connect.status.read", operator=bare)


def test_api_connect_status_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault / "generated" / "ops" / "connect-receipt.json", _valid_receipt())
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["connect_status_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/connect-status", headers=auth), timeout=2
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "RECORDED"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_connect_status_is_get_only(tmp_path: Path) -> None:
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
            f"http://{host}:{port}/v1/connect-status",
            data=b"{}",
            headers={**auth, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 405
    finally:
        server.shutdown()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "ops" / "connect-receipt.json", _valid_receipt())
    first = build_connect_status(vault)
    second = build_connect_status(vault)
    assert first == second


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
    assert "AS-CODER-ALPHA-CONNECT-STATUS-001" not in authentic
    assert "AS-CODER-ALPHA-CONNECT-STATUS-001" not in reconciler
    assert "connect-status" not in reconciler


def test_web_demo_stub_does_not_fabricate_bound_vault() -> None:
    """Demo hook must stay UNKNOWN — no invented FRESH or bound receipt."""
    from pathlib import Path as P

    hook = (
        P(__file__).resolve().parents[2]
        / "apps/web/src/hooks/useConnectStatus.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "presence: \"absent\"" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "FRESH"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
