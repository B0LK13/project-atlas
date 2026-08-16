"""Import boundary for sibling control-plane APIs that remain in-tree.

``bootstrap``, ``preflight``, and ``event_client`` stay in
``atlas-vault-documentation/agent_control``. This module makes those exact
implementations callable from the installed Core package without copying them.

Receipt validate/issue are not loaded from here; they live in
``project_atlas.agent_control.receipt_gate``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast


class ControlPlaneError(RuntimeError):
    """Canonical control plane is unavailable or failed closed."""

    code: str = "CONTROL_PLANE_UNAVAILABLE"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def package_repo_root() -> Path:
    """Repository root when Core is imported from a src checkout."""
    return Path(__file__).resolve().parents[3]


def control_plane_root() -> Path:
    root = package_repo_root() / "atlas-vault-documentation"
    if not root.is_dir():
        raise ControlPlaneError(
            "canonical control plane tree is not available",
            code="CONTROL_PLANE_UNAVAILABLE",
        )
    return root


def ensure_control_plane_importable() -> Path:
    sibling = control_plane_root()
    sibling_str = str(sibling)
    if sibling_str not in sys.path:
        sys.path.insert(0, sibling_str)
    return sibling


def documentation_skill_root() -> Path:
    configured = os.environ.get("ATLAS_SKILL_ROOT")
    if configured:
        path = Path(configured)
        if (path / "SKILL.md").is_file():
            return path
        raise ControlPlaneError("ATLAS_SKILL_ROOT is not a skill root", code="PREFLIGHT_FAILED")
    candidate = control_plane_root() / "skill"
    if (candidate / "SKILL.md").is_file():
        return candidate
    raise ControlPlaneError("canonical documentation skill is missing", code="PREFLIGHT_FAILED")


def resolve_mda_command() -> Path:
    configured = os.environ.get("ATLAS_MDA_COMMAND")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        raise ControlPlaneError(
            "ATLAS_MDA_COMMAND does not point at an executable",
            code="PIPELINE_UNAVAILABLE",
        )
    fixture = control_plane_root() / "tests" / "fixtures" / "bin" / "mda"
    if fixture.is_file():
        return fixture
    raise ControlPlaneError(
        "canonical event pipeline MDA is unavailable",
        code="PIPELINE_UNAVAILABLE",
    )


def prepare_event_pipeline() -> Path:
    """Require the real capture→normalize→verify→route MDA before events."""
    mda = resolve_mda_command()
    os.environ["ATLAS_MDA_COMMAND"] = str(mda)
    return mda


def bootstrap_start(
    *,
    project_root: Path,
    vault_root: Path | None,
    agent_type: str,
    agent_value: str | None,
    task_id: str,
    skill_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    ensure_control_plane_importable()
    from agent_control.bootstrap import start

    return cast(
        tuple[dict[str, Any], dict[str, str]],
        start(
            project_root=project_root,
            vault_root=vault_root,
            agent_type=agent_type,
            agent_value=agent_value,
            task_id=task_id,
            skill_root=skill_root,
        ),
    )


def run_preflight(
    *,
    project_root: Path,
    vault_root: Path | None,
    agent_type: str,
    agent_value: str | None,
    skill_root: Path,
) -> dict[str, Any]:
    ensure_control_plane_importable()
    from agent_control.preflight import run

    return cast(
        dict[str, Any],
        run(
            project_root=project_root,
            vault_root=vault_root,
            agent_type=agent_type,
            agent_value=agent_value,
            skill_root=skill_root,
        ),
    )


def document_event(
    *,
    vault_root: Path,
    session_id: str,
    event_type: str,
    summary: str,
    work_package: str | None = None,
    validation: list[str] | None = None,
    decision: list[str] | None = None,
    changed_files: list[str] | None = None,
    spool: bool = False,
) -> dict[str, Any]:
    ensure_control_plane_importable()
    from agent_control.event_client import document

    return cast(
        dict[str, Any],
        document(
            vault_root=vault_root,
            session_id=session_id,
            event_type=event_type,
            summary=summary,
            work_package=work_package,
            validation=validation,
            decision=decision,
            changed_files=changed_files,
            spool=spool,
        ),
    )
