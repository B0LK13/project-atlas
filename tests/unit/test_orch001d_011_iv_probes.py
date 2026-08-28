"""ORCH001D-011 independent verification: reproducible probe evidence.

Checked-in versions of the ad-hoc probes run for the ORCH001D-011 IV pass
(see WORKLOG.md "ORCH001D-011"), added after review (PR #620) correctly
pointed out that prose summaries + a pass count are not reproducible
evidence. Split into:

- SAFE_LOCAL: pure functions (``build_launch_plan`` / ``resolve_cursor_transport``),
  zero subprocess.
- SAFE_ISOLATED: real (not mocked) ``SubprocessProcessRunner.run()`` calls
  using ``sys.executable`` as a benign stand-in for the Cursor CLI, so the
  actual process-spawn transport is exercised authentically without
  requiring a live Cursor CLI installation.

A second review pass on the same PR found a real gap in what "output
bounded" meant: the original ``SubprocessProcessRunner`` used
``subprocess.run(capture_output=True)``, which buffers a child's *complete*
stdout/stderr via ``Popen.communicate()`` before any cap is applied --
memory during collection was unbounded, only the returned value was
truncated. ``SubprocessProcessRunner`` was rewritten (same PR) to drain
stdout/stderr on dedicated threads with the cap enforced during collection
(draining past the cap without retaining it, so the child can never block
on a full pipe). The capture-bound regression tests below exercise that
rewrite directly, including the concurrent-large-streams case that is the
classic way a naive fix reintroduces a pipe deadlock.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from project_atlas.orchestration.agent_transport import (
    MAX_CAPTURED_BYTES,
    LauncherKind,
    ProcessRunRequest,
    ResolvedCursorExecutable,
    SubprocessProcessRunner,
    TransportError,
    build_launch_plan,
    resolve_cursor_transport,
)

_RESOLVED = ResolvedCursorExecutable(
    logical_name="agent", path="/usr/bin/agent", launcher_kind=LauncherKind.DIRECT
)


# --- SAFE_LOCAL: pure command-construction probes, zero subprocess -------


def test_oversized_prompt_rejected(tmp_path: Path) -> None:
    with pytest.raises(TransportError) as exc:
        build_launch_plan(_RESOLVED, "A" * 9000, cwd=tmp_path)
    assert exc.value.code == "PROMPT_REJECTED"


def test_nul_byte_in_prompt_rejected(tmp_path: Path) -> None:
    with pytest.raises(TransportError) as exc:
        build_launch_plan(_RESOLVED, "hello\x00world", cwd=tmp_path)
    assert exc.value.code == "PROMPT_REJECTED"


def test_empty_prompt_rejected(tmp_path: Path) -> None:
    with pytest.raises(TransportError) as exc:
        build_launch_plan(_RESOLVED, "", cwd=tmp_path)
    assert exc.value.code == "PROMPT_REJECTED"


def test_nonexistent_cwd_rejected(tmp_path: Path) -> None:
    with pytest.raises(TransportError) as exc:
        build_launch_plan(_RESOLVED, "valid prompt", cwd=tmp_path / "does" / "not" / "exist")
    assert exc.value.code == "WORKSPACE_UNSAFE"


def test_executable_path_traversal_rejected() -> None:
    with pytest.raises(TransportError) as exc:
        resolve_cursor_transport("../../../windows/system32/cmd.exe")
    assert exc.value.code == "EXECUTABLE_REJECTED"


def test_forbidden_flag_text_in_prompt_does_not_reach_argv(tmp_path: Path) -> None:
    """The prompt is stdin-only and never contributes to argv/flags, so text
    resembling a forbidden flag inside the prompt is not a live attack path
    (unlike an actual argv-level injection, which build_launch_plan does
    reject via its own explicit prompt-in-argv check). This is the probe
    that produced "no rejection" during the original IV pass; asserting the
    *reason* here (prompt absent from argv, flags are the fixed
    READ_ONLY_CURSOR_FLAGS constant) rather than just "no error" keeps this
    test meaningful instead of vacuous."""
    plan = build_launch_plan(_RESOLVED, "--force rm -rf /", cwd=tmp_path)
    assert "--force rm -rf /" not in plan.argv
    assert plan.stdin_payload == "--force rm -rf /"


# --- SAFE_ISOLATED: real (unmocked) subprocess transport probes ----------


def test_benign_roundtrip(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", "print('hello-from-isolated-probe')"),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.stdout.strip() == b"hello-from-isolated-probe"
    assert out.timed_out is False


def test_nonzero_exit_code_propagated(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", "import sys; sys.exit(7)"),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 7
    assert out.timed_out is False


def test_timeout_is_actually_enforced(tmp_path: Path) -> None:
    """A process that would sleep 5s is actually killed at ~timeout_seconds,
    not left running -- checked against real wall-clock time, not mocked."""
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", "import time; time.sleep(5)"),
        cwd=tmp_path,
        timeout_seconds=1,
        env={},
    )
    start = time.time()
    out = runner.run(req)
    elapsed = time.time() - start
    assert out.timed_out is True
    assert out.exit_code == 124
    assert elapsed < 3, f"expected the runner to kill the process at ~1s, took {elapsed:.1f}s"


def test_empty_argv_rejected_before_spawn(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    with pytest.raises(TransportError) as exc:
        runner.run(ProcessRunRequest(argv=(), cwd=tmp_path, timeout_seconds=10, env={}))
    assert exc.value.code == "ARGV_REJECTED"


def test_out_of_bounds_timeout_rejected_before_spawn(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    with pytest.raises(TransportError) as exc:
        runner.run(
            ProcessRunRequest(
                argv=(sys.executable, "-c", "print(1)"), cwd=tmp_path, timeout_seconds=0, env={}
            )
        )
    assert exc.value.code == "TIMEOUT_REJECTED"


def test_shell_metacharacters_are_never_interpreted(tmp_path: Path) -> None:
    """shell=False proof: an argv element containing shell metacharacters is
    received by the child as one literal argument, never split/chained by a
    shell. Demonstrated by having the child echo back its own argv[1]."""
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            "ignored; echo INJECTED",
        ),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.stdout.strip() == b"ignored; echo INJECTED"


# --- Remediation: captured output is bounded during collection, not just
# --- on the returned value (P2 finding on PR #620, fixed in the same PR) -


def test_large_stdout_is_bounded(tmp_path: Path) -> None:
    """Child writes several times MAX_CAPTURED_BYTES to stdout; the runner
    must still complete (drain-past-cap, never block the child) and return
    exactly MAX_CAPTURED_BYTES."""
    runner = SubprocessProcessRunner()
    over_cap = MAX_CAPTURED_BYTES * 5
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'x' * {over_cap}); sys.stdout.flush()",
        ),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.timed_out is False
    assert len(out.stdout) == MAX_CAPTURED_BYTES


def test_large_stderr_is_bounded(tmp_path: Path) -> None:
    """Same as stdout, on stderr -- the two streams are drained
    independently and neither one can starve the other."""
    runner = SubprocessProcessRunner()
    over_cap = MAX_CAPTURED_BYTES * 5
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            f"import sys; sys.stderr.buffer.write(b'e' * {over_cap}); sys.stderr.flush()",
        ),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.timed_out is False
    assert len(out.stderr) == MAX_CAPTURED_BYTES


def test_large_stdout_and_stderr_concurrently_do_not_deadlock(tmp_path: Path) -> None:
    """The classic subprocess trap: if only one stream is drained while the
    other's OS pipe buffer fills, the child blocks writing to the full pipe
    and the parent blocks waiting on the child -- a deadlock. Both streams
    here are large enough to fill a typical pipe buffer many times over;
    the process completing at all (not the exact byte counts) is the
    deadlock proof. A short timeout bounds the test if this regresses."""
    runner = SubprocessProcessRunner()
    over_cap = MAX_CAPTURED_BYTES * 5
    script = (
        "import sys\n"
        f"sys.stdout.buffer.write(b'x' * {over_cap})\n"
        "sys.stdout.flush()\n"
        f"sys.stderr.buffer.write(b'e' * {over_cap})\n"
        "sys.stderr.flush()\n"
    )
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.timed_out is False
    assert len(out.stdout) == MAX_CAPTURED_BYTES
    assert len(out.stderr) == MAX_CAPTURED_BYTES


def test_output_exactly_at_the_boundary_is_not_truncated(tmp_path: Path) -> None:
    """Writing exactly MAX_CAPTURED_BYTES must come back whole, unaltered."""
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'y' * {MAX_CAPTURED_BYTES}); sys.stdout.flush()",
        ),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert len(out.stdout) == MAX_CAPTURED_BYTES
    assert out.stdout == b"y" * MAX_CAPTURED_BYTES


def test_output_one_byte_over_boundary_is_truncated_by_exactly_one(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    over_by_one = MAX_CAPTURED_BYTES + 1
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'z' * {over_by_one}); sys.stdout.flush()",
        ),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert len(out.stdout) == MAX_CAPTURED_BYTES
    assert out.stdout == b"z" * MAX_CAPTURED_BYTES


def test_empty_output_roundtrips_as_empty(tmp_path: Path) -> None:
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.stdout == b""
    assert out.stderr == b""


def test_binary_non_utf8_output_is_returned_as_raw_bytes(tmp_path: Path) -> None:
    """The contract is raw bytes end to end (ProcessRunRequest/Outcome are
    typed ``bytes``, never ``str``) -- non-UTF-8 output must not raise a
    decode error or get mangled, since nothing here decodes it."""
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(bytes([0xFF, 0xFE, 0x00, 0x80, 0x81]))",
        ),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.stdout == bytes([0xFF, 0xFE, 0x00, 0x80, 0x81])


def test_nonzero_exit_with_oversized_output_reports_both_correctly(tmp_path: Path) -> None:
    """Bounding the capture must not interfere with exit-code propagation."""
    runner = SubprocessProcessRunner()
    over_cap = MAX_CAPTURED_BYTES * 3
    req = ProcessRunRequest(
        argv=(
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'x' * {over_cap}); sys.exit(9)",
        ),
        cwd=tmp_path,
        timeout_seconds=15,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 9
    assert out.timed_out is False
    assert len(out.stdout) == MAX_CAPTURED_BYTES


def test_timeout_preserves_output_already_produced_before_the_kill(tmp_path: Path) -> None:
    """A process that writes output, then hangs, is killed at the timeout --
    but whatever it already wrote (and the reader threads already drained)
    is still returned, not discarded."""
    runner = SubprocessProcessRunner()
    script = (
        "import sys, time\n"
        "sys.stdout.buffer.write(b'produced-before-hang')\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n"
    )
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=1,
        env={},
    )
    start = time.time()
    out = runner.run(req)
    elapsed = time.time() - start
    assert out.timed_out is True
    assert out.exit_code == 124
    assert out.stdout == b"produced-before-hang"
    assert elapsed < 5, f"expected kill at ~1s, took {elapsed:.1f}s"


def test_normal_small_output_is_unchanged_by_the_bounded_drain(tmp_path: Path) -> None:
    """The common case (small, well-under-cap output) must behave exactly
    as before the fix -- this is effectively test_benign_roundtrip again,
    kept here to sit alongside the rest of the capture-bound regression
    set as one readable group."""
    runner = SubprocessProcessRunner()
    req = ProcessRunRequest(
        argv=(sys.executable, "-c", "print('small and ordinary')"),
        cwd=tmp_path,
        timeout_seconds=10,
        env={},
    )
    out = runner.run(req)
    assert out.exit_code == 0
    assert out.stdout.strip() == b"small and ordinary"
    assert len(out.stdout) < MAX_CAPTURED_BYTES
