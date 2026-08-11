"""AS-2.1-API-SERVER-001 - stdlib LIVE_API read server (+ bounded actions).

Serves AppService JSON over HTTP. Default bind 127.0.0.1 only.
GET is read-only. POST /v1/actions records reconstructable web actions only
(never Layer B). Requires authz api.read / web.action as applicable.
Hardened: localhost CORS, Host gate, POST size cap, obs/authz/mcp routes.

SEC-009: loopback / Host binding is defense-in-depth only. Every GET/POST
requires a high-entropy per-launch Bearer credential bound to an explicit
request principal (OperatorProfile).
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from project_atlas.app_service import AppService, open_app_service
from project_atlas.ask_atlas_live import AskAtlasLiveError, ask_atlas_live
from project_atlas.authz import (
    ApiAuthError,
    ApiSessionCredentials,
    ApiSessionStore,
    OperatorProfile,
    default_operator,
    mint_api_session,
)
from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.mcp_server import list_mcp_tools
from project_atlas.obs_live import build_live_observability_receipt
from project_atlas.ops_receipts import inventory_ops_receipts
from project_atlas.web_actions import (
    WebActionError,
    list_recent_actions,
    load_action_ledger,
    submit_web_action,
)
from project_atlas.web_mission_workspace import build_mission_view, build_workspace_view

PACKAGE_ID = "AS-2.1-API-SERVER-001"
TRUTH_BOUNDARY = (
    "LIVE_API READ + BOUNDED ACTIONS != AUTHORITY / != LAYER-B WRITE"
)
MAX_POST_BYTES = 64_000
CORS_ORIGIN = "http://127.0.0.1:5173"
_LOCAL_HOST_RE = re.compile(
    r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$",
    re.IGNORECASE,
)


class ApiServerError(ValueError):
    """Fail-closed API server error."""


class AtlasApiServer(ThreadingHTTPServer):
    """Threading HTTP server carrying the per-launch API session store."""

    atlas_session: ApiSessionStore


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_limit(qs: dict[str, list[str]], *, default: int = 100) -> int:
    raw = (qs.get("limit") or [str(default)])[0]
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiServerError("api-limit-invalid") from exc
    if value < 1 or value > 500:
        raise ApiServerError("api-limit-out-of-range")
    return value


def session_credentials(server: ThreadingHTTPServer) -> ApiSessionCredentials:
    """Return the per-launch credentials attached to a LIVE_API server."""
    store = getattr(server, "atlas_session", None)
    if not isinstance(store, ApiSessionStore):
        raise ApiServerError("api-session-missing")
    return store.credentials


def make_handler(
    service: AppService,
    session: ApiSessionStore,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to a vault AppService + session store."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization",
            )
            self.send_header("Vary", "Origin")

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Atlas-Package", PACKAGE_ID)
            self.send_header("X-Atlas-Truth-Boundary", TRUTH_BOUNDARY)
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").strip()
            if not host:
                return True
            return bool(_LOCAL_HOST_RE.fullmatch(host))

        def _authenticate(self) -> OperatorProfile | None:
            """Resolve request principal; send 401 and return None on failure."""
            try:
                return session.resolve_bearer(self.headers.get("Authorization"))
            except ApiAuthError as exc:
                self._send(401, {"error": str(exc), "package_id": PACKAGE_ID})
                return None

        def do_OPTIONS(self) -> None:
            # CORS preflight: Host gate only (browsers omit Authorization).
            if not self._host_ok():
                self._send(403, {"error": "host-non-local-forbidden", "package_id": PACKAGE_ID})
                return
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            if not self._host_ok():
                self._send(403, {"error": "host-non-local-forbidden", "package_id": PACKAGE_ID})
                return
            operator = self._authenticate()
            if operator is None:
                return
            try:
                operator.require("api.read")
            except PermissionError as exc:
                self._send(403, {"error": str(exc), "package_id": PACKAGE_ID})
                return
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            qs = parse_qs(parsed.query)
            if path == "/v1/ask":
                query = (qs.get("q") or qs.get("query") or [""])[0]
                try:
                    self._send(
                        200,
                        ask_atlas_live(service.vault, query=query, operator=operator),
                    )
                except (AskAtlasLiveError, PermissionError, ValueError) as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                return
            if path == "/v1/projects":
                try:
                    limit = _parse_limit(qs)
                except ApiServerError as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                    return
                projects = service.projects()[:limit]
                self._send(200, {"projects": projects, "limit": limit})
                return
            if path == "/v1/knowledge":
                try:
                    limit = _parse_limit(qs)
                except ApiServerError as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                    return
                knowledge = service.knowledge()[:limit]
                self._send(200, {"knowledge": knowledge, "limit": limit})
                return
            if path == "/v1/actions/recent":
                try:
                    limit = _parse_limit(qs, default=20)
                except ApiServerError as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                    return
                self._send(200, list_recent_actions(service.vault, limit=limit))
                return
            if path == "/v1/ops/receipts":
                try:
                    limit = _parse_limit(qs, default=100)
                except ApiServerError as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                    return
                try:
                    self._send(
                        200,
                        inventory_ops_receipts(service.vault, limit=limit),
                    )
                except ValueError as exc:
                    self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                return
            routes: dict[str, Any] = {
                "/health": lambda: service.health(),
                "/v1/health": lambda: service.health(),
                "/v1/graph": lambda: service.graph_summary(),
                "/v1/snapshot": lambda: service.snapshot(),
                "/v1/actions": lambda: load_action_ledger(service.vault),
                "/v1/mcp/tools": lambda: list_mcp_tools(operator=operator),
                "/v1/obs": lambda: build_live_observability_receipt(
                    service.vault, receipt_id="api-obs"
                ),
                "/v1/mission": lambda: build_mission_view(service.vault),
                "/v1/workspace": lambda: build_workspace_view(service.vault),
                "/v1/authz": lambda: {
                    "package_id": "AS-2.1-AUTHZ-001",
                    "operator_id": operator.operator_id,
                    "capabilities": sorted(operator.capabilities),
                    "authority": False,
                    "write_enabled": False,
                },
                "/v1/meta": lambda: {
                    "package_id": PACKAGE_ID,
                    "truth_boundary": TRUTH_BOUNDARY,
                    "write_enabled": False,
                    "actions_enabled": True,
                    "live_api": True,
                    "ask_atlas_live": True,
                    "ask_atlas_2": True,
                    "obs_live": True,
                    "ops_receipts": True,
                    "mission_live": True,
                    "workspace_live": True,
                    "authz_profile": True,
                    "session_auth": True,
                    "max_post_bytes": MAX_POST_BYTES,
                    "cors_origin": CORS_ORIGIN,
                    "operator_id": operator.operator_id,
                },
            }
            if path not in routes:
                self._send(404, {"error": "not-found", "path": path})
                return
            try:
                self._send(200, routes[path]())
            except PermissionError as exc:
                self._send(403, {"error": str(exc), "package_id": PACKAGE_ID})

        def do_POST(self) -> None:
            if not self._host_ok():
                self._send(403, {"error": "host-non-local-forbidden", "package_id": PACKAGE_ID})
                return
            operator = self._authenticate()
            if operator is None:
                return
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path != "/v1/actions":
                self._send(
                    405,
                    {
                        "error": "writes-forbidden",
                        "package_id": PACKAGE_ID,
                        "truth_boundary": TRUTH_BOUNDARY,
                    },
                )
                return
            raw_length = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_length)
            except ValueError:
                self._send(
                    400,
                    {
                        "error": "content-length-invalid",
                        "package_id": PACKAGE_ID,
                    },
                )
                return
            if length < 0 or length > MAX_POST_BYTES:
                # Close without reading body (DoS-safe). Clients — especially on
                # Windows — may see connection abort instead of a full 413 body.
                self.close_connection = True
                self._send(
                    413,
                    {
                        "error": "payload-too-large",
                        "max_post_bytes": MAX_POST_BYTES,
                        "package_id": PACKAGE_ID,
                    },
                )
                return
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                # Avoid leaking parser internals / filesystem paths (ADV path leakage).
                self._send(
                    400,
                    {"error": "json-invalid", "package_id": PACKAGE_ID},
                )
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "body-not-object"})
                return
            try:
                txn = submit_web_action(
                    service.vault,
                    action_id=str(body.get("action_id", "")),
                    action_type=body.get("action_type"),  # type: ignore[arg-type]
                    payload=body.get("payload")
                    if isinstance(body.get("payload"), dict)
                    else {},
                    operator=operator,
                )
            except (WebActionError, PermissionError, TypeError, ValueError) as exc:
                self._send(400, {"error": str(exc), "package_id": PACKAGE_ID})
                return
            self._send(200, {"accepted": True, "transaction": txn})

        def do_PUT(self) -> None:
            if not self._host_ok():
                self._send(403, {"error": "host-non-local-forbidden", "package_id": PACKAGE_ID})
                return
            if self._authenticate() is None:
                return
            self._send(405, {"error": "writes-forbidden", "package_id": PACKAGE_ID})

        def do_DELETE(self) -> None:
            if not self._host_ok():
                self._send(403, {"error": "host-non-local-forbidden", "package_id": PACKAGE_ID})
                return
            if self._authenticate() is None:
                return
            self._send(405, {"error": "writes-forbidden", "package_id": PACKAGE_ID})

    return Handler


def serve_api(
    vault: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    operator: OperatorProfile | None = None,
    session: ApiSessionStore | None = None,
) -> AtlasApiServer:
    """Create (but do not serve forever) a LIVE_API server instance.

    Mints (or accepts) a per-launch session store. Callers must present a
    Bearer credential from ``server.atlas_session.credentials`` on every
    GET/POST (SEC-009).
    """
    require_compatibility_anchor()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ApiServerError("api-bind-non-local-forbidden")
    svc = open_app_service(vault)
    launch_op = operator or default_operator()
    launch_op.require("api.read")
    store = session or mint_api_session(launch_op)
    # Ensure the read principal can serve api.read.
    store.credentials.read_operator.require("api.read")
    handler = make_handler(svc, store)
    server = AtlasApiServer((host, port), handler)
    server.atlas_session = store
    return server
