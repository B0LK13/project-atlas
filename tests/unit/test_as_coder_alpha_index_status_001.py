"""AS-CODER-ALPHA-INDEX-STATUS-001 — vault-scoped lexical index readiness."""

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
from project_atlas.index_status import (
    PACKAGE_ID,
    REQUIRED_INDEXES,
    TRUTH_BOUNDARY,
    build_index_status,
    render_index_status_text,
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


def _index_payload(ids: list[str] | None = None) -> dict[str, object]:
    return {"schema_version": 1, "ids": ids if ids is not None else ["a"]}


def _write_required(vault: Path, *, skip: str | None = None) -> None:
    for name in REQUIRED_INDEXES:
        if name == skip:
            continue
        payload: dict[str, object]
        if name == "provenance.json":
            payload = {
                "schema_version": 1,
                "by_source_lineage_id": {"lin-1": ["a"]},
                "by_receipt_id": {},
            }
        else:
            payload = _index_payload()
        _write(vault / "generated" / "indexes" / name, payload)


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="index-status-vault-missing"):
        build_index_status(tmp_path / "absent")


def test_empty_vault_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_index_status(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "REQUIRED_INDEXES_ABSENT"
    assert report["required_present"] == 0
    assert report["required_total"] == len(REQUIRED_INDEXES)
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["honesty"]["presence_is_validate"] is False
    assert report["honesty"]["fabricated_indexes"] is False
    text = render_index_status_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[FRESH]" not in text


def test_recorded_indexes_are_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    report = build_index_status(vault)
    assert report["status"] == "RECORDED"
    assert report["available"] is True
    assert report["required_present"] == len(REQUIRED_INDEXES)
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["index_status_is_authority"] is False
    assert report["honesty"]["presence_is_validate"] is False
    assert report["status"] != "HEALTHY"
    assert report["status"] != "FRESH"
    by_name = {row["name"]: row for row in report["indexes"]}
    assert by_name["claims.json"]["presence"] == "ok"
    assert by_name["claims.json"]["id_count"] == 1
    assert by_name["provenance.json"]["id_count"] == 1


def test_partial_required_set_is_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault, skip="conflicts.json")
    report = build_index_status(vault)
    assert report["status"] == "PARTIAL"
    assert report["available"] is True
    assert report["reason_code"] == "REQUIRED_INDEXES_INCOMPLETE"
    assert report["required_present"] == len(REQUIRED_INDEXES) - 1
    assert report["status"] != "HEALTHY"


def test_unreadable_required_index_stays_unknown_or_partial(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "indexes" / "claims.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    report = build_index_status(vault)
    assert report["status"] in {"UNKNOWN", "PARTIAL"}
    assert report["status"] != "HEALTHY"
    by_name = {row["name"]: row for row in report["indexes"]}
    assert by_name["claims.json"]["presence"] == "unreadable"
    assert report["honesty"]["unknown_is_healthy"] is False


def test_non_object_index_is_unreadable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "generated" / "indexes" / "claims.json", ["not", "an", "object"])
    report = build_index_status(vault)
    by_name = {row["name"]: row for row in report["indexes"]}
    assert by_name["claims.json"]["presence"] == "unreadable"
    assert report["status"] != "HEALTHY"


def test_malformed_ids_are_dropped_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    _write(
        vault / "generated" / "indexes" / "claims.json",
        {"ids": [1, "", "ok", None]},
    )
    report = build_index_status(vault)
    by_name = {row["name"]: row for row in report["indexes"]}
    assert by_name["claims.json"]["id_count"] == 1


def test_legacy_indexes_dir_is_never_authoritative(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    (vault / "indexes").mkdir()
    (vault / "indexes" / "claims.json").write_text("{}", encoding="utf-8")
    report = build_index_status(vault)
    assert report["legacy_indexes_present"] is True
    assert report["reason_code"] == "LEGACY_INDEXES_PRESENT"
    assert report["honesty"]["legacy_indexes_are_authoritative"] is False
    assert report["status"] != "HEALTHY"
    assert report["status"] != "FRESH"


def test_legacy_only_vault_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "indexes").mkdir(parents=True)
    _write(vault / "indexes" / "claims.json", _index_payload())
    report = build_index_status(vault)
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["legacy_indexes_present"] is True
    assert report["reason_code"] == "LEGACY_INDEXES_PRESENT"


def test_companion_unreadable_does_not_look_complete(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    reviews = vault / "generated" / "indexes" / "reviews.json"
    reviews.write_text("[]", encoding="utf-8")
    report = build_index_status(vault)
    assert report["status"] == "RECORDED"
    assert report["reason_code"] == "COMPANION_INDEX_UNREADABLE"
    by_name = {row["name"]: row for row in report["indexes"]}
    assert by_name["reviews.json"]["presence"] == "unreadable"
    assert report["honesty"]["presence_is_validate"] is False


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_index_status(vault)
    assert _snapshot(vault) == before


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    first = build_index_status(vault)
    second = build_index_status(vault)
    assert first == second


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["index-status", "--vault", str(vault), "--json"]) == EXIT_OK


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.indexes.status.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.indexes.status.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_healthy"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.indexes.status.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.indexes.status.read", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.indexes.status.read", operator=bare)


def test_api_index_status_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_required(vault)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["index_status_live"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/index-status", headers=auth), timeout=2
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "RECORDED"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_index_status_is_get_only(tmp_path: Path) -> None:
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
            f"http://{host}:{port}/v1/index-status",
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
    assert "AS-CODER-ALPHA-INDEX-STATUS-001" not in authentic
    assert "AS-CODER-ALPHA-INDEX-STATUS-001" not in reconciler
    assert "index-status" not in reconciler


def test_web_demo_stub_does_not_fabricate_indexes() -> None:
    """Demo hook must stay UNKNOWN — no invented HEALTHY or recorded indexes."""
    from pathlib import Path as P

    hook = (
        P(__file__).resolve().parents[2] / "apps/web/src/hooks/useIndexStatus.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "indexes: []" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'status: "FRESH"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
