import threading
import time

import atlas_studio_bridge
from projection_cache import ProjectionCache


def test_equivalent_concurrent_reads_share_one_build():
    cache = ProjectionCache(ttl_seconds=30, failure_backoff_seconds=0)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def build():
        nonlocal calls
        calls += 1
        started.set()
        release.wait(timeout=2)
        return {"snapshot": "same"}

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get(("repo", "agent"), build))) for _ in range(3)]
    for thread in threads:
        thread.start()
    assert started.wait(timeout=1)
    release.set()
    for thread in threads:
        thread.join(timeout=2)

    assert calls == 1
    assert results == [{"snapshot": "same"}] * 3


def test_cache_expiry_and_context_isolation():
    now = [100.0]
    cache = ProjectionCache(ttl_seconds=10, clock=lambda: now[0])
    calls = []

    def build():
        calls.append(True)
        return {"call": len(calls)}

    assert cache.get(("repo-a", "agent"), build) == {"call": 1}
    assert cache.get(("repo-a", "agent"), build) == {"call": 1}
    assert cache.get(("repo-b", "agent"), build) == {"call": 2}
    now[0] += 11
    assert cache.get(("repo-a", "agent"), build) == {"call": 3}
    assert len(calls) == 3


def test_failed_build_is_not_cached():
    cache = ProjectionCache(ttl_seconds=30, failure_backoff_seconds=0)
    calls = 0

    def fail():
        nonlocal calls
        calls += 1
        raise RuntimeError("upstream")

    for _ in range(2):
        try:
            cache.get(("repo", "agent"), fail)
        except RuntimeError as error:
            assert str(error) == "upstream"
    assert calls == 2


def test_failed_build_is_suppressed_during_backoff_then_retried():
    now = [100.0]
    cache = ProjectionCache(ttl_seconds=30, failure_backoff_seconds=5, clock=lambda: now[0])
    calls = 0

    def fail():
        nonlocal calls
        calls += 1
        raise RuntimeError("rate limited")

    for _ in range(2):
        try:
            cache.get(("repo", "agent"), fail)
        except RuntimeError as error:
            assert str(error) == "rate limited"
    assert calls == 1
    now[0] += 6
    try:
        cache.get(("repo", "agent"), fail)
    except RuntimeError as error:
        assert str(error) == "rate limited"
    assert calls == 2


def test_projection_key_binds_non_secret_access_host(monkeypatch):
    monkeypatch.setenv("GH_HOST", "github.example")
    assert atlas_studio_bridge.projection_cache_key("repo", "agent") == (
        "repo", "agent", "github.example"
    )
