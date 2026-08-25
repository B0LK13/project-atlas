"""AS-CODER-ALPHA-PROVIDER-READ-001 -- vault-scoped provider REPORT READ.

Inspects persisted AS-2.0-PROV-001 artifacts:

- ``generated/ops/provider-adapter-registry.json``
- ``generated/ops/provider-quarantine/*.json``

This module never writes a registry, never quarantines new output, never
enables live SDKs, and never dispatches provider generate.

Honesty:
- PROVIDER != AUTHORITY
- REGISTRY != LIVE SDK
- QUARANTINE != APPROVED
- MISSING != ENABLED
- EMPTY != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-PROVIDER-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-provider-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.provider-read.v1"
TOOL_ID: Final[str] = "atlas.provider.read"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-PROV-001",)
TRUTH_BOUNDARY: Final[str] = (
    "PROVIDER != AUTHORITY / REGISTRY != LIVE SDK / "
    "QUARANTINE != APPROVED / MISSING != ENABLED / EMPTY != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

OPS_REL: Final[Path] = Path("generated") / "ops"
REGISTRY_REL: Final[Path] = OPS_REL / "provider-adapter-registry.json"
QUARANTINE_REL: Final[Path] = OPS_REL / "provider-quarantine"

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "PROVIDER != AUTHORITY",
    "REGISTRY != LIVE SDK",
    "QUARANTINE != APPROVED",
    "MISSING != ENABLED",
    "EMPTY != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

ProjectionStatus = Literal["MISSING", "EMPTY", "PRESENT"]
StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebProviderError(ValueError):
    """Fail-closed provider REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "provider_is_authority": False,
        "registry_is_live_sdk": False,
        "quarantine_is_approved": False,
        "missing_is_enabled": False,
        "missing_is_healthy": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "live_sdk_enabled": False,
        "generate_dispatched": False,
        "registry_written": False,
        "quarantine_written": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebProviderError(f"provider-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebProviderError("provider-vault-missing")
    return root


def _inside(vault: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise WebProviderError(f"provider-path-unreadable:{exc}") from exc
    if not resolved.is_relative_to(vault):
        raise WebProviderError("provider-path-escape")
    return resolved


def _projection_root(
    vault: Path, relative: Path
) -> tuple[ProjectionStatus, Path | None]:
    raw = vault / relative
    if not raw.exists():
        return "MISSING", None
    if raw.is_symlink() or not raw.is_dir():
        raise WebProviderError(
            f"provider-projection-not-directory:{relative.as_posix()}"
        )
    return "EMPTY", _inside(vault, raw)


def _read_json_object(vault: Path, path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WebProviderError(f"provider-not-regular-file:{path.name}")
    resolved = _inside(vault, path)
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebProviderError(f"provider-malformed-json:{path.name}") from exc
    except OSError as exc:
        raise WebProviderError(f"provider-unreadable:{path.name}") from exc
    if not isinstance(loaded, dict):
        raise WebProviderError(f"provider-json-not-object:{path.name}")
    return loaded


def _validate(payload: dict[str, Any], schema_kind: str, name: str) -> None:
    try:
        validate_record(payload, schema_kind)
    except SchemaValidationError as exc:
        raise WebProviderError(f"provider-malformed-record:{name}") from exc


def _relative_posix(vault: Path, path: Path) -> str:
    return _inside(vault, path).relative_to(vault).as_posix()


def _adapter_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("adapters")
    adapters = raw if isinstance(raw, list) else []
    rows: list[dict[str, Any]] = []
    for item in adapters:
        if not isinstance(item, dict):
            continue
        adapter_id = item.get("adapter_id")
        if adapter_id is None:
            continue
        capabilities_raw = item.get("capabilities")
        capabilities = (
            [str(cap) for cap in capabilities_raw]
            if isinstance(capabilities_raw, list)
            else []
        )
        rows.append(
            {
                "adapter_id": str(adapter_id),
                "provider": item.get("provider"),
                "enabled": False,
                "status": item.get("status"),
                "capabilities": capabilities,
            }
        )
    rows.sort(key=lambda row: str(row["adapter_id"]).casefold())
    return rows


def _inspect_registry(
    vault: Path,
) -> tuple[ProjectionStatus, dict[str, Any] | None]:
    _, ops_root = _projection_root(vault, OPS_REL)
    if ops_root is None:
        return "MISSING", None
    raw = vault / REGISTRY_REL
    if not raw.exists():
        return "EMPTY", None
    payload = _read_json_object(vault, raw)
    _validate(payload, "provider-adapter-registry", raw.name)
    if payload.get("adapters_enabled") is not False:
        raise WebProviderError("provider-registry-live-claimed")
    return "PRESENT", payload


def _quarantine_summary(
    vault: Path, path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    secret = payload.get("secret_scan")
    findings_count = 0
    content_redacted = True
    if isinstance(secret, dict):
        raw_count = secret.get("findings_count", 0)
        findings_count = int(raw_count) if isinstance(raw_count, int) else 0
        content_redacted = bool(secret.get("content_redacted", True))
    return {
        "kind": "quarantine-envelope",
        "path": _relative_posix(vault, path),
        "envelope_id": str(payload["envelope_id"]),
        "adapter_id": str(payload["adapter_id"]),
        "status": payload.get("status"),
        "findings_count": findings_count,
        "content_redacted": content_redacted,
        "payload_sha256": payload.get("payload_sha256"),
    }


def _list_quarantine(
    vault: Path,
) -> tuple[ProjectionStatus, list[dict[str, Any]]]:
    _, root = _projection_root(vault, QUARANTINE_REL)
    if root is None:
        return "MISSING", []
    records: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.name.endswith(".json"):
            continue
        payload = _read_json_object(vault, path)
        _validate(payload, "provider-quarantine-envelope", path.name)
        if payload.get("status") not in {
            "quarantined",
            "rejected-secret",
            "rejected-disabled",
        }:
            raise WebProviderError(f"provider-quarantine-approved-claimed:{path.name}")
        records.append(_quarantine_summary(vault, path, payload))
    if records:
        return "PRESENT", records
    return "EMPTY", []


def _ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = [str(item[key]) for item in rows if key in item]
    values.sort(key=str.casefold)
    return values


def _rollup(
    registry_status: ProjectionStatus,
    quarantine_status: ProjectionStatus,
) -> tuple[StatusRollup, str, str, bool]:
    states = (registry_status, quarantine_status)
    if any(state == "PRESENT" for state in states):
        return (
            "PRESENT",
            "persisted provider registry/quarantine reports are visible; "
            "PROVIDER != AUTHORITY; REGISTRY != LIVE SDK; "
            "QUARANTINE != APPROVED",
            "ARTIFACTS_PRESENT",
            True,
        )
    if all(state == "MISSING" for state in states):
        return (
            "UNKNOWN",
            "provider registry/quarantine reports are absent; absence is "
            "not ENABLED and is not healthy",
            "ARTIFACTS_ABSENT",
            False,
        )
    return (
        "EMPTY",
        "generated/ops exists but holds no provider registry/quarantine "
        "reports; EMPTY != HEALTHY",
        "ARTIFACTS_EMPTY",
        False,
    )


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    registry_status: ProjectionStatus,
    registry_payload: dict[str, Any] | None,
    quarantine_status: ProjectionStatus,
    quarantine: list[dict[str, Any]],
) -> dict[str, Any]:
    adapters = _adapter_records(registry_payload) if registry_payload else []
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "artifacts": {
            "registry": {
                "status": registry_status,
                "path": REGISTRY_REL.as_posix(),
                "adapters_enabled": False,
                "adapter_count": len(adapters),
                "adapter_ids": _ids(adapters, "adapter_id"),
                "records": adapters,
            },
            "quarantine": {
                "status": quarantine_status,
                "path": QUARANTINE_REL.as_posix(),
                "count": len(quarantine),
                "envelope_ids": _ids(quarantine, "envelope_id"),
                "records": quarantine,
            },
        },
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_provider(vault: Path) -> dict[str, Any]:
    """Read-only provider registry/quarantine inspect. Never writes or generates."""
    root = _resolve_vault(vault)
    registry_status, registry_payload = _inspect_registry(root)
    quarantine_status, quarantine = _list_quarantine(root)
    status, reason, reason_code, available = _rollup(
        registry_status, quarantine_status
    )
    return _envelope(
        status=status,
        reason=reason,
        reason_code=reason_code,
        available=available,
        registry_status=registry_status,
        registry_payload=registry_payload,
        quarantine_status=quarantine_status,
        quarantine=quarantine,
    )


def render_provider_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    artifacts = view.get("artifacts")
    registry: dict[str, Any] = {}
    quarantine: dict[str, Any] = {}
    if isinstance(artifacts, dict):
        raw_registry = artifacts.get("registry")
        raw_quarantine = artifacts.get("quarantine")
        if isinstance(raw_registry, dict):
            registry = raw_registry
        if isinstance(raw_quarantine, dict):
            quarantine = raw_quarantine
    lines = [
        f"atlas provider report [{view.get('status', 'UNKNOWN')}]",
        f"  available:    {view.get('available')}",
        f"  reason:       {view.get('reason_code')}",
        (
            "  registry:     "
            f"{registry.get('status', 'MISSING')} "
            f"adapters={registry.get('adapter_count', 0)} "
            "enabled=false"
        ),
        (
            "  quarantine:   "
            f"{quarantine.get('status', 'MISSING')} "
            f"count={quarantine.get('count', 0)}"
        ),
        "  live_sdk:     false",
        (
            "  honesty:      PROVIDER != AUTHORITY; REGISTRY != LIVE SDK; "
            "QUARANTINE != APPROVED; MISSING != ENABLED; "
            "EMPTY != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
