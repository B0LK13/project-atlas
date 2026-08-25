"""AS-CODER-ALPHA-STATE-API-001 — read-only GET /v1/state."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.web_api.intelligence import read_project_state
from project_atlas.web_api.state import WebStateError, read_project_current_state


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


def _seed_state(vault: Path, project_id: str, *, conflicts: int = 0) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps({"project_id": project_id, "lifecycle": "active", "coverage": []})
        + "\n```\n",
        encoding="utf-8",
    )
    status = vault / "projects" / project_id / "knowledge-status.md"
    status.write_text(
        "| Signal | Count |\n| --- | --- |\n| unresolved conflicts | "
        + str(conflicts)
        + " |\n| claims awaiting review | 0 |\n",
        encoding="utf-8",
    )
    if conflicts:
        path = vault / "review" / "conflicts" / f"{project_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "conflict_id": f"cf-{project_id}",
                            "conflict_type": "competing-claim",
                            "field": f"{project_id}-field",
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
    with pytest.raises(WebStateError) as exc:
        read_project_current_state(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebStateError) as exc:
        read_project_current_state(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_missing_evidence_stays_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_project_current_state(vault, "empty-proj")
    assert report["project_id"] == "empty-proj"
    assert report["status"] == "unknown"
    assert report["rollup"] == "unknown"
    assert report["honesty"]["state_is_authority"] is False
    assert report["honesty"]["unknown_is_healthy"] is False
    assert report["honesty"]["rollup_is_trust_score"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["api_package"] == "AS-CODER-ALPHA-STATE-API-001"
    assert not (vault / "generated").exists()


def test_seeded_state_is_derived_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_state(vault, "harbor-api", conflicts=1)
    report = read_project_current_state(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["signals"]["unresolved_conflicts"] == 1
    assert report["honesty"]["state_is_authority"] is False
    assert "OWNER_GATE" not in json.dumps(report)
    assert not (vault / "generated" / "answers").exists()


def test_cross_project_state_is_isolated(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_state(vault, "harbor-api", conflicts=1)
    _seed_state(vault, "portal-app", conflicts=1)
    harbor = read_project_current_state(vault, "harbor-api")
    portal = read_project_current_state(vault, "portal-app")
    assert "cf-harbor-api" not in json.dumps(harbor) or harbor["project_id"] == "harbor-api"
    assert harbor["signals"]["unresolved_conflicts"] == 1
    assert portal["project_id"] == "portal-app"
    assert "portal-app-field" not in json.dumps(harbor)


def test_hygiene_route_is_not_intelligence_project_state(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    current = read_project_current_state(vault, "harbor-api")
    intel = read_project_state(vault, "harbor-api")
    assert current["api_package"] == "AS-CODER-ALPHA-STATE-API-001"
    assert current["schema"] == "atlas.coder-alpha.state-lens.v1"
    assert intel.get("package_id") != current["api_package"]


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.state("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_http_state_scope_isolation_and_writes_forbidden(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _seed_state(vault, "harbor-api", conflicts=1)
    _seed_state(vault, "portal-app", conflicts=1)
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/state")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/state?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["honesty"]["state_is_authority"] is False
        assert "portal-app-field" not in json.dumps(harbor)
        status, patched = _http_json(
            str(host),
            int(port),
            {**hdrs, "Content-Type": "application/json"},
            "/v1/state?project=harbor-api",
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
        assert meta["state_live"] is True
        status, intel = _http_json(
            str(host), int(port), hdrs, "/v1/project-state?project=harbor-api"
        )
        assert status == 200
        assert intel.get("package_id") != harbor["api_package"]
    finally:
        server.shutdown()
