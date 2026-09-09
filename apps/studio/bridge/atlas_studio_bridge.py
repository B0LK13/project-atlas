#!/usr/bin/env python3
"""Minimal read-only HTTP adapter for Atlas Studio A1 projections.

This is a development bridge, not an Atlas daemon or authority surface. It
imports the typed A1 builder directly; it never parses CLI text, accepts no
mutation methods, and exposes no UI-controlled process or filesystem input.
"""
from __future__ import annotations

import argparse
import json
import os
import select
import signal
import socket
import subprocess
import threading
import time
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio.mission_control import (  # noqa: E402
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


def run_worker(command, *, timeout=20, cancelled=lambda: False):
    """Own the worker and its gh descendants; reap them on timeout/disconnect."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled():
                raise RuntimeError("REQUEST_CANCELLED")
            if time.monotonic() >= deadline:
                raise RuntimeError("PROJECTION_DEADLINE")
            try:
                out, diagnostic = process.communicate(timeout=max(.001, min(.1, deadline-time.monotonic())))
                # Worker emits only stage names/counts/durations, never gh stderr.
                if diagnostic:
                    try:
                        report = json.loads(diagnostic)
                        print(json.dumps({"projection_timing": report}), file=sys.stderr, flush=True)
                    except ValueError:
                        pass
                packet = json.loads(out)
                if process.returncode:
                    raise RuntimeError("PROJECTION_UPSTREAM_UNAVAILABLE")
                return packet
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()


def build_current_projection(repository: str, agent_id: str | None, cancelled=lambda: False) -> dict[str, Any]:
    packet = run_worker([sys.executable, str(Path(__file__).with_name("projection_worker.py")),
                         repository, agent_id or ""], cancelled=cancelled)
    if validate_mission_control(packet):
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

    def _disconnected(self):
        if select.select([self.connection], [], [], 0)[0]:
            return self.connection.recv(1, socket.MSG_PEEK) == b""
        return False

    def do_GET(self) -> None:
        if self.headers.get("Origin") and not self._cors_origin():
            self._send_json(HTTPStatus.FORBIDDEN, {"status": "ORIGIN_REFUSED"})
            return
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
        if not self.config.slots.acquire(blocking=False):
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"status": "BUSY", "fixture_served": False})
            return
        try:
            packet = build_current_projection(self.config.repository, self.config.agent_id, self._disconnected)
        except (RuntimeError, ValueError, OSError) as exc:
            if self._disconnected():
                return
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "schema": SCHEMA,
                    "status": "OFFLINE",
                    "reason": str(exc) if isinstance(exc, RuntimeError) else "PROJECTION_UNAVAILABLE",
                    "unknown_ne_healthy": True,
                    "fixture_served": False,
                },
            )
            return
        finally:
            self.config.slots.release()
        self._send_json(HTTPStatus.OK, packet)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"atlas-studio bridge: {format % args}\n")


class ReadOnlyStudioServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], repository: str, agent_id: str | None):
        super().__init__(address, ReadOnlyStudioHandler)
        self.slots = threading.BoundedSemaphore(2)
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
