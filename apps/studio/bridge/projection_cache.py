"""Bounded request coalescing for read-only Studio projections."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=tuple[str, ...])


@dataclass
class _Pending(Generic[T]):
    event: threading.Event
    value: T | None = None
    error: BaseException | None = None


class ProjectionCache(Generic[T, K]):
    """Cache validated packets briefly and coalesce equivalent in-flight reads."""

    def __init__(
        self,
        ttl_seconds: float,
        failure_backoff_seconds: float = 5,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self.failure_backoff_seconds = failure_backoff_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._values: dict[K, tuple[float, T]] = {}
        self._pending: dict[K, _Pending[T]] = {}
        self._failures: dict[K, tuple[float, BaseException]] = {}

    def get(self, key: K, builder: Callable[[], T]) -> T:
        now = self.clock()
        with self._lock:
            cached = self._values.get(key)
            if cached and now - cached[0] <= self.ttl_seconds:
                return cached[1]
            failure = self._failures.get(key)
            if failure and now < failure[0]:
                raise failure[1]
            pending = self._pending.get(key)
            if pending is None:
                pending = _Pending(threading.Event())
                self._pending[key] = pending
                owner = True
            else:
                owner = False
        if not owner:
            pending.event.wait()
            if pending.error is not None:
                raise pending.error
            if pending.value is None:
                raise RuntimeError("PROJECTION_CACHE_EMPTY")
            return pending.value
        try:
            value = builder()
        except BaseException as error:
            with self._lock:
                pending.error = error
                self._pending.pop(key, None)
                self._failures[key] = (self.clock() + self.failure_backoff_seconds, error)
                pending.event.set()
            raise
        with self._lock:
            self._values[key] = (self.clock(), value)
            self._failures.pop(key, None)
            pending.value = value
            self._pending.pop(key, None)
            pending.event.set()
        return value
