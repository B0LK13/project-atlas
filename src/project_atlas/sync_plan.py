"""AS-SYNC-002-SCAFFOLD — Deterministic dry-run sync plan (no estate scan).

Consumes an explicit workspace-registry dry-run document (from
``workspace_registry.build_dry_run_registry`` or a fixture dict) and emits a
schema-valid sync PLAN with an ordered ``project_uuid`` list and dispositions
``eligible`` / ``quarantined`` / ``disabled``.

Scaffold only — never claims AS-SYNC-002 certification, never writes
``00-system/sync/``, never invents PILOT roots or project UUIDs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from project_atlas.schema import validate_record
from project_atlas.source_identity import validate_project_uuid

GENERATOR_ID = "atlas-sync-002-scaffold"
PACKAGE_ID = "AS-SYNC-002-SCAFFOLD"
REPORT_SCHEMA = "sync-plan-dry-run"
REPORT_RELATIVE = Path("generated") / "ops" / "sync-plan-dry-run.json"

_DISPOSITION_ELIGIBLE = "eligible"
_DISPOSITION_QUARANTINED = "quarantined"
_DISPOSITION_DISABLED = "disabled"

_REQUIRED_REGISTRY_KEYS = (
    "registry_id",
    "vault_identity",
    "projects",
    "quarantine",
    "policy_defaults",
)


class SyncPlanError(ValueError):
    """Fail-closed dry-run sync plan error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _as_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SyncPlanError(f"{label} must be an object")
    return value


def _as_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise SyncPlanError(f"{label} must be an array")
    return value


def _project_sync_eligible(project: dict[str, Any], defaults: dict[str, Any]) -> bool:
    policy = project.get("policy")
    if isinstance(policy, dict) and "sync_eligible" in policy:
        return bool(policy["sync_eligible"])
    return bool(defaults.get("sync_eligible", True))


def _quarantine_paths(quarantine: list[Any]) -> set[str]:
    paths: set[str] = set()
    for row in quarantine:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if isinstance(path, str) and path.strip():
            paths.add(path.strip())
    return paths


def _quarantine_reason_for_path(quarantine: list[Any], path: str) -> str | None:
    for row in quarantine:
        if isinstance(row, dict) and row.get("path") == path:
            reason = row.get("reason")
            return str(reason) if reason is not None else None
    return None


def build_dry_run_sync_plan(registry: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic dry-run sync plan from a registry document.

    Input must be an explicit registry mapping (fixture or
    ``build_dry_run_registry`` output). No filesystem scan is performed.
    """
    document = _as_mapping(registry, label="registry")
    for key in _REQUIRED_REGISTRY_KEYS:
        if key not in document:
            raise SyncPlanError(f"registry missing required key: {key}")

    registry_id = document["registry_id"]
    vault_identity = document["vault_identity"]
    if not isinstance(registry_id, str) or not registry_id.strip():
        raise SyncPlanError("registry_id must be a non-empty string")
    if not isinstance(vault_identity, str) or not vault_identity.strip():
        raise SyncPlanError("vault_identity must be a non-empty string")

    projects = _as_list(document["projects"], label="projects")
    quarantine = _as_list(document["quarantine"], label="quarantine")
    defaults = _as_mapping(document["policy_defaults"], label="policy_defaults")
    blocked_paths = _quarantine_paths(quarantine)

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in projects:
        project = _as_mapping(raw, label="project entry")
        uuid_raw = project.get("project_uuid")
        if not isinstance(uuid_raw, str) or not uuid_raw.strip():
            raise SyncPlanError("project entry missing project_uuid")
        try:
            project_uuid = validate_project_uuid(uuid_raw.strip())
        except ValueError as exc:
            raise SyncPlanError(f"invalid project_uuid: {uuid_raw!r}") from exc
        if project_uuid in seen:
            raise SyncPlanError(f"duplicate project_uuid in registry: {project_uuid}")
        seen.add(project_uuid)

        root_id = project.get("root_id")
        project_root = project.get("project_root")
        if not isinstance(root_id, str) or not root_id.strip():
            raise SyncPlanError(f"project {project_uuid} missing root_id")
        if not isinstance(project_root, str) or not project_root.strip():
            raise SyncPlanError(f"project {project_uuid} missing project_root")

        enabled = bool(project.get("enabled", True))
        reason: str | None = None
        if project_root in blocked_paths:
            disposition = _DISPOSITION_QUARANTINED
            reason = _quarantine_reason_for_path(quarantine, project_root)
        elif not enabled:
            disposition = _DISPOSITION_DISABLED
            reason = "project_disabled"
        elif not _project_sync_eligible(project, defaults):
            disposition = _DISPOSITION_DISABLED
            reason = "sync_eligible_false"
        else:
            disposition = _DISPOSITION_ELIGIBLE

        entries.append(
            {
                "project_uuid": project_uuid,
                "disposition": disposition,
                "reason": reason,
                "root_id": root_id,
                "project_root": project_root,
            }
        )

    entries.sort(key=lambda row: str(row["project_uuid"]))
    project_order = [str(row["project_uuid"]) for row in entries]

    # Path-only quarantine rows (no invent UUID) — visibility stub, not plan order.
    quarantine_paths: list[dict[str, Any]] = []
    for row in quarantine:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        quarantine_paths.append(
            {
                "path": path.strip(),
                "reason": str(row.get("reason") or "unspecified"),
            }
        )
    quarantine_paths.sort(key=lambda row: str(row["path"]))

    plan: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.sync_plan.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "DRY-RUN SYNC PLAN SCAFFOLD ≠ AS-SYNC-002 CERTIFIED / ≠ PILOT PASS",
        "package": PACKAGE_ID,
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": registry_id.strip(),
        "vault_identity": vault_identity.strip(),
        "project_order": project_order,
        "entries": entries,
        "quarantine_paths": quarantine_paths,
        # Retry/resume stubs — scaffold only; not SYNC-002 certified resume.
        "checkpoint": {
            "resume_from_project_uuid": None,
            "completed_project_uuids": [],
            "last_checkpoint_key": None,
        },
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(plan, REPORT_SCHEMA)
    return plan


def write_dry_run_sync_plan(vault: Path, document: dict[str, Any]) -> Path:
    """Persist dry-run sync plan under generated/ops/ only."""
    validate_record(document, REPORT_SCHEMA)
    vault_root = vault.expanduser().resolve()
    path = vault_root / REPORT_RELATIVE
    forbidden = vault_root / "00-system" / "sync" / "sync-plan.json"
    if path.resolve() == forbidden.resolve():  # pragma: no cover - defensive
        raise SyncPlanError("scaffold must not write production sync plan path")
    # Also refuse any write under production sync registry directory.
    production_sync = vault_root / "00-system" / "sync"
    if path.resolve().is_relative_to(production_sync.resolve()):
        raise SyncPlanError("scaffold must not write under 00-system/sync/")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, payload)
    return path
