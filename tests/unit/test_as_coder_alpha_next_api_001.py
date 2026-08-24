"""AS-CODER-ALPHA-NEXT-API-001 — read-only GET /v1/next."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.next import WebNextError, read_project_next


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


def _seed_project(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "roadmap.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntype: Roadmap\n---\n\n# Roadmap\n\n## Roadmap record\n\n```json\n"
        + json.dumps({"items": []})
        + "\n```\n",
        encoding="utf-8",
    )
    (vault / "projects" / project_id / "project.md").write_text(
        f"---\ntype: Project\ntitle: {project_id}\n---\n\n# {project_id}\n",
        encoding="utf-8",
    )


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebNextError) as exc:
        read_project_next(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebNextError) as exc:
        read_project_next(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebNextError) as exc:
        read_project_next(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_unknown_project_is_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects").mkdir()
    with pytest.raises(WebNextError) as exc:
        read_project_next(vault, "missing-project")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_empty_project_is_unknown_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _seed_project(vault, "empty-proj")
    report = read_project_next(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["authority"] == "derived"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["next_is_command"] is False
    assert report["honesty"]["auto_execution"] is False
    assert report["status"] == "unknown"
    assert report["api_package"] == "AS-CODER-ALPHA-NEXT-API-001"


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.next_work("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_next_scope_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _seed_project(vault, "harbor-api")
    _seed_project(vault, "portal-app")
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/next")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/next?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/next?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["authority"] == "derived"
        assert harbor["honesty"]["next_is_authority"] is False
        assert harbor["honesty"]["next_is_command"] is False
        status, portal = _http_json(
            str(host), int(port), hdrs, "/v1/next?project=portal-app"
        )
        assert status == 200
        assert portal["project_id"] == "portal-app"
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/next?project=harbor-api",
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
        assert meta["next_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
