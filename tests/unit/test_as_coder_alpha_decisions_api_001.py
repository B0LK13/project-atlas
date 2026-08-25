"""AS-CODER-ALPHA-DECISIONS-API-001 — read-only GET /v1/decisions."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.decisions import WebDecisionsError, read_project_decisions


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


def _seed_decisions(vault: Path, project_id: str, title: str) -> None:
    note = vault / "projects" / project_id / "decisions.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"# Decisions\n\n## ADR-001 — {title}\n", encoding="utf-8")


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebDecisionsError) as exc:
        read_project_decisions(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebDecisionsError) as exc:
        read_project_decisions(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_evidence_stays_unknown_not_governing(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_decisions(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["status"] == "unknown"
    assert report["decision_count"] == 0
    assert report["active_governing_count"] == 0
    assert report["authority"] == "derived"
    assert report["honesty"]["decisions_is_authority"] is False
    assert report["honesty"]["active_governing_is_trust_score"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-DECISIONS-API-001"
    assert not (vault / "generated").exists()


def test_formal_adr_is_derived_not_owner_grant(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_decisions(vault, "harbor-api", "Use PostgreSQL 16")
    report = read_project_decisions(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["decision_count"] >= 1
    dumped = json.dumps(report)
    assert "Use PostgreSQL 16" in dumped
    assert report["honesty"]["decisions_is_authority"] is False
    assert "OWNER_GATE" not in dumped
    assert "OWNER_CAPABILITY_GRANTED" not in dumped


def test_cross_project_decisions_are_isolated(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_decisions(vault, "harbor-api", "Harbor datastore pin")
    _seed_decisions(vault, "portal-app", "Portal session cookie")
    harbor = read_project_decisions(vault, "harbor-api")
    portal = read_project_decisions(vault, "portal-app")
    assert "Harbor datastore pin" in json.dumps(harbor)
    assert "Portal session cookie" not in json.dumps(harbor)
    assert "Harbor datastore pin" not in json.dumps(portal)


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.decisions("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_decisions_scope_isolation_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_decisions(vault, "harbor-api", "Harbor datastore pin")
    _seed_decisions(vault, "portal-app", "Portal session cookie")
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/decisions")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/decisions?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["honesty"]["decisions_is_authority"] is False
        assert "Portal session cookie" not in json.dumps(harbor)
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/decisions?project=harbor-api",
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
        assert meta["decisions_live"] is True
    finally:
        server.shutdown()
