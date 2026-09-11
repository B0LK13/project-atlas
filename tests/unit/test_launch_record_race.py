"""The launch record must exist from the instant the child does, not from the
instant we finish asking the operating system who it is.

WAS
    `run_child_to_completion` spawned the child, THEN computed
    `process_start_identity(pid)`, and only then fired the callback that made
    the launch durable. The child was live for the whole of that middle step.
    `AttemptRecord` receives a pid only on ADAPTER_RETURNED, so in flight
    `attempt_liveness` falls back to the launch record -- which did not exist
    yet -- and `process_liveness(None, ...)` answered

        "no process identity was recorded for this attempt"

    which `classify_attempt` correctly escalated to NEEDS_RECONCILIATION, about
    a worker that was running perfectly well.

    On Linux the identity probe reads /proc and the window is microseconds, so
    it was effectively never lost. On Windows it starts PowerShell. Two
    independent native-Windows hosts lost it 18 times out of 18; a hosted
    windows-latest runner won it every recorded run. Deterministic per host,
    divergent across hosts -- so the gate stayed green while real machines were
    reliably broken.

NOW
    The adapter records a launch INTENT between the spawn and the probe, so
    there is no instant at which a live child is unrecorded. The intent carries
    the launching supervisor's pid and instance token, which is what makes a
    pid without an identity safe to act on: it cannot be a reused pid while the
    process still waiting for it is itself still running. Liveness gains
    IN_FLIGHT for exactly that state.

    Fail-closed is unchanged and is asserted below: an orphaned intent -- one
    whose supervisor is gone -- is UNKNOWN, not IN_FLIGHT, and still routes to
    NEEDS_RECONCILIATION.

These tests force the delay instead of hoping for it, so they are deterministic
on every platform rather than on slow ones. Zero model calls.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from test_supervisor_g3_reconciliation import (
    test_g3_running_attempt_is_not_reported_as_needing_reconciliation as _g3_oracle,
)

from project_atlas.orchestration.program.adapters import base as adapters_base
from project_atlas.orchestration.program.adapters.base import process_start_identity
from project_atlas.orchestration.program.recovery import (
    Liveness,
    RecoveryAction,
    _intent_liveness,
    process_liveness,
)
from project_atlas.orchestration.program.store import (
    ProgramStateRecord,
    clear_launch,
    launches_dir,
    load_launch_intent,
    persist_state,
    record_launch_intent,
)

#: Upper bound only. The hold below is released by an event, not by a clock, so
#: this is a deadlock guard and never a timing assumption.
HOLD_TIMEOUT_SECONDS = 90.0


def _hold_identity_until_child_has_probed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    during: Callable[[], None] | None = None,
) -> None:
    """Hold the identity probe open until the child has done its work.

    A fixed ``time.sleep`` would have been the obvious way to widen the window,
    and it is the wrong one: it makes the test a race with a bigger margin
    rather than not a race, so it stays host-dependent -- too short on a slow
    machine, pure wasted wall-clock on a fast one. The Windows CI job already
    finishes its suite at 28:34 of a 30-minute budget, so seconds of deliberate
    sleeping are not free either.

    So the probe is held on the child's own output instead. ``probe.json`` is
    written by the G3 fixture worker AFTER it has asked this program for its
    status -- which is precisely the observation the defect corrupted. Holding
    until it appears guarantees the child observes the window, on any hardware,
    and costs exactly as long as the child actually takes.

    The timeout is a deadlock guard, not a timing assumption: if it ever fires
    the test fails loudly rather than silently becoming a coin flip.
    """
    real = adapters_base.process_start_identity
    probe_out = tmp_path / "probe.json"

    def held(pid: int) -> str:
        deadline = time.monotonic() + HOLD_TIMEOUT_SECONDS
        while not probe_out.exists():
            if time.monotonic() > deadline:
                raise AssertionError(
                    "the child never produced probe.json, so the identity "
                    "window was never actually held open and this test would "
                    "have proved nothing"
                )
            time.sleep(0.01)
        if during is not None:
            during()
        return real(pid)

    monkeypatch.setattr(adapters_base, "process_start_identity", held)


def test_one_run_proves_the_window_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression, the ordering, and process cleanup -- from ONE launch.

    Deliberately one scenario with three observations rather than three
    scenarios. The Windows CI job finishes its suite at 28:34 of a 30-minute
    budget, so each extra supervisor-plus-child run is spent out of a budget
    that is already nearly gone; three would likely have pushed the job past it
    and produced no verdict at all, which is worth less than any of the three
    assertions.

    The oracle is IMPORTED, not reimplemented. It was written before this
    repair existed and is byte-identical to the version that failed on
    candidate 009, so it cannot have been shaped around the fix. Everything
    this test adds is the hold and the observations taken during it.

    On candidate 009 this fails with "no process identity was recorded for this
    attempt". It passes here.
    """
    state_root = tmp_path / "state"
    seen: dict[str, object] = {}
    children_before = _child_pids()

    def observe_during_the_window() -> None:
        # The one moment that matters: the child is live and has already asked
        # this program for its status, and the identity probe has not returned.
        seen["intents"] = _launch_files(state_root, ".intent.json")
        seen["identified"] = _launch_files(state_root, ".json")

    _hold_identity_until_child_has_probed(
        monkeypatch, tmp_path, during=observe_during_the_window
    )

    _g3_oracle(tmp_path)

    # 1. Ordering: the intent was on disk while the identity was still unknown.
    intents = seen["intents"]
    assert isinstance(intents, list) and intents, (
        "no launch intent existed while the child was already running and had "
        "already read this program's status -- that is the window the repair "
        "closes, and nothing was written into it"
    )
    intent = intents[0]
    assert intent["identity_state"] == "PENDING"
    assert isinstance(intent["pid"], int) and intent["pid"] > 0
    assert isinstance(intent["supervisor_pid"], int) and intent["supervisor_pid"] > 0
    assert intent["supervisor_instance_id"]

    # 2. And the identified record was NOT, or this test is observing the wrong
    #    instant and its first assertion would be trivially satisfiable.
    assert seen["identified"] == [], (
        "the identified launch record already existed during the identity "
        "probe, so this test is not observing the window it claims to"
    )

    # 3. No worker outlived its attempt. The repair adds a callback that can
    #    terminate the child, so a mistake there leaks a process per attempt
    #    instead of failing visibly.
    deadline = time.monotonic() + 30
    leaked: set[int] = set()
    while time.monotonic() < deadline:
        leaked = _child_pids() - children_before
        if not leaked:
            break
        time.sleep(0.2)
    assert not leaked, f"worker process(es) outlived the attempt: {sorted(leaked)}"


