"""The child environment must be correct on the platform the child runs on.

``BASE_ENV_NAMES`` was a POSIX-only list. On Windows a worker was therefore
handed ``PATH`` and ``HOME`` and nothing else -- no ``SystemRoot``, no
``TEMP``/``TMP``, no ``USERPROFILE``. That is not a conservative default there,
it is a broken one:

  * ``sdk.host.pid_is_alive`` runs ``tasklist`` and
    ``sdk.host.process_start_identity`` runs ``powershell``; neither starts
    without ``SystemRoot``. A liveness probe that cannot run answers UNKNOWN,
    and ``recovery.classify_attempt`` turns UNKNOWN into NEEDS_RECONCILIATION
    -- for a worker that is in fact running.
  * ``ntpath.expanduser`` reads ``USERPROFILE`` and ignores ``HOME``, so
    ``Path.home()`` raises in a child given only ``HOME``.

The repository had already solved this once:
``local_process_transport.DEFAULT_ENV_ALLOWLIST`` names ``SystemRoot``,
``TEMP``, ``TMP`` and ``USERPROFILE``, and ``_build_env`` case-folds on ``nt``
under an IV finding from PR #661. This package re-implemented the idea later
and kept only the POSIX half of it.

These tests drive BOTH platform branches from either host. That is the whole
point: the defect survived because the only runner that could observe it was
Windows, and the jobs that gate merges -- ruff, mypy, the covered suite -- all
run on Linux.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program.adapters.base import (
    COMMON_BASE_ENV_NAMES,
    WINDOWS_BASE_ENV_NAMES,
    base_env_names,
    build_child_env,
)
from project_atlas.orchestration.program.profiles import AgentProfile

PROBE_WORKER = Path(__file__).with_name("_child_env_probe_worker.py")

#: How a windows-latest runner's environment actually presents. ``os.environ``
#: upper-cases every key on ``nt`` (``os.py``: ``encodekey = str.upper``), so
#: these are the names a real lookup has to survive.
WINDOWS_RUNNER_ENV: dict[str, str] = {
    "PATH": r"C:\Windows\system32;C:\Windows",
    "SYSTEMROOT": r"C:\Windows",
    "WINDIR": r"C:\Windows",
    "SYSTEMDRIVE": "C:",
    "COMSPEC": r"C:\Windows\system32\cmd.exe",
    "PATHEXT": ".COM;.EXE;.BAT;.CMD",
    "TEMP": r"C:\Users\runneradmin\AppData\Local\Temp",
    "TMP": r"C:\Users\runneradmin\AppData\Local\Temp",
    "USERPROFILE": r"C:\Users\runneradmin",
    "HOMEDRIVE": "C:",
    "HOMEPATH": r"\Users\runneradmin",
    "APPDATA": r"C:\Users\runneradmin\AppData\Roaming",
    "LOCALAPPDATA": r"C:\Users\runneradmin\AppData\Local",
    "PROGRAMDATA": r"C:\ProgramData",
    "NUMBER_OF_PROCESSORS": "4",
    "PROCESSOR_ARCHITECTURE": "AMD64",
    "HOME": r"C:\Users\runneradmin",
}

POSIX_RUNNER_ENV: dict[str, str] = {
    "PATH": "/usr/local/bin:/usr/bin",
    "HOME": "/home/runner",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TZ": "UTC",
    "TMPDIR": "/tmp",
}


def _profile(**overrides: Any) -> AgentProfile:
    payload: dict[str, Any] = {
        "profile_id": "impl",
        "agent_id": "impl",
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "adapter_options": {"argv": ["/bin/true"]},
    }
    payload.update(overrides)
    return AgentProfile.model_validate(payload)


# --------------------------------------------------------------- name sets


def test_the_windows_set_is_the_posix_set_plus_windows_names() -> None:
    """Purely additive, so no platform can lose a name it already had."""
    posix = base_env_names("posix")
    windows = base_env_names("nt")
    assert posix == COMMON_BASE_ENV_NAMES
    assert set(posix) < set(windows)
    assert set(windows) - set(posix) == set(WINDOWS_BASE_ENV_NAMES)


def test_no_always_forwarded_name_is_credential_shaped() -> None:
    """The allow-list rule is unchanged: nothing secret is forwarded by default."""
    for name in base_env_names("nt") + base_env_names("posix"):
        upper = name.upper()
        assert not any(
            marker in upper
            for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")
        ), f"{name} is forwarded to every child without being allow-listed"


# ------------------------------------------------------------------ Windows


def test_windows_child_receives_what_windows_needs_to_start() -> None:
    """The regression itself: these were all dropped on windows-latest."""
    env = build_child_env(_profile(), parent=WINDOWS_RUNNER_ENV, os_name="nt")
    for required in (
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "PATHEXT",
        "COMSPEC",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
    ):
        assert required in env, f"{required} is missing from the Windows child env"
    assert env["SYSTEMROOT"] == r"C:\Windows"


def test_windows_matching_is_case_insensitive_and_keeps_the_source_casing() -> None:
    """Windows resolves names case-insensitively; an exact lookup drops them.

    ``os.environ`` normalises to upper case, but a mapping handed in as
    ``parent`` carries whatever casing its producer used -- the PR #661 IV
    finding, in this module.
    """
    native = {
        "Path": r"C:\Windows\system32",
        "SystemRoot": r"C:\Windows",
        "ComSpec": r"C:\Windows\system32\cmd.exe",
        "Temp": r"C:\Temp",
    }
    env = build_child_env(_profile(), parent=native, os_name="nt")
    assert env == native, "a name present under different casing was dropped"


def test_windows_absent_names_are_simply_absent() -> None:
    """A name the platform does not set is skipped, never invented or raised."""
    partial = {"PATH": r"C:\Windows\system32", "SYSTEMROOT": r"C:\Windows"}
    env = build_child_env(_profile(), parent=partial, os_name="nt")
    assert env == partial
    assert "USERPROFILE" not in env and "TEMP" not in env


# -------------------------------------------------------------------- POSIX


def test_posix_child_env_is_byte_identical_to_before_the_repair() -> None:
    """The Windows repair must not change POSIX behaviour at all."""
    env = build_child_env(_profile(), parent=POSIX_RUNNER_ENV, os_name="posix")
    assert env == POSIX_RUNNER_ENV


def test_posix_matching_stays_case_sensitive() -> None:
    """POSIX names are genuinely distinct; folding would conflate two variables."""
    env = build_child_env(
        _profile(), parent={"path": "/usr/bin", "Home": "/home/x"}, os_name="posix"
    )
    assert env == {}


def test_posix_child_never_receives_the_windows_names() -> None:
    mixed = dict(POSIX_RUNNER_ENV)
    mixed["SYSTEMROOT"] = r"C:\Windows"
    env = build_child_env(_profile(), parent=mixed, os_name="posix")
    assert "SYSTEMROOT" not in env


# ------------------------------------------- allowed / unexpected / empty


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_allow_listed_names_are_forwarded_on_both_platforms(os_name: str) -> None:
    parent = dict(WINDOWS_RUNNER_ENV if os_name == "nt" else POSIX_RUNNER_ENV)
    parent["ATLAS_FIXTURE_MODE"] = "write"
    env = build_child_env(
        _profile(env_allowlist=["ATLAS_FIXTURE_MODE"]), parent=parent, os_name=os_name
    )
    assert env["ATLAS_FIXTURE_MODE"] == "write"


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_an_allow_listed_name_that_is_not_set_is_not_invented(os_name: str) -> None:
    parent = dict(WINDOWS_RUNNER_ENV if os_name == "nt" else POSIX_RUNNER_ENV)
    env = build_child_env(
        _profile(env_allowlist=["ATLAS_FIXTURE_MODE"]), parent=parent, os_name=os_name
    )
    assert "ATLAS_FIXTURE_MODE" not in env


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_unexpected_names_are_never_forwarded(os_name: str) -> None:
    """Including credential-shaped ones. This is the property the repair keeps."""
    parent = dict(WINDOWS_RUNNER_ENV if os_name == "nt" else POSIX_RUNNER_ENV)
    parent["ANTHROPIC_API_KEY"] = "sk-should-not-be-forwarded"
    parent["SOME_UNRELATED_VAR"] = "leak"
    env = build_child_env(_profile(), parent=parent, os_name=os_name)
    assert "ANTHROPIC_API_KEY" not in env
    assert "SOME_UNRELATED_VAR" not in env


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_an_empty_environment_yields_an_empty_child_environment(os_name: str) -> None:
    env = build_child_env(
        _profile(env_allowlist=["ATLAS_FIXTURE_MODE"]), parent={}, os_name=os_name
    )
    assert env == {}


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_extras_are_applied_over_an_empty_environment(os_name: str) -> None:
    """``extra`` is the supervisor's own, not inherited, so it is unconditional."""
    env = build_child_env(
        _profile(), parent={}, extra={"ATLAS_PROGRAM_TASK": "t1"}, os_name=os_name
    )
    assert env == {"ATLAS_PROGRAM_TASK": "t1"}


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_a_partial_environment_forwards_only_what_is_there(os_name: str) -> None:
    env = build_child_env(_profile(), parent={"PATH": "/usr/bin"}, os_name=os_name)
    assert env == {"PATH": "/usr/bin"}


