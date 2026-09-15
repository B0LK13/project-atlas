"""Versioned code-level authority registry (AS-CORE-006 trust root).

Trust chain:
  owner authorization → certified repository change → this registry
  → deterministic authority evaluation

Documents that self-assert “canonical” / “authoritative” are not the trust root.
Only owner-certified registry rules grant domain authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from project_atlas.domain.authority_semantics import ArtifactRole, AuthorityDomainId

AUTHORITY_REGISTRY_VERSION: Final[int] = 1
AUTHORITY_TRUST_ROOT: Final[str] = (
    "code-level-authority-registry/v1"
    " (owner-certified Core package AS-CORE-006)"
)


@dataclass(frozen=True, slots=True)
class AuthorityRule:
    """One explicit domain → role mapping in the registry."""

    rule_id: str
    domain: AuthorityDomainId
    authoritative_role: ArtifactRole
    subject_prefix: str
    field: str
    description: str


# MVP encodes only rules proven by the AS-CORE-006 entry gate.
_RULES: tuple[AuthorityRule, ...] = (
    AuthorityRule(
        rule_id="R-TITLE-001",
        domain=AuthorityDomainId.WORK_PACKAGE_DURABLE_TITLE,
        authoritative_role=ArtifactRole.PACKAGE_GENESIS_RECEIPT,
        subject_prefix="wp:",
        field="title",
        description=(
            "For the durable work-package title domain, package_genesis_receipt "
            "is authoritative. Remediation episode titles and later operational "
            "titles do not replace the durable package title merely because they "
            "were observed later."
        ),
    ),
)


def registry_version() -> int:
    """Return the explicit authority registry version."""
    return AUTHORITY_REGISTRY_VERSION


def trust_root() -> str:
    """Return the inspectable trust-root identifier."""
    return AUTHORITY_TRUST_ROOT


def persisted_authority_binding_matches_live(
    *,
    recorded_trust_root: str | None = None,
    recorded_registry_version: object | None = None,
) -> bool:
    """Return True only when recorded metadata is absent or matches live registry.

    A present mismatch is never accepted. Bool/string versions are not live
    integers (``True`` must not equal registry version ``1``). This does not
    grant owner authority; it only rejects forged or stale bindings (AX-AUTH-005).
    """
    trust_ok = recorded_trust_root is None or (
        isinstance(recorded_trust_root, str) and recorded_trust_root == trust_root()
    )
    version_ok = recorded_registry_version is None or (
        isinstance(recorded_registry_version, int)
        and not isinstance(recorded_registry_version, bool)
        and recorded_registry_version == registry_version()
    )
    return trust_ok and version_ok


def all_rules() -> tuple[AuthorityRule, ...]:
    """Return all registered authority rules in deterministic order."""
    return tuple(sorted(_RULES, key=lambda rule: rule.rule_id))


def rules_for(subject: str, field: str) -> tuple[AuthorityRule, ...]:
    """Return registry rules matching subject+field (may be empty)."""
    matches = [
        rule
        for rule in _RULES
        if subject.startswith(rule.subject_prefix) and field == rule.field
    ]
    return tuple(sorted(matches, key=lambda rule: rule.rule_id))


def get_rule(rule_id: str) -> AuthorityRule | None:
    """Lookup a single rule by ID."""
    for rule in _RULES:
        if rule.rule_id == rule_id:
            return rule
    return None