# ------------------------------------------------- fail-closed is preserved


def _state_with(root: Path, instance_id: str | None) -> None:
    """A persisted state naming which supervisor instance owns this program."""
    persist_state(
        root,
        ProgramStateRecord(
            program_id="p",
            program_digest="0" * 64,
            base_pin="0" * 40,
            supervisor_instance_id=instance_id,
            supervisor_pid=os.getpid(),
        ),
    )


def _intent(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "attempt_id": "a",
        "pid": os.getpid(),
        "identity_state": "PENDING",
        "supervisor_pid": os.getpid(),
        "supervisor_instance_id": "token-1",
        # This process really is the "launcher" in these tests, so its start
        # identity is the honest value to record.
        "supervisor_start_identity": process_start_identity(os.getpid()),
    }
    base.update(over)
    return base


def test_a_live_intent_from_the_running_supervisor_is_in_flight(
    tmp_path: Path,
) -> None:
    _state_with(tmp_path, "token-1")
    verdict, reason = _intent_liveness(_intent(), root=tmp_path)
    assert verdict is Liveness.IN_FLIGHT, reason


def test_an_orphaned_intent_is_unknown_not_in_flight(tmp_path: Path) -> None:
    """The safety property the whole design rests on.

    A live pid with no established identity is only trustworthy while the
    supervisor that launched it is still waiting for it. With that supervisor
    gone the pid could have been reused by a stranger, and the honest answer is
    UNKNOWN -- which routes to NEEDS_RECONCILIATION, exactly as before.
    """
    _state_with(tmp_path, "token-1")
    verdict, reason = _intent_liveness(
        _intent(supervisor_pid=2**31 - 2), root=tmp_path
    )
    assert verdict is Liveness.UNKNOWN, reason
    assert "reused" in reason


def test_a_different_supervisor_instance_is_unknown_not_in_flight(
    tmp_path: Path,
) -> None:
    """A LIVE supervisor from a later run must not inherit an older intent."""
    _state_with(tmp_path, "a-later-run")
    verdict, reason = _intent_liveness(_intent(), root=tmp_path)
    assert verdict is Liveness.UNKNOWN, reason
    assert "owns this program now" in reason


def test_a_stranger_on_the_dead_launchers_pid_is_unknown(tmp_path: Path) -> None:
    """The clean-room gate's attack on the first version of this record.

    1. Supervisor A mints token T and writes it into state.json.
    2. A records an intent naming its own pid and T.
    3. A is SIGKILLed. `state.supervisor_instance_id` is NEVER cleared on exit
       -- not by `_release`, and certainly not by a kill -- so state.json still
       holds T.
    4. The OS reuses A's pid for an unrelated process.
    5. An operator reconciles, which is the natural thing to do after a
       supervisor dies and happens BEFORE any new run mints a new token.

    Against the pid-plus-token version this returned IN_FLIGHT, and its reason
    string claimed the launcher was "still running and still waiting for it"
    while nothing was waiting. Both facts it checked came from storage the dead
    supervisor itself had written.

    The live re-derivation is what breaks the chain: a stranger holding that
    pid has a different start time, so the launcher's identity no longer
    matches and the answer degrades to UNKNOWN -- which routes to
    NEEDS_RECONCILIATION, the correct outcome for an orphan.
    """
    _state_with(tmp_path, "token-1")  # stale: A died without clearing it
    verdict, reason = _intent_liveness(
        _intent(supervisor_start_identity="linux:not-the-supervisor-that-launched-it"),
        root=tmp_path,
    )
    assert verdict is Liveness.UNKNOWN, reason
    assert "not the supervisor that launched it" in reason
    assert "orphaned" in reason


