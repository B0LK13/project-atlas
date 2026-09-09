"""D-CODEX-STUDIO-004: request budgets and request-local read reuse."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/studio/bridge"))
from projection_worker import RequestClient  # noqa: E402


def test_read_cache_is_request_local_and_deduplicates():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "value", "")

    first = RequestClient("owner/repo", timeout=2, runner=runner)
    assert first.run_gh(["api", "repos/owner/repo"]) == "value"
    assert first.run_gh(["api", "repos/owner/repo"]) == "value"
    assert len(calls) == 1
    assert 0 < calls[0][1]["timeout"] <= 2
    second = RequestClient("owner/repo", timeout=2, runner=runner)
    second.run_gh(["api", "repos/owner/repo"])
    assert len(calls) == 2


def test_read_failures_do_not_expose_stderr_or_cache_success():
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "credential-canary")

    client = RequestClient("owner/repo", timeout=2, runner=runner)
    with pytest.raises(RuntimeError, match="UPSTREAM_READ_FAILED") as error:
        client.run_gh(["api", "repos/owner/repo"])
    assert "credential-canary" not in str(error.value)
    assert client.failed


@pytest.mark.skipif(os.name != "posix", reason="Linux desktop process-group lifecycle")
def test_worker_deadline_kills_slow_process():
    spec = importlib.util.spec_from_file_location(
        "bridge_budget", ROOT / "apps/studio/bridge/atlas_studio_bridge.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="PROJECTION_DEADLINE"):
        bridge.run_worker([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
    assert time.monotonic() - start < 2


@pytest.mark.skipif(os.name != "posix", reason="Linux desktop process-group lifecycle")
def test_worker_cancellation():
    spec = importlib.util.spec_from_file_location(
        "bridge_cancel", ROOT / "apps/studio/bridge/atlas_studio_bridge.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    with pytest.raises(RuntimeError, match="REQUEST_CANCELLED"):
        bridge.run_worker(
            [sys.executable, "-c", "import time; time.sleep(10)"], timeout=2, cancelled=lambda: True
        )


def test_request_client_refuses_mutations_before_execution():
    client = RequestClient("owner/repo", runner=lambda *a, **kw: pytest.fail("executed"))
    for args in [
        ["api", "repos/owner/repo", "-X", "POST"],
        ["pr", "merge", "1"],
        ["api", "repos/owner/repo", "--method=POST"],
    ]:
        with pytest.raises(RuntimeError, match="READ_ONLY_BOUNDARY"):
            client.run_gh(args)


@pytest.mark.parametrize(
    "args",
    [
        ["api", "repos/owner/repo/issues", "-XPOST"],
        ["api", "repos/owner/repo/issues", "-fbody=x"],
        ["api", "repos/owner/repo/issues", "--input=/tmp/body"],
        ["auth", "status", "--show-token"],
        ["api", "repos/owner/repository"],
    ],
)
def test_compact_mutation_and_token_options_are_refused(args):
    client = RequestClient("owner/repo", runner=lambda *a, **kw: pytest.fail("executed"))
    with pytest.raises(RuntimeError, match="READ_ONLY_BOUNDARY"):
        client.run_gh(args)


@pytest.mark.parametrize(
    "code",
    [
        "PROJECTION_FAILED_AUTHENTICATION",
        "PROJECTION_FAILED_UPSTREAM_READS",
        "PROJECTION_FAILED_PROJECTION_CONSTRUCTION",
        "credential-canary",
    ],
)
def test_worker_failure_stage_is_allowlisted(code):
    spec = importlib.util.spec_from_file_location(
        "bridge_stage", ROOT / "apps/studio/bridge/atlas_studio_bridge.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    program = 'import json,sys;print(json.dumps({"error":sys.argv[1]}));sys.exit(1)'
    expected = code if code.startswith("PROJECTION_FAILED_") else "PROJECTION_UPSTREAM_UNAVAILABLE"
    with pytest.raises(RuntimeError, match=expected):
        bridge.run_worker([sys.executable, "-c", program, code])


def test_http_boundary_rejects_write_methods_and_foreign_origins(monkeypatch):
    import http.client
    import threading

    spec = importlib.util.spec_from_file_location(
        "bridge_http", ROOT / "apps/studio/bridge/atlas_studio_bridge.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    calls = []
    monkeypatch.setattr(
        bridge,
        "build_current_projection",
        lambda *args: calls.append(args) or {"test": "read-only"},
    )
    server = bridge.ReadOnlyStudioServer(("127.0.0.1", 0), "owner/repo", None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for method, origin, expected in [
            ("POST", "http://127.0.0.1:4420", 501),
            ("PUT", "http://127.0.0.1:4420", 501),
            ("DELETE", "http://127.0.0.1:4420", 501),
            ("GET", "https://foreign.example", 403),
            ("GET", "http://127.0.0.1:4420", 200),
        ]:
            connection = http.client.HTTPConnection(*server.server_address, timeout=2)
            connection.request(method, "/v1/mission-control", headers={"Origin": origin})
            response = connection.getresponse()
            assert response.status == expected
            response.read()
            connection.close()
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_compare_sha_separator_is_read_only_not_path_traversal():
    # D-CODEX-STUDIO-005: GitHub's SHA...SHA compare path is required by A1.
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, '{"status":"ahead"}', '')

    client = RequestClient("owner/repo", runner=runner)
    assert client.is_ancestor("a" * 40, "b" * 40) is True
    assert not client.failed
    with pytest.raises(RuntimeError, match="READ_ONLY_BOUNDARY"):
        client.run_gh(["api", "repos/owner/repo/../other"])
