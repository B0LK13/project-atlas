"""AS-CODER-ALPHA-OVERVIEW-API-001 — read-only GET /v1/overview."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.overview import WebOverviewError, read_project_overview


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


def _seed_overview(vault: Path, project_id: str, title: str, body: str) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    sources = [{"path": "README.md", "source_id": f"src-{project_id}"}]
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps({"project_id": project_id, "sources": sources, "coverage": []})
        + "\n```\n",
        encoding="utf-8",
    )
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True, exist_ok=True)
    (imported / f"src-{project_id}.md").write_text(
        f"# {title}\n\n{body}\n",
        encoding="utf-8",
    )


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebOverviewError) as exc:
        read_project_overview(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebOverviewError) as exc:
        read_project_overview(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebOverviewError) as exc:
        read_project_overview(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_project_note_stays_unknown_and_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_overview(vault, "missing-proj")
    assert report["project_id"] == "missing-proj"
    assert report["status"] == "unknown"
    assert report["summary"] is None
    assert report["authority"] == "derived"
    assert report["honesty"]["overview_is_authority"] is False
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-OVERVIEW-API-001"
    assert not (vault / "generated").exists()


def test_valid_estate_overview_is_derived_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_overview(vault, "harbor-api", "Harbor Portal", "Persistent brain for harbor.")
    report = read_project_overview(vault, "harbor-api")
    assert report["status"] == "derived"
    assert "Harbor Portal" in (report["summary"] or "")
    assert report["honesty"]["overview_is_authority"] is False
    assert report["honesty"]["auto_execution"] is False
    assert "OWNER_GATE" not in json.dumps(report)
    assert not (vault / "generated" / "answers").exists()


def test_cross_project_rows_are_never_returned(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_overview(vault, "harbor-api", "Harbor Portal", "Harbor only.")
    _seed_overview(vault, "portal-app", "Portal App", "Portal secret.")
    harbor = read_project_overview(vault, "harbor-api")
    portal = read_project_overview(vault, "portal-app")
    assert "Harbor Portal" in (harbor["summary"] or "")
    assert "Portal App" in (portal["summary"] or "")
    dumped = json.dumps(harbor)
    assert "Portal secret" not in dumped
    assert "portal-app" not in dumped or harbor["project_id"] == "harbor-api"
    assert "Portal App" not in dumped


def test_repeated_read_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_overview(vault, "harbor-api", "Harbor Portal", "Persistent brain.")
    first = read_project_overview(vault, "harbor-api")
    second = read_project_overview(vault, "harbor-api")
    assert first == second


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.overview("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_overview_scope_isolation_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_overview(vault, "harbor-api", "Harbor Portal", "Harbor only.")
    _seed_overview(vault, "portal-app", "Portal App", "Portal secret.")
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/overview")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, traversal = _http_json(
            str(host), int(port), hdrs, "/v1/overview?project=../escape"
        )
        assert status == 400
        assert traversal["honesty"] == "MALFORMED_INPUT"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/overview?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["authority"] == "derived"
        assert harbor["honesty"]["overview_is_authority"] is False
        assert "Portal secret" not in json.dumps(harbor)
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/overview?project=harbor-api",
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
        assert meta["overview_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
