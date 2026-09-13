"""TAKEOVER-001: a second resident must not publish or execute concurrently."""

import threading
from pathlib import Path

import pytest

from project_atlas.orchestration.program import resident


def test_second_resident_refuses_before_overwriting_heartbeat(tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()
    root = tmp_path / "state"
    queue = root / "queue"
    one = resident.ResidentDispatcher(root=root, queue_root=queue)
    two = resident.ResidentDispatcher(root=root, queue_root=queue)

    def hold(_seconds: float) -> None:
        entered.set()
        assert release.wait(5)

    one.wait = hold
    thread = threading.Thread(target=lambda: one.run(max_ticks=1))
    thread.start()
    try:
        assert entered.wait(5)
        beat = resident.read_heartbeat(root)
        with pytest.raises(resident.DispatcherError, match="already owned"):
            two.run(max_ticks=0)
        assert resident.read_heartbeat(root) == beat
    finally:
        release.set()
        thread.join(6)
    assert not thread.is_alive()
    # Kernel ownership was released, not stranded by a stale PID file.
    two.run(max_ticks=0)
