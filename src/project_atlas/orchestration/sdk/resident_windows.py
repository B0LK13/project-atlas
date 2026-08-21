"""Windows resident host — Scheduled Task + detached process group.

Least privilege. No secrets on the command line. No elevation required for
user-level tasks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

from project_atlas.orchestration.sdk.host import host_state_dir, pid_is_alive, write_host_identity
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE

TASK_NAME: Final[str] = "AtlasAtlasGovernorResident"
WRAPPER_NAME: Final[str] = "atlas-resident-driver.cmd"


def write_resident_wrapper(
    *,
    root: Path,
    package_src: Path,
    python: str | None = None,
) -> Path:
    """Write a .cmd launcher that sets PYTHONPATH and runs the resident loop."""
    interpreter = python or sys.executable
    runtime = root / STATE_DIR_RELATIVE
    runtime.mkdir(parents=True, exist_ok=True)
    wrapper = runtime / WRAPPER_NAME
    # Use short env inheritance; never embed secrets.
    body = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "PYTHONPATH={package_src};%PYTHONPATH%"\r\n'
        f'"{interpreter}" -m project_atlas.cli orchestrator governor-resident-run '
        f'--root "{root}" --detached-worker\r\n'
        "endlocal\r\n"
    )
    wrapper.write_text(body, encoding="utf-8")
    return wrapper


def detach_resident_driver(
    *,
    root: Path,
    package_src: Path,
    python: str | None = None,
) -> int:
    """Start resident loop in a new Windows process group. Returns PID."""
    interpreter = python or sys.executable
    args = [
        interpreter,
        "-m",
        "project_atlas.cli",
        "orchestrator",
        "governor-resident-run",
        "--root",
        str(root),
        "--detached-worker",
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(
            getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    log_dir = host_state_dir(root)
    log_dir.mkdir(parents=True, exist_ok=True)
    log = (log_dir / "resident-driver.stdout.log").open("a", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(package_src) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    proc = subprocess.Popen(
        args,
        cwd=str(root),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=(os.name != "nt"),
        env=env,
    )
    write_host_identity(
        root,
        pid=int(proc.pid),
        backend="RESIDENT_SELF_WAKE",
        package_head="AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001",
        worktree=str(package_src.parent.parent if package_src.name == "src" else package_src),
    )
    return int(proc.pid)


def register_windows_logon_task(
    *,
    root: Path,
    package_src: Path,
    python: str | None = None,
    task_name: str = TASK_NAME,
) -> dict[str, object]:
    """Register a current-user logon task for bounded restart. No elevation."""
    if os.name != "nt":
        return {"registered": False, "reason": "not_windows"}
    wrapper = write_resident_wrapper(root=root, package_src=package_src, python=python)
    # /SC ONLOGON keeps user env (gh auth, CURSOR_API_KEY) without printing secrets.
    create = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            task_name,
            "/TR",
            str(wrapper),
            "/SC",
            "ONLOGON",
            "/RL",
            "LIMITED",
            "/F",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = {
        "registered": create.returncode == 0,
        "task_name": task_name,
        "wrapper": str(wrapper),
        "exit_code": create.returncode,
        "stdout_tail": (create.stdout or "")[-400:],
        "stderr_tail": (create.stderr or "")[-400:],
        "merge_authorized": False,
    }
    path = root / STATE_DIR_RELATIVE / "resident-windows-task.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def resident_pid_alive(root: Path) -> bool:
    pid_path = host_state_dir(root) / "supervisor.pid"
    if not pid_path.is_file():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return pid_is_alive(pid)
