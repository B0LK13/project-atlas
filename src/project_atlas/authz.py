"""AS-2.1-AUTHZ-001 - local operator capability authorization.

Fail-closed capability checks for live 2.1 surfaces. No network identity
provider in this package — explicit operator profile only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

PACKAGE_ID = "AS-2.1-AUTHZ-001"
Capability = Literal[
    "api.read",
    "web.read",
    "mcp.read",
    "scheduler.arm",
    "scheduler.dispatch",
    "oai.import",
    "pilot.scan",
    "autonomy.l3",
    "vault.write",
]

ALL_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        "api.read",
        "web.read",
        "mcp.read",
        "scheduler.arm",
        "scheduler.dispatch",
        "oai.import",
        "pilot.scan",
        "autonomy.l3",
        "vault.write",
    }
)

# Default local operator: read surfaces + import/pilot scan; no write/L3/dispatch.
DEFAULT_OPERATOR_CAPS: Final[frozenset[Capability]] = frozenset(
    {
        "api.read",
        "web.read",
        "mcp.read",
        "oai.import",
        "pilot.scan",
        "scheduler.arm",
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
