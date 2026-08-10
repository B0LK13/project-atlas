"""AS-2.1-AUTHZ-001 - local operator capability authorization.

Fail-closed capability checks for live 2.1 surfaces. No network identity
provider in this package — explicit operator profile only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-AUTHZ-001"
Capability = Literal[
    "api.read",
    "web.read",
    "mcp.read",
    "scheduler.arm",
    "scheduler.dispatch",
    "oai.import",
    "oai.responses",
    "pilot.scan",
    "autonomy.l3",
    "vault.write",
    "chatgpt.bridge",
    "collab.session",
    "web.action",
    "provider.live",
]

ALL_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        "api.read",
        "web.read",
        "mcp.read",
        "scheduler.arm",
        "scheduler.dispatch",
        "oai.import",
        "oai.responses",
        "pilot.scan",
        "autonomy.l3",
        "vault.write",
        "chatgpt.bridge",
        "collab.session",
        "web.action",
        "provider.live",
    }
)

# Default local operator: read surfaces + import/pilot/collab/chatgpt/oai.responses;
# no write/L3/dispatch/provider.live/web.action.
DEFAULT_OPERATOR_CAPS: Final[frozenset[Capability]] = frozenset(
    {
        "api.read",
        "web.read",
        "mcp.read",
        "oai.import",
        "oai.responses",
        "pilot.scan",
        "scheduler.arm",
        "chatgpt.bridge",
        "collab.session",
    }
)


class AuthzError(PermissionError):
    """Fail-closed authorization error."""


@dataclass(frozen=True, slots=True)
class OperatorProfile:
    """Explicit local operator capability set."""

    operator_id: str
    capabilities: frozenset[Capability]
    package_id: str = PACKAGE_ID

    def allows(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if capability not in ALL_CAPABILITIES:
            raise AuthzError(f"authz-unknown-capability:{capability}")
        if not self.allows(capability):
            raise AuthzError(f"authz-denied:{capability}")


def default_operator(operator_id: str = "local-operator") -> OperatorProfile:
    """Return the default supervised local operator profile."""
    return OperatorProfile(operator_id=operator_id, capabilities=DEFAULT_OPERATOR_CAPS)


def elevated_operator(
    operator_id: str,
    *,
    extra: set[Capability] | frozenset[Capability],
) -> OperatorProfile:
    """Build an elevated profile; vault.write / autonomy.l3 must be explicit."""
    caps = set(DEFAULT_OPERATOR_CAPS)
    caps.update(extra)
    unknown = caps - set(ALL_CAPABILITIES)
    if unknown:
        raise AuthzError(f"authz-unknown-capability:{sorted(unknown)[0]}")
    return OperatorProfile(operator_id=operator_id, capabilities=frozenset(caps))


def write_authz_audit_receipt(
    vault: Path,
    *,
    receipt_id: str = "authz-audit",
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Persist a reconstructable capability audit receipt (not authority)."""
    require_compatibility_anchor()
    op = operator or default_operator()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": receipt_id,
        "operator_id": op.operator_id,
        "capabilities": sorted(op.capabilities),
        "all_capabilities": sorted(ALL_CAPABILITIES),
        "denied_by_default": sorted(ALL_CAPABILITIES - op.capabilities),
        "authority": False,
        "generated": {"by": "project-atlas"},
    }
    path = vault / "generated" / "ops" / "authz" / f"{receipt_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)
    return payload
