"""AS-CODER-ALPHA-REVOCATIONS-READ-001 — vault-scoped receipt-revocation list."""

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
from project_atlas.receipt_revocation import INDEX_RELATIVE, empty_index, revoke_receipt
from project_atlas.revocations_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    RevocationsReadError,
    build_revocations_read,
    render_revocations_read_text,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _write_index(vault: Path, payload: dict[str, object]) -> None:
    path = vault / INDEX_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RevocationsReadError, match="revocations-vault-missing"):
        build_revocations_read(tmp_path / "absent")


def test_empty_vault_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_revocations_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "INDEX_ABSENT"
    assert report["revocation_count"] == 0
    assert report["revocations"] == []
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["fabricated_revocations"] is False
    assert report["honesty"]["revoke_applied"] is False
    assert report["honesty"]["write_applied"] is False
    text = render_revocations_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[FRESH]" not in text


def test_empty_index_file_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_index(vault, empty_index())
    report = build_revocations_read(vault)
    assert report["status"] == "EMPTY"
    assert report["available"] is True
    assert report["reason_code"] == "INDEX_EMPTY"
    assert report["revocation_count"] == 0
    assert report["revocations"] == []
    assert report["status"] != "HEALTHY"
    assert report["honesty"]["empty_is_healthy"] is False


def test_recorded_revocations_are_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    revoke_receipt(vault, project_id="proj-a", event_id="AE-001", reason="operator")
    report = build_revocations_read(vault)
    assert report["status"] == "RECORDED"
    assert report["available"] is True
    assert report["revocation_count"] == 1
    assert report["returned_count"] == 1
    assert report["revocations"][0]["unit_key"] == "proj-a/AE-001"
    assert report["revocations"][0]["status"] == "revoked"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["revocations_are_authority"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["status"] != "HEALTHY"
    assert report["status"] != "FRESH"


def test_corrupt_index_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INDEX_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(RevocationsReadError, match="malformed revocation index"):
        build_revocations_read(vault)


def test_limit_rejects_out_of_range(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(RevocationsReadError, match="revocations-limit-out-of-range"):
        build_revocations_read(vault, limit=0)
    with pytest.raises(RevocationsReadError, match="revocations-limit-out-of-range"):
        build_revocations_read(vault, limit=501)


def test_limit_truncates_sorted_rows(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    revoke_receipt(vault, project_id="proj-a", event_id="AE-001")
    revoke_receipt(vault, project_id="proj-b", event_id="AE-002")
    revoke_receipt(vault, project_id="proj-c", event_id="AE-003")
    report = build_revocations_read(vault, limit=2)
    assert report["revocation_count"] == 3
    assert report["returned_count"] == 2
    assert report["truncated"] is True
    assert [row["unit_key"] for row in report["revocations"]] == [
        "proj-a/AE-001",
        "proj-b/AE-002",
    ]


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_revocations_read(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    revoke_receipt(vault, project_id="proj-a", event_id="AE-001")
    first = build_revocations_read(vault)
    second = build_revocations_read(vault)
    assert first == second


def test_cross_vault_rows_are_not_imported(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    revoke_receipt(left, project_id="proj-a", event_id="AE-LEFT")
    report = build_revocations_read(right)
    assert report["status"] == "UNKNOWN"
    assert report["revocations"] == []
    assert all(
        row.get("event_id") != "AE-LEFT" for row in report["revocations"]
    )


def test_existing_revocation_list_contract_unchanged(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    revoke_receipt(vault, project_id="proj-a", event_id="AE-001")
    assert main(["revocation", "list", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["revocations", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_corrupt_index_exits_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INDEX_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    assert main(["revocations", "--vault", str(vault), "--json"]) == EXIT_ERROR


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.ops.revocations.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.ops.revocations.write" not in listing["tools"]
    assert "atlas.ops.revocations.revoke" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.ops.revocations.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_healthy"] is False
    assert result["revocations"] == []


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.revocations.read", "args": {"limit": 1}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.revocations.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.ops.revocations.read", operator=bare)


def test_api_revocations_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    revoke_receipt(vault, project_id="proj-a", event_id="AE-001")
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["ops_revocations_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/ops/revocations", headers=auth), timeout=2
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "RECORDED"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_revocations_is_get_only(tmp_path: Path) -> None:
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
            f"http://{host}:{port}/v1/ops/revocations",
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
    root = Path(__file__).resolve().parents[2]
    authentic = (
        root / "src/project_atlas/orchestration/autonomy/authentic_estate.py"
    ).read_text(encoding="utf-8")
    reconciler = (
        root / "src/project_atlas/orchestration/sdk/mission_reconciler.py"
    ).read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-REVOCATIONS-READ-001" not in authentic
    assert "AS-CODER-ALPHA-REVOCATIONS-READ-001" not in reconciler
    assert "revocations_read" not in reconciler


def test_web_demo_stub_does_not_fabricate_revocations() -> None:
    """Demo hook must stay UNKNOWN — no invented HEALTHY or revocation rows."""
    hook = (
        Path(__file__).resolve().parents[2] / "apps/web/src/hooks/useRevocations.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "revocations: []" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'status: "FRESH"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
