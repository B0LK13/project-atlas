"""AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001 — vault-scoped deletion lens."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.event_tombstones import record_explicit_tombstone
from project_atlas.event_tombstones_read import (
    PACKAGE_ID,
    TRUTH_BOUNDARY,
    EventTombstonesReadError,
    build_event_tombstones_read,
    render_event_tombstones_read_text,
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


def _seed_tombstone(
    vault: Path, project_id: str = "harbor", event_id: str = "AE-001"
) -> None:
    record_explicit_tombstone(vault, project_id=project_id, event_id=event_id)


def test_missing_vault_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        EventTombstonesReadError, match="event-tombstones-vault-missing"
    ):
        build_event_tombstones_read(tmp_path / "absent")


def test_missing_index_is_unknown_not_clean(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = build_event_tombstones_read(vault)
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["reason_code"] == "INDEX_ABSENT"
    assert report["deleted_count"] == 0
    assert report["index_present"] is False
    assert report["honesty"]["unknown_is_clean"] is False
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["owner_capability_granted"] is False
    assert report["honesty"]["authentic_pilot"] is False
    text = render_event_tombstones_read_text(report)
    assert "[UNKNOWN]" in text
    assert "[HEALTHY]" not in text
    assert "[CLEAN]" not in text


def test_empty_index_is_empty_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    record_explicit_tombstone(vault, project_id="harbor", event_id="AE-tmp")
    index = vault / "generated" / "ops" / "event-tombstones.json"
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["tombstones"] = []
    index.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = build_event_tombstones_read(vault)
    assert report["status"] == "EMPTY"
    assert report["available"] is True
    assert report["reason_code"] == "INDEX_EMPTY"
    assert report["deleted_count"] == 0
    assert report["honesty"]["empty_is_healthy"] is False
    assert report["status"] != "HEALTHY"


def test_present_tombstone_is_deleted_visible(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault)
    report = build_event_tombstones_read(vault)
    assert report["status"] == "DELETED_VISIBLE"
    assert report["available"] is True
    assert report["deleted_count"] == 1
    assert report["tombstones"][0]["unit_key"] == "harbor/AE-001"
    assert report["tombstones"][0]["state"] == "deleted"
    assert report["honesty"]["deleted_is_vanished"] is False
    assert report["honesty"]["lens_is_authority"] is False


def test_project_scope_hides_sibling(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault, "harbor", "AE-001")
    _seed_tombstone(vault, "portal", "AE-009")
    harbor = build_event_tombstones_read(vault, "harbor")
    portal = build_event_tombstones_read(vault, "portal")
    assert harbor["status"] == "DELETED_VISIBLE"
    assert [row["unit_key"] for row in harbor["tombstones"]] == ["harbor/AE-001"]
    assert portal["tombstones"][0]["unit_key"] == "portal/AE-009"
    assert "portal/AE-009" not in [
        row["unit_key"] for row in harbor["tombstones"]
    ]


def test_unrelated_project_is_empty_not_deleted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault, "harbor", "AE-001")
    report = build_event_tombstones_read(vault, "missing-sibling")
    assert report["status"] == "EMPTY"
    assert report["deleted_count"] == 0
    assert report["honesty"]["empty_is_healthy"] is False


def test_unsafe_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(
        EventTombstonesReadError, match="event-tombstones-project-unsafe"
    ):
        build_event_tombstones_read(vault, "../escape")


def test_malformed_index_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "event-tombstones.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(
        EventTombstonesReadError, match="event-tombstones-index-malformed"
    ):
        build_event_tombstones_read(vault)


def test_malformed_index_does_not_look_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "event-tombstones.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(EventTombstonesReadError):
        build_event_tombstones_read(vault)


def test_read_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault)
    before = _snapshot(vault)
    build_event_tombstones_read(vault)
    build_event_tombstones_read(vault, "harbor")
    assert _snapshot(vault) == before


def test_missing_index_read_does_not_create_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    build_event_tombstones_read(vault)
    assert _snapshot(vault) == before
    assert not (vault / "generated" / "ops" / "event-tombstones.json").exists()


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault)
    first = build_event_tombstones_read(vault, "harbor")
    second = build_event_tombstones_read(vault, "harbor")
    assert first == second


def test_cross_vault_tombstones_are_not_imported(tmp_path: Path) -> None:
    left = tmp_path / "left"
    left.mkdir()
    _seed_tombstone(left, "harbor", "AE-001")
    right = tmp_path / "right"
    right.mkdir()
    report = build_event_tombstones_read(right, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["available"] is False
    assert report["deleted_count"] == 0
    _ = left


def test_cli_json_empty_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert main(["event-tombstones", "--vault", str(vault), "--json"]) == EXIT_OK


def test_cli_missing_vault_exits_error(tmp_path: Path) -> None:
    assert (
        main(["event-tombstones", "--vault", str(tmp_path / "absent"), "--json"])
        == EXIT_ERROR
    )


def test_existing_retention_cli_unchanged() -> None:
    from project_atlas.cli import build_parser

    help_text = build_parser().format_help()
    assert "event-tombstones" in help_text
    assert "retention" in help_text


def test_mcp_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.event.tombstones.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.event.tombstones.write" not in listing["tools"]


def test_mcp_empty_vault_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.event.tombstones.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["status"] == "UNKNOWN"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_clean"] is False


def test_mcp_args_and_write_keys_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _snapshot(vault)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.event.tombstones.read", "args": {"project": "x"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.event.tombstones.write", "write": True}),
        )
    assert _snapshot(vault) == before


def test_mcp_requires_read_capability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.event.tombstones.read", operator=bare)


def test_api_event_tombstones_route(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_tombstone(vault)
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
        assert meta["event_tombstones_live"] is True
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/event-tombstones?project=harbor",
                headers=auth,
            ),
            timeout=2,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["package_id"] == PACKAGE_ID
        assert body["truth_boundary"] == TRUTH_BOUNDARY
        assert body["status"] == "DELETED_VISIBLE"
        assert body["honesty"]["owner_capability_granted"] is False
        assert body["honesty"]["authentic_pilot"] is False
    finally:
        server.shutdown()


def test_api_event_tombstones_is_get_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        req = Request(
            f"http://{host}:{port}/v1/event-tombstones",
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
    assert "AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001" not in authentic
    assert "AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001" not in reconciler
    assert "event_tombstones_read" not in reconciler


def test_web_demo_stub_does_not_fabricate_empty_or_healthy() -> None:
    """Demo hook must stay UNKNOWN — no invented EMPTY/HEALTHY rows."""
    hook = (
        Path(__file__).resolve().parents[2]
        / "apps/web/src/hooks/useEventTombstones.ts"
    ).read_text(encoding="utf-8")
    assert 'status: "UNKNOWN"' in hook
    assert 'reason_code: "DEMO_STUB_UNKNOWN"' in hook
    assert "available: false" in hook
    assert "demo_isolated: true" in hook
    assert 'status: "EMPTY"' not in hook
    assert 'status: "HEALTHY"' not in hook
    assert 'status: "DELETED_VISIBLE"' not in hook
    assert "OWNER_CAPABILITY_GRANTED" not in hook
