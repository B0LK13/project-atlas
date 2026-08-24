"""AS-CODER-ALPHA-INBOX-API-001 — read-only GET /v1/inbox."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.knowledge_inbox import build_knowledge_inbox_receipt
from project_atlas.web_api.inbox import WebInboxError, read_project_inbox


def _http_json(
    host: str,
    port: int,
    headers: dict[str, str],
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    req = Request(f"http://{host}:{port}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return exc.code, payload


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _capture(
    vault: Path,
    *,
    capture_id: str,
    project_id: str,
    summary: str,
    review_state: str = "captured",
) -> None:
    inbox_status = {
        "captured": "quarantined",
        "reviewed": "accepted-review",
        "rejected": "rejected",
    }[review_state]
    _write(
        vault / "generated" / "ops" / "conversation-captures" / f"{capture_id}.json",
        {
            "capture_id": capture_id,
            "project_id": project_id,
            "summary": summary,
            "review_state": review_state,
            "capture_items": [{"item_type": "observation", "text": summary}],
            "inbox": {"status": inbox_status, "promoted_to_authority": False},
        },
    )
    build_knowledge_inbox_receipt(
        vault,
        record_id=capture_id,
        status=inbox_status,
        item_count=1,
    )


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebInboxError) as exc:
        read_project_inbox(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebInboxError) as exc:
        read_project_inbox(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebInboxError) as exc:
        read_project_inbox(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_empty_project_is_unknown_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_inbox(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["count"] == 0
    assert report["authority"] == "derived"
    assert report["honesty"]["inbox_is_authority"] is False
    assert report["honesty"]["inbox_is_command"] is False
    assert report["honesty"]["listing_is_mutation"] is False
    assert report["honesty"]["auto_execution"] is False
    assert report["promoted_to_authority"] is False
    assert report["layer_b_writes"] == 0
    assert report["api_package"] == "AS-CODER-ALPHA-INBOX-API-001"
    assert report["unknown"] == "UNKNOWN (no inbox items for project)"


def test_unknown_project_token_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_inbox(vault, "unknown-project")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "UNKNOWN_PROJECT"
    assert report["count"] == 0
    assert report["honesty"]["inbox_is_authority"] is False


def test_cross_project_rows_are_never_returned(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-harbor-1", project_id="harbor-api", summary="harbor note")
    _capture(vault, capture_id="ccap-portal-1", project_id="portal-app", summary="portal note")
    harbor = read_project_inbox(vault, "harbor-api")
    portal = read_project_inbox(vault, "portal-app")
    assert harbor["count"] == 1
    assert harbor["items"][0]["receipt_id"] == "ccap-harbor-1"
    assert all(item["project_id"] == "harbor-api" for item in harbor["items"])
    assert portal["count"] == 1
    assert portal["items"][0]["receipt_id"] == "ccap-portal-1"
    dumped = json.dumps(harbor)
    assert "ccap-portal-1" not in dumped
    assert "portal note" not in dumped


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.inbox("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_inbox_scope_isolation_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-harbor-1", project_id="harbor-api", summary="harbor note")
    _capture(vault, capture_id="ccap-portal-1", project_id="portal-app", summary="portal note")
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        before = {
            path.relative_to(vault).as_posix(): path.read_bytes()
            for path in vault.rglob("*")
            if path.is_file()
        }
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/inbox")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["count"] == 1
        assert harbor["authority"] == "derived"
        assert harbor["honesty"]["inbox_is_authority"] is False
        assert harbor["honesty"]["inbox_is_command"] is False
        assert harbor["honesty"]["listing_is_mutation"] is False
        assert "ccap-portal-1" not in json.dumps(harbor)
        status, portal = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=portal-app"
        )
        assert status == 200
        assert portal["project_id"] == "portal-app"
        assert portal["count"] == 1
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/inbox?project=harbor-api",
            method="PATCH",
            body=b"{}",
        )
        assert status == 405
        assert patched["error"] == "writes-forbidden"
        after = {
            path.relative_to(vault).as_posix(): path.read_bytes()
            for path in vault.rglob("*")
            if path.is_file()
        }
        assert after == before
        status, meta = _http_json(str(host), int(port), hdrs, "/v1/meta")
        assert status == 200
        assert meta["inbox_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
