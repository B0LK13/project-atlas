"""Shared Atlas 3 contracts, honesty stamps, and atomic helpers.

D-191 / D-192 / D-193. Isolated namespace. No wall-clock in generated content.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Final

from atlas_contracts.identity import safe_relative_component

ATLAS3_NAMESPACE: Final[str] = "project_atlas.atlas3"
GENERATOR_ID: Final[str] = "atlas-3-isolated-runtime-001"
OPS_RELATIVE: Final[Path] = Path("generated") / "ops" / "atlas3"
FULL_LIVE_DEMO_READY: Final[bool] = False
MERGE_AUTHORIZATION: Final[str] = "NOT_GRANTED"
TRUTH_BOUNDARY: Final[str] = (
    "MODEL OUTPUT != AUTHORITY / CONVERSATION != TRUTH CORE / "
    "GRAPH != AUTHORITY / UI != CANONICAL TRUTH / "
    "CAPTURE != CANONICAL FACT / PROOF != MODEL CLAIM / "
    "FULL_LIVE_DEMO_READY = NO / MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY: Final[dict[str, object]] = {
    "full_live_demo_ready": False,
    "authentic_pilot": False,
    "demo_is_release": False,
    "ui_is_canonical_truth": False,
    "model_output_is_authority": False,
    "conversation_is_authority": False,
    "graph_is_authority": False,
    "capture_is_canonical_fact": False,
    "promoted_to_truth_core": False,
    "merge_authorization": MERGE_AUTHORIZATION,
    "lens_is_authority": False,
}

ITEM_TYPES: Final[frozenset[str]] = frozenset(
    {
        "session_note",
        "idea",
        "observation",
        "research_finding",
        "action_item",
        "open_question",
        "proposed_decision",
        "confirmed_owner_decision",
        "claim_candidate",
        "constraint",
        "lesson_learned",
        "failed_approach",
        "next_step",
    }
)


class Atlas3Error(ValueError):
    """Fail-closed Atlas 3 error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def honesty_block() -> dict[str, object]:
    return dict(HONESTY)


def safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise Atlas3Error("UNSAFE_PROJECT_ID", str(exc)) from exc


def require_vault(vault: Path | str) -> Path:
    resolved = Path(vault).expanduser().resolve()
    if not resolved.is_dir():
        raise Atlas3Error("VAULT_NOT_FOUND", f"vault is not a directory: {resolved}")
    return resolved


def require_project(vault: Path, project_id: str) -> str:
    pid = safe_project_id(project_id)
    path = vault / "projects" / pid
    if not path.is_dir():
        raise Atlas3Error("UNKNOWN_PROJECT", f"project {pid!r} is not in the vault")
    return pid


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def assert_no_symlink_components(
    root: Path, relative: Path, *, code: str = "PROOF_LOCATOR_UNSAFE"
) -> None:
    """Refuse if any component of ``relative`` below ``root`` is a symlink or a
    Windows junction, checked with ``lstat`` on the *unresolved* path before
    any ``resolve()``. Shared by proof v2 and observation receipts (AT3-103 /
    ULT-01b-1)."""
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise Atlas3Error(code, f"path component {part!r} is a symlink or junction")


def write_locator_json(
    root: Path,
    locator: Path,
    payload: dict[str, Any],
    *,
    namespace: Path,
    identity_field: str,
    identity_value: str,
    code_unsafe: str = "PROOF_LOCATOR_UNSAFE",
    code_collision: str = "PROOF_LOCATOR_COLLISION",
    code_escape: str = "UNSAFE_TASK_ID",
) -> Path:
    """Write ``payload`` at ``root / locator`` under the shared locator rules.

    ``locator`` is a relative path whose parent names a task/project directory
    and whose final component is ``<digest16>.json``: the file name is a
    locator only, ``payload[identity_field]`` is the identity. ``namespace`` is
    the fixed relative root the locator must stay under (``proof/v2``,
    ``observation/v1``). Every component is symlink/junction-checked
    unresolved; the parent must be a directory (or absent); the target must be
    absent or a regular file; the resolved target must stay under the
    resolved ``root / namespace``; and an existing target holding a different
    ``identity_field`` value (or unreadable) fails closed instead of being
    overwritten.
    """
    assert_no_symlink_components(root, locator, code=code_unsafe)
    parent = root / locator.parent
    if parent.exists() and not parent.is_dir():
        raise Atlas3Error(code_unsafe, "locator parent path is not a directory")
    target = root / locator
    if target.exists() and not target.is_file():
        raise Atlas3Error(code_unsafe, "locator is not a regular file")
    if not target.resolve().is_relative_to((root / namespace).resolve()):
        raise Atlas3Error(code_escape, "locator path escaped its namespace")
    if target.is_file():
        existing = read_json(target)
        if existing is None or existing.get(identity_field) != identity_value:
            raise Atlas3Error(
                code_collision,
                "locator already holds a different or unreadable record; not overwritten",
            )
    write_json_atomic(target, payload)
    return target


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_answer(vault: Path, answer_id: str) -> dict[str, Any] | None:
    return read_json(vault / "generated" / "answers" / f"{answer_id}.json")
