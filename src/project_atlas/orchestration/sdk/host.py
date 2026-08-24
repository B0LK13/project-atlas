"""Detached Windows/Linux supervisor host. No secrets, no elevation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, SdkRuntimeError

SUPERVISOR_STOP_NAME = "supervisor.stop"
SUPERVISOR_LOCK_NAME = "supervisor.lock"


def host_state_dir(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE


def write_host_identity(
    root: Path,
    *,
    pid: int,
    backend: str,
    package_head: str,
    worktree: str,
) -> Path:
    store = host_state_dir(root)
    store.mkdir(parents=True, exist_ok=True)
    payload = {
        "supervisor_pid": pid,
        "supervisor_backend": backend,
        "supervisor_package_head": package_head,
        "supervisor_worktree": worktree,
        "supervisor_command": "atlas orchestrator governor-service-run",
        "merge_authorized": False,
        "execution_authorized": False,
    }
    target = store / "supervisor-host.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (store / "supervisor.pid").write_text(f"{pid}\n", encoding="utf-8")
    return target


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in (proc.stdout or "")
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def detach_governor_service(
    *,
    root: Path,
    python: str | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Start governor-service-run in a new process group and return its PID."""
    interpreter = python or sys.executable
    args = [
        interpreter,
        "-m",
        "project_atlas.cli",
        "orchestrator",
        "governor-service-run",
        "--root",
        str(root),
        *(extra_args or []),
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(
            getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    log_dir = host_state_dir(root)
    log_dir.mkdir(parents=True, exist_ok=True)
    log = (log_dir / "supervisor.stdout.log").open("a", encoding="utf-8")
    proc = subprocess.Popen(
        args,
        cwd=str(root),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=(os.name != "nt"),
    )
    return int(proc.pid)


def stop_requested(root: Path) -> bool:
    return (host_state_dir(root) / SUPERVISOR_STOP_NAME).is_file()


def request_supervisor_stop(root: Path) -> None:
    path = host_state_dir(root) / SUPERVISOR_STOP_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stop\n", encoding="utf-8")


def clear_supervisor_stop(root: Path) -> None:
    path = host_state_dir(root) / SUPERVISOR_STOP_NAME
    if path.is_file():
        path.unlink()


def read_supervisor_lock_pid(root: Path) -> int:
    path = host_state_dir(root) / SUPERVISOR_LOCK_NAME
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        other = int(data.get("pid", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0
    if other > 0 and pid_is_alive(other):
        return other
    return 0


def acquire_supervisor_lock(root: Path) -> bool:
    """Fail closed when another live supervisor already owns the host lock."""
    path = host_state_dir(root) / SUPERVISOR_LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    me = os.getpid()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            other = int(data.get("pid", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            other = 0
        if other > 0 and other != me and pid_is_alive(other):
            return False
    path.write_text(json.dumps({"pid": me}, indent=2) + "\n", encoding="utf-8")
    return True


def release_supervisor_lock(root: Path) -> None:
    path = host_state_dir(root) / SUPERVISOR_LOCK_NAME
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("pid", 0)) != os.getpid():
            return
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return
    path.unlink()


def assert_single_supervisor_or_raise(root: Path) -> None:
    if not acquire_supervisor_lock(root):
        raise SdkRuntimeError(
            "another live supervisor already owns this host",
            code="SERVICE_DOUBLE_START",
        )
