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
from project_atlas.web_api.attention import (
    WebAttentionError,
    read_project_attention_hygiene,
)
from project_atlas.web_api.intelligence import read_project_attention


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


def _seed_conflict(vault: Path, project_id: str, field: str) -> None:
    path = vault / "review" / "conflicts" / f"{project_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "conflict_id": f"cf-{project_id}",
                        "conflict_type": "competing-claim",
                        "field": field,
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebAttentionError) as exc:
        read_project_attention_hygiene(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebAttentionError) as exc:
        read_project_attention_hygiene(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_artifacts_stay_unknown_not_clear(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_attention_hygiene(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["rollup"] == "UNKNOWN"
    assert report["item_count"] >= 1
    assert all(item.get("level") != "CLEAR" for item in report["items"])
    assert report["honesty"]["attention_is_authority"] is False
    assert report["honesty"]["clear_is_default"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-ATTENTION-API-001"
    assert not (vault / "generated").exists()


def test_conflict_is_blocking_not_owner_grant(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_conflict(vault, "harbor-api", "datastore")
    report = read_project_attention_hygiene(vault, "harbor-api")
    assert report["rollup"] == "BLOCKING"
    dumped = json.dumps(report)
    assert "cf-harbor-api" in dumped
    assert "competing-claim" in dumped
    assert report["honesty"]["attention_is_authority"] is False
    assert "OWNER_GATE" not in dumped
    assert "OWNER_CAPABILITY_GRANTED" not in dumped


def test_cross_project_attention_is_isolated(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_conflict(vault, "harbor-api", "harbor-datastore")
    _seed_conflict(vault, "portal-app", "portal-cookie")
    harbor = read_project_attention_hygiene(vault, "harbor-api")
    portal = read_project_attention_hygiene(vault, "portal-app")
    assert "cf-harbor-api" in json.dumps(harbor)
    assert "cf-portal-app" not in json.dumps(harbor)
    assert "cf-harbor-api" not in json.dumps(portal)


def test_hygiene_route_is_not_intelligence_project_attention(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    hygiene = read_project_attention_hygiene(vault, "harbor-api")
    intel = read_project_attention(vault, "harbor-api")
    assert hygiene["api_package"] == "AS-CODER-ALPHA-ATTENTION-API-001"
    assert hygiene["schema"] == "atlas.coder-alpha.attention.v1"
    assert intel.get("api_package") != hygiene["api_package"]
    assert "care_about" in hygiene
    assert "care_about" not in intel


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.attention("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_attention_scope_isolation_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_conflict(vault, "harbor-api", "harbor-datastore")
    _seed_conflict(vault, "portal-app", "portal-cookie")
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
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/attention?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["honesty"]["attention_is_authority"] is False
        assert "cf-portal-app" not in json.dumps(harbor)
        assert "cf-harbor-api" in json.dumps(harbor)
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
        assert meta["attention_live"] is True
        status, intel = _http_json(
            str(host), int(port), hdrs, "/v1/project-attention?project=harbor-api"
        )
        assert status == 200
        assert intel.get("api_package") != harbor["api_package"]
    finally:
        server.shutdown()
