#!/usr/bin/env python3
"""Minimal read-only HTTP adapter for Atlas Studio A1 projections.

This is a development bridge, not an Atlas daemon or authority surface. It
imports the typed A1 builder directly; it never parses CLI text, accepts no
mutation methods, and exposes no UI-controlled process or filesystem input.
"""
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag.gh import GhClient, GhError  # noqa: E402
from atlas_studio.mission_control import (  # noqa: E402
    build_mission_control,
    validate_mission_control,
)

SCHEMA = "ATLAS_STUDIO_BRIDGE_STATUS_V1"
ALLOWED_ORIGINS = frozenset(
    {
        "http://127.0.0.1:1420",
        "http://127.0.0.1:4420",
        "http://localhost:1420",
        "http://localhost:4420",
        "tauri://localhost",
        "https://tauri.localhost",
    }
)


def github_read_available(repository: str) -> tuple[bool, str]:
    """Use the existing fixed GhClient boundary; no shell or UI input."""
    try:
        client = GhClient(repo=repository)
        client.run_gh(["auth", "status"])
        if client.default_branch() is None:
            return False, "GITHUB_REPOSITORY_UNAVAILABLE"
    except GhError as exc:
        return False, f"GITHUB_READ_UNAVAILABLE:{type(exc).__name__}"
    return True, "GITHUB_READ_AVAILABLE"


def build_current_projection(repository: str, agent_id: str | None) -> dict[str, Any]:
    available, reason = github_read_available(repository)
    if not available:
        raise RuntimeError(reason)
    packet = build_mission_control(agent_id=agent_id, live=True, repo=repository)
    errors = validate_mission_control(packet)
    if errors:
        raise RuntimeError("A1_SCHEMA_VALIDATION_FAILED")
    return packet


class ReadOnlyStudioHandler(BaseHTTPRequestHandler):
    server_version = "AtlasStudioReadOnly/0.1"

    @property
    def config(self) -> ReadOnlyStudioServer:
        return self.server  # type: ignore[return-value]

    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        return origin if origin in ALLOWED_ORIGINS else None

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Atlas-Authority", "none")
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Accept")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "schema": SCHEMA,
                    "status": "READ_ONLY",
                    "authority": "NONE",
                    "mutation_methods": [],
                },
            )
            return
        if self.path != "/v1/mission-control":
            self._send_json(HTTPStatus.NOT_FOUND, {"schema": SCHEMA, "status": "UNKNOWN"})
            return
        try:
            packet = build_current_projection(self.config.repository, self.config.agent_id)
        except RuntimeError as exc:
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "schema": SCHEMA,
                    "status": "OFFLINE",
                    "reason": str(exc),
                    "unknown_ne_healthy": True,
                    "fixture_served": False,
                },
            )
            return
        self._send_json(HTTPStatus.OK, packet)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"atlas-studio bridge: {format % args}\n")


class ReadOnlyStudioServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], repository: str, agent_id: str | None):
        super().__init__(address, ReadOnlyStudioHandler)
        self.repository = repository
        self.agent_id = agent_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atlas Studio read-only development bridge")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=47631)
    parser.add_argument("--repository", default="B0LK13/project-atlas")
    parser.add_argument("--agent", default=None)
    args = parser.parse_args(argv)
    server = ReadOnlyStudioServer((args.host, args.port), args.repository, args.agent)
    print(f"Atlas Studio read-only bridge on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
