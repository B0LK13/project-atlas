"""Fail-closed adapter rehearsal readiness registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def check(path: Path | None, adapter_id: str, skill_version: str, skill_sha256: str) -> dict[str, Any]:
    if path is None:
        return {"status": "not-configured", "authorized": True, "reason": "legacy or local fixture mode"}
    if not path.is_file():
        return {"status": "missing", "authorized": False, "reason": "readiness registry is missing"}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry = data.get("adapters", {}).get(adapter_id) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        return {"status": "unknown", "authorized": False, "reason": "adapter is not registered"}
    status = str(entry.get("rehearsal_status", "pending"))
    authorized = status == "passed" and not bool(entry.get("revoked", False)) and str(entry.get("skill_version")) == skill_version and str(entry.get("skill_sha256")) == skill_sha256
    return {"status": status, "authorized": authorized, "reason": "passed" if authorized else "adapter rehearsal, skill, or revocation check failed"}


def promote(path: Path, adapter_id: str, skill_id: str, skill_version: str, skill_sha256: str, rehearsal_id: str, receipt_sha256: str) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("adapters"), dict):
        raise ValueError("invalid readiness registry")
    entry = data["adapters"].setdefault(adapter_id, {})
    if entry.get("governed_work_ready") and entry.get("rehearsal", {}).get("receipt_sha256") == receipt_sha256:
        return {"ok": True, "adapter_id": adapter_id, "rehearsal_id": rehearsal_id, "governed_work_ready": True, "result": "already-promoted", "registry_mutations": 0}
    entry.update({"skill_id": skill_id, "skill_version": skill_version, "skill_sha256": skill_sha256, "rehearsal": {"status": "passed", "rehearsal_id": rehearsal_id, "receipt_sha256": receipt_sha256}, "rehearsal_status": "passed", "governed_work_ready": True, "revoked": False})
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return {"ok": True, "adapter_id": adapter_id, "rehearsal_id": rehearsal_id, "governed_work_ready": True, "result": "promoted", "registry_mutations": 1}
