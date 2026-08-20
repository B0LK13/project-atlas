"""Least-privilege durable-host install renderers. No embedded secrets.

Windows Task Scheduler task name: ProjectAtlasGovernor
Linux: systemd --user unit project-atlas-governor.service

Neither renderer writes CURSOR_API_KEY, passwords, or receipts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

TASK_NAME: Final[str] = "ProjectAtlasGovernor"
SYSTEMD_UNIT_NAME: Final[str] = "project-atlas-governor.service"


def render_systemd_user_unit(*, root: Path, atlas_bin: str) -> str:
    working = root.resolve()
    return (
        "[Unit]\n"
        "Description=Project Atlas durable governor (AS-ORCH-CONTINUATION-BROKER-001)\n"
        "After=default.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={working}\n"
        f"ExecStart={atlas_bin} orchestrator governor-service-run --root {working}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "KillMode=process\n"
        "# Secrets stay in the user environment. Do not embed API keys here.\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def render_windows_schtasks_command(*, root: Path, atlas_bin: str) -> str:
    working = root.resolve()
    command = f'"{atlas_bin}" orchestrator governor-service-run --root "{working}"'
    return (
        f'schtasks /Create /TN "{TASK_NAME}" /SC ONLOGON /RL LIMITED /F '
        f'/TR {command} /NP'
    )


def write_linux_unit(*, output: Path, root: Path, atlas_bin: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_systemd_user_unit(root=root, atlas_bin=atlas_bin), encoding="utf-8")
    return output
