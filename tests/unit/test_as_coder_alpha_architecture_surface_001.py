"""AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001 — read-only /v1/architecture."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.project_architecture import ARCHITECTURE_SLOTS
from project_atlas.web_api.architecture import WebArchitectureError, read_architecture

_HARBOR_TOKEN = "HarborControlPlaneToken"
_PORTAL_TOKEN = "PortalDataPlaneToken"
_SECRET = "AKIAIOSFODNN7EXAMPLE"


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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan_text(*, purpose: str, token: str) -> str:
    return (
        "# Plan\n\n"
        f"{purpose}\n\n"
        "# 2. Core architectural decision\n\n"
        "I recommend a **three-layer vault**.\n\n"
        f"## Layer A - Source evidence\n\n{token} owned evidence plane.\n\n"
        "## Layer B - Canonical knowledge\n\nStructured OKF concept documents.\n\n"
        "## Layer C - Portfolio intelligence\n\nCross-project views.\n"
    )


def _seed_two_project_vault(vault: Path) -> None:
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "portal-app").mkdir(parents=True)
    (vault / "projects" / "harbor-api" / "layer-b-note.md").write_text(
        f"# Layer B\n\nsecret {_SECRET}\n",
        encoding="utf-8",
    )
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True)
    (imported / "harbor-plan.md").write_text(
        _plan_text(purpose="Harbor API persistence brain.", token=_HARBOR_TOKEN),
        encoding="utf-8",
    )
    (imported / "portal-plan.md").write_text(
        _plan_text(purpose="Portal App operator console.", token=_PORTAL_TOKEN),
        encoding="utf-8",
    )
    (imported / "harbor-readme.md").write_text(
        f"# Harbor\n\nREADME is not architecture authority. {_SECRET}\nPython stack invented?\n",
        encoding="utf-8",
    )
    _write_json(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "source_root": str(vault / "src-root"),
            "sources": [
                {
                    "path": "docs/plan.md",
                    "source_id": "harbor-plan",
                    "likely_project": "harbor-api",
                },
                {
                    "path": "docs/plan.md",
                    "source_id": "portal-plan",
                    "likely_project": "portal-app",
                },
                {
                    "path": "README.md",
                    "source_id": "harbor-readme",
                    "likely_project": "harbor-api",
                },
            ],
        },
    )


def test_read_requires_explicit_project(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(WebArchitectureError) as exc:
        read_architecture(vault, "")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebArchitectureError) as exc:
        read_architecture(vault, "   ")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"
    with pytest.raises(WebArchitectureError) as exc:
        read_architecture(vault, "a" * 80)
    assert exc.value.honesty == "MALFORMED_INPUT"
    with pytest.raises(WebArchitectureError) as exc:
        read_architecture(vault, "../harbor-api")
    assert exc.value.honesty == "MALFORMED_INPUT"


def test_empty_project_stays_unknown_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = read_architecture(vault, "harbor-api")
    assert report["project_id"] == "harbor-api"
    assert report["api_package"] == "AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001"
    assert report["honesty"]["lens_is_authority"] is False
    assert report["honesty"]["ui_is_canonical"] is False
    assert report["status"] == "unknown"
    assert report["summary"] is None
    assert set(report["slots"]) == set(ARCHITECTURE_SLOTS)
    assert all(value == "UNKNOWN" for value in report["slots"].values())
    blob = json.dumps(report)
    assert "Python" not in blob
    assert "TypeScript" not in blob
    assert "React" not in blob


def test_app_service_rejects_unscoped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    svc = open_app_service(vault)
    with pytest.raises(AppServiceError) as exc:
        svc.architecture("")
    assert exc.value.honesty == "UNSUPPORTED_SCOPE"


def test_read_returns_structured_slots_without_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _seed_two_project_vault(vault)
    before = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    report = read_architecture(vault, "harbor-api")
    assert report["project_id"] == "harbor-api"
    assert report["status"] == "derived"
    assert set(report["slots"]) == set(ARCHITECTURE_SLOTS)
    assert report["slots"]["knowledge_pipeline"] != "UNKNOWN"
    assert _HARBOR_TOKEN in str(report["slots"]["knowledge_pipeline"])
    assert _PORTAL_TOKEN not in json.dumps(report)
    assert _SECRET not in json.dumps(report)
    after = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (vault / "generated" / "answers").exists()


def test_authority_ranked_source_secret_redacted_not_echoed(tmp_path: Path) -> None:
    """IV-472-SECRET-ECHO-001 — authority-ranked docs must not echo secrets."""
    vault = tmp_path / "v"
    _seed_two_project_vault(vault)
    plan = vault / "sources" / "imported-documents" / "harbor-plan.md"
    plan.write_text(
        _plan_text(purpose="Harbor API persistence brain.", token=_SECRET),
        encoding="utf-8",
    )
    report = read_architecture(vault, "harbor-api")
    blob = json.dumps(report)
    assert _SECRET not in blob
    assert "[redacted: secret-shaped value]" in blob


def test_http_architecture_scope_writes_and_leak(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _seed_two_project_vault(vault)
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
        status, missing = _http_json(str(host), int(port), hdrs, "/v1/architecture")
        assert status == 400
        assert missing["honesty"] == "UNSUPPORTED_SCOPE"
        assert missing["error"] == "architecture-requires-project"
        status, empty = _http_json(str(host), int(port), hdrs, "/v1/architecture?project=")
        assert status == 400
        assert empty["honesty"] == "UNSUPPORTED_SCOPE"
        status, long_tok = _http_json(
            str(host), int(port), hdrs, "/v1/architecture?project=" + ("x" * 80)
        )
        assert status == 400
        assert long_tok["honesty"] == "MALFORMED_INPUT"
        status, harbor = _http_json(
            str(host), int(port), hdrs, "/v1/architecture?project=harbor-api"
        )
        assert status == 200
        assert harbor["project_id"] == "harbor-api"
        assert harbor["honesty"]["lens_is_authority"] is False
        assert harbor["honesty"]["ui_is_canonical"] is False
        assert set(harbor["slots"]) == set(ARCHITECTURE_SLOTS)
        assert _HARBOR_TOKEN in json.dumps(harbor)
        status, portal = _http_json(
            str(host), int(port), hdrs, "/v1/architecture?project=portal-app"
        )
        assert status == 200
        assert portal["project_id"] == "portal-app"
        harbor_blob = json.dumps(harbor)
        portal_blob = json.dumps(portal)
        leak_count = 0
        if _PORTAL_TOKEN in harbor_blob:
            leak_count += 1
        if _HARBOR_TOKEN in portal_blob:
            leak_count += 1
        assert leak_count == 0
        assert _SECRET not in harbor_blob
        assert _SECRET not in portal_blob
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, blocked = _http_json(
                str(host),
                int(port),
                {**hdrs, "Content-Type": "application/json"},
                "/v1/architecture?project=harbor-api",
                method=method,
                body=b"{}",
            )
            assert status == 405
            assert blocked["error"] == "writes-forbidden"
        after = {
            path.relative_to(vault).as_posix(): path.read_bytes()
            for path in vault.rglob("*")
            if path.is_file()
        }
        assert after == before
        assert not (vault / "generated" / "answers").exists()
        status, meta = _http_json(str(host), int(port), hdrs, "/v1/meta")
        assert status == 200
        assert meta["architecture_live"] is True
        assert meta["write_enabled"] is False
    finally:
        server.shutdown()
