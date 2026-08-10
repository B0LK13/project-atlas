"""AS-2.1-API-SERVER-001 - stdlib LIVE_API read server.

Serves AppService JSON over HTTP. Default bind 127.0.0.1 only.
Write routes are rejected. Requires authz api.read.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from project_atlas.app_service import AppService, open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import require_compatibility_anchor

PACKAGE_ID = "AS-2.1-API-SERVER-001"
TRUTH_BOUNDARY = "LIVE_API READ-ONLY != AUTHORITY / != WRITE BRIDGE"


class ApiServerError(ValueError):
    """Fail-closed API server error."""


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def make_handler(
    service: AppService,
    operator: OperatorProfile,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to a vault AppService."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Atlas-Package", PACKAGE_ID)
            self.send_header("X-Atlas-Truth-Boundary", TRUTH_BOUNDARY)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            try:
                operator.require("api.read")
            except PermissionError as exc:
                self._send(403, {"error": str(exc), "package_id": PACKAGE_ID})
                return
            path = urlparse(self.path).path.rstrip("/") or "/"
            routes: dict[str, Any] = {
                "/health": lambda: service.health(),
                "/v1/health": lambda: service.health(),
                "/v1/projects": lambda: {"projects": service.projects()},
                "/v1/knowledge": lambda: {"knowledge": service.knowledge()},
                "/v1/graph": lambda: service.graph_summary(),
                "/v1/snapshot": lambda: service.snapshot(),
                "/v1/meta": lambda: {
                    "package_id": PACKAGE_ID,
                    "truth_boundary": TRUTH_BOUNDARY,
                    "write_enabled": False,
                    "live_api": True,
                    "operator_id": operator.operator_id,
                },
            }
            if path not in routes:
                self._send(404, {"error": "not-found", "path": path})
                return
            self._send(200, routes[path]())

        def do_POST(self) -> None:
            self._send(
                405,
                {
                    "error": "writes-forbidden",
                    "package_id": PACKAGE_ID,
                    "truth_boundary": TRUTH_BOUNDARY,
                },
            )

        def do_PUT(self) -> None:
            self.do_POST()

        def do_DELETE(self) -> None:
            self.do_POST()

    return Handler


def serve_api(
    vault: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    operator: OperatorProfile | None = None,
) -> ThreadingHTTPServer:
    """Create (but do not serve forever) a LIVE_API server instance."""
    require_compatibility_anchor()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ApiServerError("api-bind-non-local-forbidden")
    svc = open_app_service(vault)
    op = operator or default_operator()
    op.require("api.read")
    handler = make_handler(svc, op)
    return ThreadingHTTPServer((host, port), handler)
