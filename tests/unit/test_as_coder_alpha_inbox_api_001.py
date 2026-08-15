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
from project_atlas.secrets import scan_text
from project_atlas.web_api.inbox import WebInboxError, read_inbox


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
        read_inbox(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebInboxError) as exc:
        read_inbox(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebInboxError) as exc:
        read_inbox(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebInboxError) as exc:
        read_inbox(vault, "Harbor_API")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_read_empty_is_unknown_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_inbox(vault, "harbor-api")
    assert report["project_id"] == "harbor-api"
    assert report["items"] == []
    assert report["unknown"] == "UNKNOWN (no inbox items for project)"
    assert report["authority"] == "derived"
    assert report["promoted_to_authority"] is False
    assert report["honesty"]["inbox_is_authority"] is False
    assert report["honesty"]["capture_is_verified_fact"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-INBOX-API-001"
    assert "INBOX != AUTHORITY" in str(report["truth_boundary"])
    assert "CAPTURE != VERIFIED FACT" in str(report["truth_boundary"])


def test_read_is_project_scoped_and_skips_orphans(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _capture(vault, capture_id="ccap-b", project_id="harbor-api", summary="later-id")
    _capture(vault, capture_id="ccap-a", project_id="harbor-api", summary="earlier-id")
    _capture(vault, capture_id="ccap-z", project_id="portal-app", summary="other-project")
    build_knowledge_inbox_receipt(vault, record_id="orphan-1", item_count=1)
    report = read_inbox(vault, "harbor-api")
    ids = [item["receipt_id"] for item in report["items"]]
    assert ids == ["ccap-a", "ccap-b"]
    assert all(item["project_id"] == "harbor-api" for item in report["items"])
    assert "orphan-1" not in ids
    leaked = read_inbox(vault, "portal-app")
    assert [item["receipt_id"] for item in leaked["items"]] == ["ccap-z"]


def test_read_status_filter_limit_and_secret_redaction(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    secret = "AKIA" + "ABCDEFGHIJKLMNOP"
    assert scan_text(secret)
    _capture(vault, capture_id="ccap-q", project_id="harbor-api", summary=secret)
    _capture(
        vault,
        capture_id="ccap-r",
        project_id="harbor-api",
        summary="reviewed-row",
        review_state="reviewed",
    )
    filtered = read_inbox(vault, "harbor-api", status="accepted-review")
    assert [item["receipt_id"] for item in filtered["items"]] == ["ccap-r"]
    limited = read_inbox(vault, "harbor-api", limit=1)
    assert limited["count"] == 1
    assert limited["items"][0]["receipt_id"] == "ccap-q"
    assert limited["items"][0]["summary"] == "[redacted: secret-shaped value]"
    assert secret not in json.dumps(limited)
    with pytest.raises(WebInboxError) as exc:
        read_inbox(vault, "harbor-api", limit=0)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebInboxError) as exc:
        read_inbox(vault, "harbor-api", status="promoted")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.inbox("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_inbox_scope_writes_and_isolation(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "portal-app").mkdir(parents=True)
    _capture(vault, capture_id="ccap-h", project_id="harbor-api", summary="harbor-row")
    _capture(vault, capture_id="ccap-p", project_id="portal-app", summary="portal-row")
    build_knowledge_inbox_receipt(vault, record_id="orphan-http", item_count=1)
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
        status, long_tok = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=" + ("x" * 80)
        )
        assert status == 400
        assert long_tok["honesty"] == "MALFORMED_INPUT"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=../harbor-api"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["authority"] == "derived"
        assert harbor["honesty"]["inbox_is_authority"] is False
        ids = [item["receipt_id"] for item in harbor["items"]]  # type: ignore[index]
        assert ids == ["ccap-h"]
        assert "orphan-http" not in ids
        status, portal = _http_json(
            str(host), int(port), hdrs, "/v1/inbox?project=portal-app"
        )
        assert status == 200
        assert [item["receipt_id"] for item in portal["items"]] == ["ccap-p"]  # type: ignore[index]
        status, filtered = _http_json(
            str(host),
            int(port),
            hdrs,
            "/v1/inbox?project=harbor-api&status=rejected",
        )
        assert status == 200
        assert filtered["items"] == []
        assert filtered["unknown"] == "UNKNOWN (no inbox items for project)"
        status, bad_status = _http_json(
            str(host),
            int(port),
            hdrs,
            "/v1/inbox?project=harbor-api&status=promoted",
        )
        assert status == 400
        assert bad_status["honesty"] == "MALFORMED_INPUT"
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
        status, posted = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/inbox?project=harbor-api",
            method="POST",
            body=b"{}",
        )
        assert status == 405
        assert posted["error"] == "writes-forbidden"
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
