"""Managed-session postflight validation.

Canonical path: ``session.load`` → ``receipt_gate.validate`` → ``receipt_gate.issue``.
Sibling ``agent_control.postflight`` and the dispatcher both call ``run``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.agent_control import receipt_gate, session


def run(root: Path, session_id: str) -> dict[str, Any]:
    state = session.load(root, session_id)
    errors = receipt_gate.validate(state)
    if errors:
        return {"ok": False, "status": "incomplete", "session_id": session_id, "errors": errors}
    receipt = receipt_gate.issue(root, state)
    return {"ok": True, "status": "complete", "session_id": session_id, "receipt": receipt}
