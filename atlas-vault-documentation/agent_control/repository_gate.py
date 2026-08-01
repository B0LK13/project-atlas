"""Deterministic repository change-to-receipt enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_control import protected_paths


def validate(*, project_id: str, changed_files: list[str], receipt_path: Path | None, skill_sha256: str | None = None) -> dict[str, Any]:
    protected = sorted(path for path in changed_files if protected_paths.is_protected(path))
    errors: list[str] = []
    receipt: dict[str, Any] | None = None
    if protected:
        errors.append("direct protected-path changes are not authorized")
    meaningful = bool(changed_files)
    if meaningful and receipt_path is None:
        errors.append("meaningful changes require an Atlas session receipt")
    if receipt_path is not None:
        if not receipt_path.is_file():
            errors.append("receipt is missing")
        else:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("session", {}).get("project_id") != project_id:
                errors.append("receipt belongs to another project")
            if skill_sha256 and receipt.get("skill", {}).get("sha256") != skill_sha256:
                errors.append("receipt uses an obsolete skill hash")
            if not receipt.get("events", {}).get("validation"):
                errors.append("receipt lacks validation evidence")
            if not receipt.get("events", {}).get("completion"):
                errors.append("receipt lacks completion evidence")
    return {"ok": not errors, "project_id": project_id, "changed_files": changed_files, "protected_files": protected, "receipt_id": receipt.get("receipt_id") if receipt else None, "errors": errors}
