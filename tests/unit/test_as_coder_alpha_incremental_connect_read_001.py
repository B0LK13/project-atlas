"""AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001 — vault-scoped skip receipt."""

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
from project_atlas.incremental_connect import (
    INCREMENTAL_RECEIPT_RELATIVE,
    ActiveDelta,
    IncrementalDecision,
    write_incremental_receipt,
)
from project_atlas.incremental_connect_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    IncrementalConnectReadError,
    build_incremental_connect_read,
    render_incremental_connect_read_text,
)
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _empty_delta() -> ActiveDelta:
    return ActiveDelta(
        added=(),
        removed=(),
        modified=(),
        renamed=(),
        unknown_moves=(),
        content_changed=0,
        semantic_records_changed=0,
        lineage_proven=True,
    )


def _decision(
    disposition: str,
    *,
    reason: str = "active_sources_unchanged",
    ingest: int = 0,
    discover: int = 1,
) -> IncrementalDecision:
    return IncrementalDecision(
        disposition=disposition,  # type: ignore[arg-type]
        reason=reason,
        files_inspected=4,
        content_changed=0,
        semantic_records_changed=0,
        physical_writes=0,
        projections_regenerated=0,
        ingest_invocations=ingest,
        discover_invocations=discover,
        fingerprint_digest="abc123",
        prior_receipt_complete=True,
        delta=_empty_delta(),
    )


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        IncrementalConnectReadError, match="incremental-connect-vault-missing"
    ):
        build_incremental_connect_read(tmp_path / "absent")


def test_empty_vault_is_unknown_not_skip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_incremental_connect_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["disposition"] == "unknown"
    assert report["reason_code"] == "RECEIPT_ABSENT"
    assert report["honesty"]["absent_is_skip"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["fabricated_skip"] is False
    assert report["honesty"]["incremental_skip_is_authority"] is False
    assert report["honesty"]["incremental_skip_is_validate"] is False
    text = render_incremental_connect_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[FRESH]" not in text
    assert "no_change_skip" not in text


def test_recorded_skip_is_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_incremental_receipt(vault, _decision("no_change_skip"))
    report = build_incremental_connect_read(vault)
    assert report["status"] == "RECORDED"
    assert report["available"] is True
    assert report["disposition"] == "no_change_skip"
    assert report["counters"]["ingest_invocations"] == 0
    assert report["counters"]["discover_invocations"] == 1
    assert report["status"] != "HEALTHY"
    assert report["honesty"]["incremental_skip_is_authority"] is False
    assert report["honesty"]["incremental_skip_is_validate"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["receipt_is_live_certification"] is False


def test_full_compile_receipt_is_not_rewritten_to_skip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_incremental_receipt(
        vault,
        _decision("full_compile", reason="active_sources_changed", ingest=2, discover=2),
    )
    report = build_incremental_connect_read(vault)
    assert report["disposition"] == "full_compile"
    assert report["counters"]["ingest_invocations"] == 2
    assert report["disposition"] != "no_change_skip"


def test_corrupt_receipt_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INCREMENTAL_RECEIPT_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(
        IncrementalConnectReadError, match="malformed incremental-connect receipt"
    ):
        build_incremental_connect_read(vault)


def test_foreign_package_receipt_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INCREMENTAL_RECEIPT_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "atlas.coder-alpha.incremental-connect.v1",
                "package": "DEMO-FIXTURE",
                "disposition": "no_change_skip",
                "reason": "masquerade",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        IncrementalConnectReadError, match="receipt-package-mismatch"
    ):
        build_incremental_connect_read(vault)


def test_demo_schema_cannot_masquerade_as_authentic_skip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INCREMENTAL_RECEIPT_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "atlas.demo.incremental-connect.v1",
                "package": "AS-CODER-ALPHA-INCREMENTAL-CONNECT-001",
                "disposition": "no_change_skip",
                "reason": "demo",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        IncrementalConnectReadError, match="receipt-schema-mismatch"
    ):
        build_incremental_connect_read(vault)


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_incremental_connect_read(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_incremental_receipt(vault, _decision("no_change_skip"))
    first = build_incremental_connect_read(vault)
    second = build_incremental_connect_read(vault)
    assert first == second


def test_cross_vault_receipt_is_not_imported(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    write_incremental_receipt(left, _decision("no_change_skip"))
    report = build_incremental_connect_read(right)
    assert report["status"] == "UNKNOWN"
    assert report["disposition"] == "unknown"
    assert report["receipt_present"] is False


def test_existing_connect_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    help_text = build_parser().format_help()
    assert "connect" in help_text
    assert "incremental-connect" in help_text


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["incremental-connect", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_corrupt_receipt_exits_error(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / INCREMENTAL_RECEIPT_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    assert main(["incremental-connect", "--vault", str(vault), "--json"]) == EXIT_ERROR


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.ops.incremental-connect.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.ops.incremental-connect.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.ops.incremental-connect.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["absent_is_skip"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.ops.incremental-connect.read", "args": {"skip": True}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.incremental-connect.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(
            vault, "atlas.ops.incremental-connect.read", operator=bare
        )


def test_api_incremental_connect_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_incremental_receipt(vault, _decision("no_change_skip"))
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2
        ) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["ops_incremental_connect_live"] is True
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/ops/incremental-connect", headers=auth
            ),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["disposition"] == "no_change_skip"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_incremental_connect_is_get_only(tmp_path: Path) -> None:
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
            f"http://{host}:{port}/v1/ops/incremental-connect",
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
    assert "AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001" not in authentic
    assert "AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001" not in reconciler
    assert "incremental_connect_read" not in reconciler


def test_web_demo_stub_does_not_fabricate_skip() -> None:
    """Demo hook must stay UNKNOWN — no invented HEALTHY or skip rows."""
    hook = (
        Path(__file__).resolve().parents[2]
        / "apps/web/src/hooks/useIncrementalConnect.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert 'disposition: "unknown"' in hook
    assert "demo_isolated: true" in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'disposition: "no_change_skip"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
