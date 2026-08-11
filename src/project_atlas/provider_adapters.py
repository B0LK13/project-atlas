"""AS-2.0-PROV-001 — optional provider adapter registry + quarantine.

Adapters remain disabled by default. Provider/model output is quarantined with
metadata-only secret findings and never writes Layer B authority. Bound to the
Atlas 1.0 compatibility anchor. No OpenAI/MCP SDK wiring in this package.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.0-PROV-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ENV_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

ProviderName = Literal["openai", "mcp", "local-model", "other"]
Capability = Literal["classify-assist", "summarize", "tool-read", "tool-query"]


class ProviderError(ValueError):
    """Fail-closed provider adapter error."""


FORBIDDEN_CAPABILITIES = frozenset(
    {
        "promote",
        "authority-mutate",
        "claim-compile",
        "vault-write",
        "secret-exfiltrate",
    }
)


@dataclass(frozen=True, slots=True)
class ProviderAdapter:
    adapter_id: str
    provider: ProviderName
    capabilities: tuple[Capability, ...]
    notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "adapter_id": self.adapter_id,
            "provider": self.provider,
            "enabled": False,
            "capabilities": list(self.capabilities),
            "status": "registered",
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _validate_adapter_id(adapter_id: str) -> str:
    token = adapter_id.strip()
    if not _ID_RE.fullmatch(token):
        raise ProviderError("provider-adapter-id-invalid")
    return token


def build_adapter_registry(
    vault: Path,
    *,
    adapters: list[ProviderAdapter] | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Write a disabled-by-default provider adapter registry."""
    _ = anchor or require_compatibility_anchor()
    items = adapters or []
    seen: set[str] = set()
    serialized: list[dict[str, Any]] = []
    for adapter in items:
        aid = _validate_adapter_id(adapter.adapter_id)
        if aid in seen:
            raise ProviderError(f"provider-adapter-duplicate:{aid}")
        seen.add(aid)
        for cap in adapter.capabilities:
            if str(cap) in FORBIDDEN_CAPABILITIES:
                raise ProviderError(f"provider-capability-forbidden:{cap}")
        serialized.append(adapter.as_dict())

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "adapters_enabled": False,
        "adapters": sorted(serialized, key=lambda item: item["adapter_id"]),
        "authority": {
            "level": "derived",
            "note": "Provider adapters optional; disabled leaves MVP functional",
        },
        "truth_boundary": "PROVIDER ADAPTER ≠ AUTHORITY / ≠ PROVENANCE BYPASS",
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "provider-adapter-registry")
    except SchemaValidationError as exc:
        raise ProviderError(f"provider-registry-schema:{exc}") from exc
    out = vault.resolve() / "generated" / "ops" / "provider-adapter-registry.json"
    _atomic_write_json(out, payload)
    return payload


def quarantine_provider_output(
    vault: Path,
    *,
    envelope_id: str,
    adapter_id: str,
    payload_text: str,
    payload_kind: Literal["structured-json", "text", "unknown"] = "text",
    adapters_enabled: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Quarantine provider output after secret scan; never promote to authority."""
    _ = anchor or require_compatibility_anchor()
    eid = envelope_id.strip()
    if not _ENV_RE.fullmatch(eid):
        raise ProviderError("provider-envelope-id-invalid")
    aid = _validate_adapter_id(adapter_id)

    if not adapters_enabled:
        status: Literal["quarantined", "rejected-secret", "rejected-disabled"] = (
            "rejected-disabled"
        )
        findings_count = 0
        finding_kinds: list[str] = []
    else:
        findings = scan_text(payload_text)
        findings_count = len(findings)
        finding_kinds = sorted({item.pattern for item in findings})
        status = "rejected-secret" if findings_count else "quarantined"

    # CODEX-SEC-006: envelope is metadata + digest only — never embed payload_text.
    digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "envelope_id": eid,
        "adapter_id": aid,
        "status": status,
        "secret_scan": {
            "findings_count": findings_count,
            "content_redacted": True,
            "finding_kinds": finding_kinds,
        },
        "payload_kind": payload_kind,
        "payload_sha256": digest,
        "authority": {
            "level": "derived",
            "note": "Quarantined provider output never writes Layer B",
        },
        "truth_boundary": "QUARANTINED PROVIDER OUTPUT ≠ AUTHORITY",
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "provider-quarantine-envelope")
    except SchemaValidationError as exc:
        raise ProviderError(f"provider-envelope-schema:{exc}") from exc

    out = (
        vault.resolve()
        / "generated"
        / "ops"
        / "provider-quarantine"
        / f"{eid}.json"
    )
    _atomic_write_json(out, payload)
    return payload
