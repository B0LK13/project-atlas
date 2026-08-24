"""AS-CODER-ALPHA-ATTENTION-API-001 — read-only GET /v1/attention."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.attention import WebAttentionError, read_project_attention_hygiene


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
    with pytest.raises(WebAttentionError) as exc:
        read_project_attention_hygiene(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebAttentionError) as exc:
        read_project_attention_hygiene(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebAttentionError) as exc:
        read_project_attention_hygiene(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_empty_vault_is_unknown_not_clear(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_attention_hygiene(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["rollup"] == "UNKNOWN"
    assert report["rollup"] != "CLEAR"
    assert report["authority"] == "derived"
    assert report["honesty"]["attention_is_authority"] is False
    assert report["honesty"]["attention_is_command"] is False
    assert report["honesty"]["hygiene_is_intelligence_rank"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-ATTENTION-API-001"


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.attention_hygiene("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_attention_is_not_intelligence_rank_and_writes_forbidden(
    tmp_path: Path,
) -> None:
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/attention")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/attention?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, hygiene = _http_json(
            str(host), int(port), hdrs, "/v1/attention?project=harbor-api"
        )
        assert status == 200
        assert hygiene["project_id"] == "harbor-api"
        assert hygiene["rollup"] == "UNKNOWN"
        assert hygiene["honesty"]["hygiene_is_intelligence_rank"] is False
        status, intel = _http_json(
            str(host), int(port), hdrs, "/v1/project-attention?project=harbor-api"
        )
        assert status == 200
        assert intel.get("api_package") != "AS-CODER-ALPHA-ATTENTION-API-001"
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/attention?project=harbor-api",
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
        assert meta["attention_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