def test_an_intent_without_a_launcher_identity_is_unknown(tmp_path: Path) -> None:
    """Absence of the strong check is not permission to fall back to the weak
    one. A record written without a launcher start identity cannot rule out a
    reused launcher pid, so it proves nothing."""
    _state_with(tmp_path, "token-1")
    for missing in (None, "", "unknown"):
        verdict, reason = _intent_liveness(
            _intent(supervisor_start_identity=missing), root=tmp_path
        )
        assert verdict is Liveness.UNKNOWN, f"{missing!r}: {reason}"


def test_an_intent_with_no_token_recorded_is_unknown(tmp_path: Path) -> None:
    _state_with(tmp_path, "token-1")
    verdict, reason = _intent_liveness(
        _intent(supervisor_instance_id=None), root=tmp_path
    )
    assert verdict is Liveness.UNKNOWN, reason


def test_an_intent_with_no_state_at_all_is_unknown(tmp_path: Path) -> None:
    """Nothing to compare against is not permission to assume."""
    verdict, reason = _intent_liveness(_intent(), root=tmp_path)
    assert verdict is Liveness.UNKNOWN, reason


def test_a_dead_pid_in_an_intent_is_gone(tmp_path: Path) -> None:
    _state_with(tmp_path, "token-1")
    verdict, reason = _intent_liveness(_intent(pid=2**31 - 2), root=tmp_path)
    assert verdict is Liveness.GONE, reason


def test_an_intent_without_a_usable_pid_is_unknown(tmp_path: Path) -> None:
    _state_with(tmp_path, "token-1")
    verdict, reason = _intent_liveness(_intent(pid=0), root=tmp_path)
    assert verdict is Liveness.UNKNOWN, reason


def test_in_flight_is_its_own_state(tmp_path: Path) -> None:
    """IN_FLIGHT joins ALIVE at exactly one branch and nowhere else."""
    assert RecoveryAction.WORKER_STILL_RUNNING.value == "WORKER_STILL_RUNNING"
    assert Liveness.IN_FLIGHT is not Liveness.ALIVE
    assert Liveness.IN_FLIGHT is not Liveness.UNKNOWN


def test_a_bare_unidentified_pid_is_still_unknown() -> None:
    """The B1 contract is untouched: the new state comes from a launch INTENT,
    never from a bare pid whose identity happens to be missing."""
    verdict, _ = process_liveness(os.getpid(), None)
    assert verdict is Liveness.UNKNOWN


# ------------------------------------------------------------ cleanup


def test_clearing_a_launch_removes_the_intent_too(tmp_path: Path) -> None:
    """A stale intent names a pid the OS may reuse, exactly as a stale launch
    record does. Cleanup that dropped one and kept the other would leave the
    weaker record behind as the only survivor."""
    record_launch_intent(
        tmp_path,
        attempt_id="att-1",
        pid=os.getpid(),
        supervisor_pid=os.getpid(),
        supervisor_instance_id="i",
        supervisor_start_identity="linux:1",
    )
    assert load_launch_intent(tmp_path, "att-1") is not None
    clear_launch(tmp_path, "att-1")
    assert load_launch_intent(tmp_path, "att-1") is None


def _launch_files(state_root: Path, suffix: str) -> list[dict[str, object]]:
    """Every launch record of one kind currently on disk, parsed.

    Read by suffix rather than by attempt id so the test never has to reach
    into the supervisor to learn what it named things.
    """
    directory = launches_dir(state_root)
    if not directory.is_dir():
        return []
    out: list[dict[str, object]] = []
    for path in sorted(directory.iterdir()):
        if not path.name.endswith(suffix):
            continue
        if suffix == ".json" and path.name.endswith(".intent.json"):
            continue
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):  # pragma: no cover
            continue
    return out


def _child_pids() -> set[int]:
    """Direct children of this process, read from /proc.

    Deliberately NOT `pgrep`/`os.popen`: those spawn a child of their own, so
    the measurement appears in its own result and a second call returns a
    different shell's pid. That reads as a leak when nothing leaked -- which is
    exactly what it did here on the first run of this test.
    """
    if os.name == "nt":  # pragma: no cover - Linux measurement only
        return set()
    mine = os.getpid()
    found: set[int] = set()
    try:
        entries = os.listdir("/proc")
    except OSError:  # pragma: no cover
        return found
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            status = pathlib.Path(f"/proc/{entry}/status").read_text(encoding="utf-8")
        except OSError:
            continue  # it exited while we were looking; that is not a leak
        for line in status.splitlines():
            if line.startswith("PPid:"):
                if line.split()[1] == str(mine):
                    found.add(int(entry))
                break
    return found
