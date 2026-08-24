"""AS-CODER-ALPHA-UNKNOWN-API-001 — read-only GET /v1/unknown."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.unknown import WebUnknownError, read_project_unknown


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


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebUnknownError) as exc:
        read_project_unknown(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebUnknownError) as exc:
        read_project_unknown(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebUnknownError) as exc:
        read_project_unknown(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_evidence_stays_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_unknown(vault, "missing-proj")
    assert report["project_id"] == "missing-proj"
    assert report["status"] == "derived"
    assert report["rollup"] == "unknown"
    assert "lifecycle=unknown" in " ".join(report["signals"]["unknown_items"])
    assert report["authority"] == "derived"
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["unknown_is_authority"] is False
    assert report["honesty"]["rollup_is_trust_score"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-UNKNOWN-API-001"
    assert not (vault / "generated").exists()


def test_pending_reviews_are_unknown_not_clear(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    pending = vault / "review" / "pending"
    pending.mkdir(parents=True)
    (pending / "harbor-api.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"id": "rev-1", "status": "pending"},
                    {"id": "rev-2", "status": "resolved"},
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = read_project_unknown(vault, "harbor-api")
    assert report["signals"]["pending_reviews"] == 1
    assert report["rollup"] == "review"
    assert report["honesty"]["unknown_is_healthy"] is False


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.unknown("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_unknown_scope_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/unknown")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/unknown?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, report = _http_json(
            str(host), int(port), hdrs, "/v1/unknown?project=harbor-api"
        )
        assert status == 200
        assert report["project_id"] == "harbor-api"
        assert report["honesty"]["unknown_is_healthy"] is False
        assert report["honesty"]["unknown_is_authority"] is False
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/unknown?project=harbor-api",
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
        assert not (vault / "generated" / "answers").exists()
        status, meta = _http_json(str(host), int(port), hdrs, "/v1/meta")
        assert status == 200
        assert meta["unknown_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