@pytest.mark.parametrize("os_name", ["nt", "posix"])
def test_extra_overrides_an_inherited_value(os_name: str) -> None:
    parent = {"PATH": "/inherited"}
    env = build_child_env(
        _profile(), parent=parent, extra={"PATH": "/explicit"}, os_name=os_name
    )
    assert env["PATH"] == "/explicit"


# ------------------------------------------------- the real child, this host


def test_a_real_child_can_do_the_work_the_fixture_workers_do(tmp_path: Path) -> None:
    """End-to-end on whichever platform this is, through the real env builder.

    The G2 and G3 fixture workers fail silently when their environment is
    inadequate -- one skips its pause, the other writes no report -- and the
    resulting test failure names the symptom, not the cause. That is why one
    windows-latest run produced no usable diagnosis. This worker reports every
    step, so a failure here says which one broke and why.
    """
    out = tmp_path / "probe.json"
    profile = _profile(env_allowlist=["ATLAS_ENVPROBE_OUT"])
    env = build_child_env(profile, extra={"ATLAS_ENVPROBE_OUT": str(out)})

    completed = subprocess.run(
        [sys.executable, str(PROBE_WORKER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert out.is_file(), (
        "the child wrote no report at all; it could not start or could not "
        f"import. exit={completed.returncode}\nstderr:\n{completed.stderr}"
    )
    report = json.loads(out.read_text(encoding="utf-8"))

    for name in base_env_names(os.name):
        if name in os.environ:
            assert name in report["env_names"], (
                f"{name} is set in this process but never reached the child"
            )

    steps = report["steps"]
    for step in (
        "import_control",
        "gettempdir",
        "path_home",
        "pid_is_alive_self",
        "process_start_identity_self",
    ):
        assert steps[step]["ok"], (
            f"the child could not complete {step} on {report['os_name']}:\n"
            f"{steps[step].get('traceback')}"
        )

    assert steps["pid_is_alive_self"]["value"] is True, (
        "the child could not observe its own process as running. On Windows "
        "this is tasklist failing, which makes every in-flight attempt look "
        "GONE to the recovery contract"
    )
    assert steps["process_start_identity_self"]["value"] != "unknown", (
        "the child could not establish a process start identity. On Windows "
        "this is powershell failing, which makes a running worker report "
        "UNKNOWN and therefore NEEDS_RECONCILIATION"
    )
