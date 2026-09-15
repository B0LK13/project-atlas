"""Machine-readable Atlas agent diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_control import preflight, skill_compiler, skill_loader, vault_identity


def run(*, project_root: Path, vault_root: Path | None, agent_type: str, skill_root: Path, generated_root: Path) -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        skill = skill_loader.load(skill_root)
        checks["canonical_skill"] = "PASS"
        checks["skill_hash"] = "PASS"
        checks["adapters"] = "PASS" if not skill_compiler.verify(skill, generated_root) else "FAIL"
    except (OSError, ValueError):
        checks["canonical_skill"] = "FAIL"
        checks["skill_hash"] = "FAIL"
        checks["adapters"] = "FAIL"
    try:
        preflight.run(project_root=project_root, vault_root=vault_root, agent_type=agent_type, agent_value=None, skill_root=skill_root)
        checks["project_configuration"] = "PASS"
        checks["vault_identity"] = "PASS"
        checks["spool"] = "PASS"
    except (OSError, ValueError):
        checks["project_configuration"] = "FAIL"
        checks["vault_identity"] = "FAIL"
        checks["spool"] = "FAIL"
    return {"ok": all(value == "PASS" for value in checks.values()), "checks": checks}
