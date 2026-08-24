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
_LOCK_ACQUIRE_ATTEMPTS = 8


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


def _write_atomic_text(path: Path, content: str) -> None:
    """Replace ``path`` atomically via same-directory temp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def request_supervisor_stop(root: Path) -> None:
    path = host_state_dir(root) / SUPERVISOR_STOP_NAME
    _write_atomic_text(path, "stop\n")


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


def _lock_payload(pid: int) -> bytes:
    return (json.dumps({"pid": pid}, indent=2) + "\n").encode("utf-8")


def _read_lock_holder_pid(path: Path) -> int | None:
    """Return holder pid, None when absent, -1 when corrupt/unreadable."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("pid", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return -1


def acquire_supervisor_lock(root: Path) -> bool:
    """Fail closed when another live supervisor already owns the host lock."""
    path = host_state_dir(root) / SUPERVISOR_LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    me = os.getpid()
    payload = _lock_payload(me)
    for _attempt in range(_LOCK_ACQUIRE_ATTEMPTS):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = _read_lock_holder_pid(path)
            if holder is None:
                continue
            if holder == -1:
                return False
            if holder > 0 and holder != me and pid_is_alive(holder):
                return False
            if holder == me:
                return True
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return False
            continue
        except OSError:
            return False
        try:
            os.write(fd, payload)
            return True
        finally:
            os.close(fd)
    return False


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
