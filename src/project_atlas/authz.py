"""AS-2.1-AUTHZ-001 - local operator capability authorization.

Fail-closed capability checks for live 2.1 surfaces. No network identity
provider in this package — explicit operator profile only.

SEC-009: loopback is NOT authentication. API callers must present a
high-entropy per-launch session credential that maps to an explicit
OperatorProfile (request principal).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
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

# Caps that a read session credential may carry (SEC-009: read MUST NOT mutate).
READ_ONLY_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
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

# Privileged / mutating capabilities require an explicit privileged credential.
PRIVILEGED_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        "web.action",
        "vault.write",
        "autonomy.l3",
        "scheduler.dispatch",
        "provider.live",
    }
)

_SESSION_TOKEN_BYTES: Final[int] = 32


class AuthzError(PermissionError):
    """Fail-closed authorization error."""


class ApiAuthError(PermissionError):
    """Fail-closed API request-principal authentication error (SEC-009)."""


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


@dataclass(frozen=True, slots=True)
class ApiSessionCredentials:
    """Per-launch API session credentials bound to request principals (SEC-009)."""

    read_token: str
    read_operator: OperatorProfile
    privileged_token: str | None = None
    privileged_operator: OperatorProfile | None = None

    def authorization_header(self, *, privileged: bool = False) -> str:
        if privileged:
            if self.privileged_token is None:
                raise ApiAuthError("auth-privileged-credential-unavailable")
            return f"Bearer {self.privileged_token}"
        return f"Bearer {self.read_token}"

    def auth_headers(self, *, privileged: bool = False) -> dict[str, str]:
        return {"Authorization": self.authorization_header(privileged=privileged)}


@dataclass
class ApiSessionStore:
    """In-memory token→principal map for one LIVE_API process launch."""

    credentials: ApiSessionCredentials
    _token_digest_to_operator: dict[bytes, OperatorProfile] = field(
        default_factory=dict, repr=False
    )

    def resolve_bearer(self, authorization_header: str | None) -> OperatorProfile:
        """Resolve Authorization Bearer to a bound OperatorProfile.

        unauthenticated → DENY; wrong credential → DENY (SEC-009).
        """
        if authorization_header is None or not authorization_header.strip():
            raise ApiAuthError("auth-required")
        raw = authorization_header.strip()
        if not raw.lower().startswith("bearer "):
            raise ApiAuthError("auth-invalid")
        token = raw[7:].strip()
        if not token:
            raise ApiAuthError("auth-invalid")
        digest = _token_digest(token)
        for stored_digest, operator in self._token_digest_to_operator.items():
            if hmac.compare_digest(stored_digest, digest):
                return operator
        raise ApiAuthError("auth-invalid")


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


def read_only_operator(operator_id: str = "api-read") -> OperatorProfile:
    """Return a read-only API principal (no privileged / mutating caps)."""
    return OperatorProfile(operator_id=operator_id, capabilities=READ_ONLY_CAPABILITIES)


def mint_api_session(
    launch_operator: OperatorProfile | None = None,
) -> ApiSessionStore:
    """Mint high-entropy per-launch credentials bound to explicit principals.

    Always issues a read credential (READ ONLY). When ``launch_operator``
    carries any privileged capability, also issues a distinct privileged
    credential bound to that operator (SEC-009).
    """
    base = launch_operator or default_operator()
    read_op = OperatorProfile(
        operator_id=f"{base.operator_id}-read",
        capabilities=frozenset(base.capabilities & READ_ONLY_CAPABILITIES)
        or READ_ONLY_CAPABILITIES,
    )
    if not read_op.allows("api.read"):
        read_op = OperatorProfile(
            operator_id=read_op.operator_id,
            capabilities=frozenset(set(read_op.capabilities) | {"api.read"}),
        )
    read_token = secrets.token_urlsafe(_SESSION_TOKEN_BYTES)
    privileged_token: str | None = None
    privileged_op: OperatorProfile | None = None
    if base.capabilities & PRIVILEGED_CAPABILITIES:
        privileged_token = secrets.token_urlsafe(_SESSION_TOKEN_BYTES)
        privileged_op = base
    creds = ApiSessionCredentials(
        read_token=read_token,
        read_operator=read_op,
        privileged_token=privileged_token,
        privileged_operator=privileged_op,
    )
    store = ApiSessionStore(credentials=creds)
    store._token_digest_to_operator[_token_digest(read_token)] = read_op
    if privileged_token is not None and privileged_op is not None:
        store._token_digest_to_operator[_token_digest(privileged_token)] = privileged_op
    return store


def _token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


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
