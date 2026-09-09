"""D-CODEX-STUDIO-004: request budgets and request-local read reuse."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/studio/bridge'))
from projection_worker import RequestClient  # noqa: E402


def test_read_cache_is_request_local_and_deduplicates():
    calls = []
    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, 'value', '')
    first = RequestClient('owner/repo', timeout=2, runner=runner)
    assert first.run_gh(['api', 'repos/owner/repo']) == 'value'
    assert first.run_gh(['api', 'repos/owner/repo']) == 'value'
    assert len(calls) == 1
    assert 0 < calls[0][1]['timeout'] <= 2
    second = RequestClient('owner/repo', timeout=2, runner=runner)
    second.run_gh(['api', 'repos/owner/repo'])
    assert len(calls) == 2


def test_read_failures_do_not_expose_stderr_or_cache_success():
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, '', 'credential-canary')
    client = RequestClient('owner/repo', timeout=2, runner=runner)
    with pytest.raises(RuntimeError, match='UPSTREAM_READ_FAILED') as error:
        client.run_gh(['api', 'repos/owner/repo'])
    assert 'credential-canary' not in str(error.value)
    assert client.failed


def test_worker_deadline_kills_slow_process():
    spec = importlib.util.spec_from_file_location('bridge_budget', 
        ROOT / 'apps/studio/bridge/atlas_studio_bridge.py')
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    start = time.monotonic()
    with pytest.raises(RuntimeError, match='PROJECTION_DEADLINE'):
        bridge.run_worker([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.1)
    assert time.monotonic() - start < 2


def test_worker_cancellation():
    spec = importlib.util.spec_from_file_location('bridge_cancel', 
        ROOT / 'apps/studio/bridge/atlas_studio_bridge.py')
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    with pytest.raises(RuntimeError, match='REQUEST_CANCELLED'):
        bridge.run_worker([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=2,
                          cancelled=lambda: True)


def test_request_client_refuses_mutations_before_execution():
    client = RequestClient('owner/repo', runner=lambda *a, **kw: pytest.fail('executed'))
    for args in [['api', 'repos/owner/repo', '-X', 'POST'], ['pr', 'merge', '1'],
                 ['api', 'repos/owner/repo', '--method=POST']]:
        with pytest.raises(RuntimeError, match='READ_ONLY_BOUNDARY'):
            client.run_gh(args)
