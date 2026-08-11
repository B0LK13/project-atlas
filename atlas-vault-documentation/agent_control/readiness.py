"""Fail-closed adapter rehearsal readiness registry (CODEX-SEC-015)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_control import authority


def check(path: Path | None, adapter_id: str, skill_version: str, skill_sha256: str) -> dict[str, Any]:
    # SEC-015: missing readiness configuration must DENY (never legacy authorize).
    if path is None:
        return {
            "status": "not-configured",
            "authorized": False,
            "reason": "readiness registry is not configured",
        }
    if not path.is_file():
        return {"status": "missing", "authorized": False, "reason": "readiness registry is missing"}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry = data.get("adapters", {}).get(adapter_id) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        return {"status": "unknown", "authorized": False, "reason": "adapter is not registered"}
    status = str(entry.get("rehearsal_status", "pending"))
    authorized = (
        status == "passed"
        and not bool(entry.get("revoked", False))
        and str(entry.get("skill_version")) == skill_version
        and str(entry.get("skill_sha256")) == skill_sha256
    )
    return {
        "status": status,
        "authorized": authorized,
        "reason": "passed" if authorized else "adapter rehearsal, skill, or revocation check failed",
    }


def promote(
    path: Path,
    adapter_id: str,
    skill_id: str,
    skill_version: str,
    skill_sha256: str,
    rehearsal_id: str,
    receipt_sha256: str,
    *,
    authority_grant: dict[str, Any],
) -> dict[str, Any]:
    """Promote readiness only when an independent GRANT authorizes it.

    A session receipt hash alone is never sufficient (SEC-016 / SEC-019).
    """
    if not isinstance(authority_grant, dict) or authority_grant.get("grant_type") != "atlas-authority-grant":
        raise ValueError("readiness promotion requires an independently issued authority grant")
    if authority_grant.get("receipt_is_authority") is True:
        raise ValueError("self-asserted receipt is not authority")
    if authority_grant.get("purpose") != authority.PURPOSE_PROMOTE_READINESS:
        raise ValueError("authority grant purpose mismatch")
    subject = authority_grant.get("subject") if isinstance(authority_grant.get("subject"), dict) else {}
    if (
        subject.get("adapter_id") != adapter_id
        or subject.get("skill_id") != skill_id
        or subject.get("skill_version") != skill_version
        or subject.get("skill_sha256") != skill_sha256
    ):
        raise ValueError("authority grant subject mismatch")
    if bool(authority_grant.get("revoked")):
        raise ValueError("authority grant is revoked")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("adapters"), dict):
        raise ValueError("invalid readiness registry")
    entry = data["adapters"].setdefault(adapter_id, {})
    if entry.get("governed_work_ready") and entry.get("rehearsal", {}).get("receipt_sha256") == receipt_sha256:
        return {
            "ok": True,
            "adapter_id": adapter_id,
            "rehearsal_id": rehearsal_id,
            "governed_work_ready": True,
            "result": "already-promoted",
            "registry_mutations": 0,
            "authority_grant_id": authority_grant.get("grant_id"),
        }
    entry.update(
        {
            "skill_id": skill_id,
            "skill_version": skill_version,
            "skill_sha256": skill_sha256,
            "rehearsal": {
                "status": "passed",
                "rehearsal_id": rehearsal_id,
                "receipt_sha256": receipt_sha256,
                "authority_grant_id": authority_grant.get("grant_id"),
            },
            "rehearsal_status": "passed",
            "governed_work_ready": True,
            "revoked": False,
        }
    )
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return {
        "ok": True,
        "adapter_id": adapter_id,
        "rehearsal_id": rehearsal_id,
        "governed_work_ready": True,
        "result": "promoted",
        "registry_mutations": 1,
        "authority_grant_id": authority_grant.get("grant_id"),
    }
