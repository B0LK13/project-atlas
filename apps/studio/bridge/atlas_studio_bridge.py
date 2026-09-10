#!/usr/bin/env python3
"""Minimal read-only HTTP adapter for Atlas Studio A1 projections.

This is a development bridge, not an Atlas daemon or authority surface. It
imports the typed A1 builder directly; it never parses CLI text, accepts no
mutation methods, and exposes no UI-controlled process or filesystem input.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio.mission_control import (  # noqa: E402
    validate_mission_control,
)
from atlas_studio.mission_journey import (  # noqa: E402
    build_mission_journey,
    validate_mission_journey,
)
from atlas_studio.task_context import (  # noqa: E402
    build_task_context,
    validate_task_context,
)
from projection_cache import ProjectionCache  # noqa: E402

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
PROJECTION_CACHE_TTL_SECONDS = 15
projection_cache: ProjectionCache[dict[str, Any], tuple[str, ...]] = ProjectionCache(
    ttl_seconds=PROJECTION_CACHE_TTL_SECONDS
)


def run_worker(command, *, timeout=20, cancelled=lambda: False):
    """Own the worker and its gh descendants; reap them on timeout/disconnect."""
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled():
                raise RuntimeError("REQUEST_CANCELLED")
            if time.monotonic() >= deadline:
                raise RuntimeError("PROJECTION_DEADLINE")
            try:
                out, diagnostic = process.communicate(
                    timeout=max(0.001, min(0.1, deadline - time.monotonic()))
                )
                # Worker emits only stage names/counts/durations, never gh stderr.
                if diagnostic:
                    try:
                        report = json.loads(diagnostic)
                        print(
                            json.dumps({"projection_timing": report}), file=sys.stderr, flush=True
                        )
                    except ValueError:
                        pass
                packet = json.loads(out)
                if process.returncode:
                    allowed = {
                        "PROJECTION_FAILED_AUTHENTICATION",
                        "PROJECTION_FAILED_UPSTREAM_READS",
                        "PROJECTION_FAILED_PROJECTION_CONSTRUCTION",
                    }
                    code = packet.get("error") if isinstance(packet, dict) else None
                    raise RuntimeError(
                        code if code in allowed else "PROJECTION_UPSTREAM_UNAVAILABLE"
                    )
                return packet
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()


def build_current_projection(
    repository: str, agent_id: str | None, cancelled=lambda: False
) -> dict[str, Any]:
    key = (repository, agent_id or "")

    def collect() -> dict[str, Any]:
        return run_worker(
            [
                sys.executable,
                str(Path(__file__).with_name("projection_worker.py")),
                repository,
                agent_id or "",
            ],
            cancelled=cancelled,
        )

    packet = projection_cache.get(key, collect)
    if validate_mission_control(packet):
        raise RuntimeError("A1_SCHEMA_VALIDATION_FAILED")
    return packet


def build_current_journey_projection(
    repository: str, agent_id: str | None, cancelled=lambda: False
) -> dict[str, Any]:
    """Pass the validated A1 read through the integration journey builder."""
    mission_control = build_current_projection(repository, agent_id, cancelled)
    packet = build_mission_journey(
        agent_id=agent_id,
        repo=repository,
        mission_control=mission_control,
        live=False,
        docs_root=REPO_ROOT / "docs",
    )
    if validate_mission_journey(packet):
        raise RuntimeError("MISSION_JOURNEY_SCHEMA_VALIDATION_FAILED")
    return packet


def build_current_task_context(
    repository: str, agent_id: str | None, lane: str, cancelled=lambda: False
) -> dict[str, Any]:
    """Compose the integration-owned task-context packet through a read-only seam.

    The bounded packet intentionally uses the already available Mission Control
    projection. Frontier and stack enrichment remain explicit missing inputs;
    invoking the live CLI here would turn a read request into an unbounded wait.
    """
    if not agent_id:
        raise RuntimeError("TASK_CONTEXT_AGENT_REQUIRED")
    if not lane.startswith("pr/") or not lane[3:].isdigit() or len(lane) > 80:
        raise RuntimeError("TASK_CONTEXT_LANE_INVALID")
    if cancelled():
        raise RuntimeError("REQUEST_CANCELLED")
    try:
        mission_control = build_current_projection(repository, agent_id, cancelled=cancelled)
        packet = build_task_context(
            lane=lane,
            agent_id=agent_id,
            mission_control=mission_control,
            journey=None,
        )
    except OSError as exc:
        raise RuntimeError("TASK_CONTEXT_UPSTREAM_UNAVAILABLE") from exc
    if validate_task_context(packet):
        raise RuntimeError("TASK_CONTEXT_SCHEMA_VALIDATION_FAILED")
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
        route, _, query = self.path.partition("?")
        if route not in {"/v1/mission-control", "/v1/mission-journey", "/v1/task-context"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"schema": SCHEMA, "status": "UNKNOWN"})
            return
        if not self.config.slots.acquire(blocking=False):
            self._send_json(
                HTTPStatus.TOO_MANY_REQUESTS, {"status": "BUSY", "fixture_served": False}
            )
            return
        try:
            if route == "/v1/mission-control":
                packet = build_current_projection(
                    self.config.repository, self.config.agent_id, self._disconnected
                )
            elif route == "/v1/mission-journey":
                packet = build_current_journey_projection(
                    self.config.repository, self.config.agent_id, self._disconnected
                )
            else:
                from urllib.parse import parse_qs

                lane = parse_qs(query, strict_parsing=False).get("lane", [""])[0]
                packet = build_current_task_context(
                    self.config.repository, self.config.agent_id, lane, self._disconnected
                )
        except (RuntimeError, ValueError, OSError) as exc:
            if self._disconnected():
                return
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "schema": SCHEMA,
                    "status": "OFFLINE",
                    "reason": str(exc)
                    if isinstance(exc, RuntimeError)
                    else "PROJECTION_UNAVAILABLE",
                    "diagnostic_ref": (
                        f"ATLAS-STUDIO-{str(exc)}"
                        if isinstance(exc, RuntimeError)
                        and str(exc).startswith("PROJECTION_FAILED_")
                        else "ATLAS-STUDIO-PROJECTION-UNAVAILABLE"
                    ),
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
