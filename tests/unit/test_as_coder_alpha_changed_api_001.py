"""AS-CODER-ALPHA-CHANGED-API-001 — read-only GET /v1/changed."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.changed import WebChangedError, read_project_changed


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


def _inventory(paths: dict[str, str], project_id: str) -> dict[str, object]:
    sources = [
        {"path": path, "sha256": digest, "project_id": project_id}
        for path, digest in sorted(paths.items())
    ]
    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.connect-inventory.v1",
        "package": "AS-CODER-ALPHA-CHANGED-001",
        "sources": sources,
        "by_path": dict(paths),
        "generated": {"by": "test"},
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebChangedError) as exc:
        read_project_changed(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebChangedError) as exc:
        read_project_changed(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebChangedError) as exc:
        read_project_changed(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_inventory_is_unknown_history_not_unchanged(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_changed(vault, "harbor-api")
    assert report["project_id"] == "harbor-api"
    assert report["status"] == "unknown"
    assert report["rollup"] == "baseline"
    assert report["rollup"] != "unchanged"
    assert report["authority"] == "derived"
    assert report["honesty"]["changed_is_kdiff"] is False
    assert report["honesty"]["changed_is_authority"] is False
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-CHANGED-API-001"
    assert "UNKNOWN" in report["summary"]
    assert not (vault / "generated").exists()


def test_read_does_not_rotate_inventory_or_write_answers(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    current = _inventory({"harbor-api/README.md": "aaa"}, "harbor-api")
    previous = _inventory({}, "harbor-api")
    current_path = vault / "generated" / "ops" / "connect-inventory.json"
    previous_path = vault / "generated" / "ops" / "connect-inventory.prev.json"
    _write_json(current_path, current)
    _write_json(previous_path, previous)
    before_current = current_path.read_bytes()
    before_previous = previous_path.read_bytes()
    report = read_project_changed(vault, "harbor-api")
    assert report["rollup"] == "changed"
    assert "harbor-api/README.md" in report["delta"]["added"]
    assert current_path.read_bytes() == before_current
    assert previous_path.read_bytes() == before_previous
    assert not (vault / "generated" / "answers").exists()


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.changed("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_changed_scope_and_writes_forbidden(tmp_path: Path) -> None:
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/changed")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/changed?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, report = _http_json(
            str(host), int(port), hdrs, "/v1/changed?project=harbor-api"
        )
        assert status == 200
        assert report["project_id"] == "harbor-api"
        assert report["status"] == "unknown"
        assert report["rollup"] == "baseline"
        assert report["honesty"]["changed_is_kdiff"] is False
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/changed?project=harbor-api",
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
        assert meta["changed_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
