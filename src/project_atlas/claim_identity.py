"""Shared Claim Identity v2 primitives (AS-CORE-003).

Canonical identity serialization, extraction rules, and stable locator
resolution used by both the knowledge compiler and the v1-to-v2 migration.
Centralizing these prevents drift between runtime extraction and historical
migration and eliminates delimiter-collision ambiguity in identity keys.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from project_atlas.domain.vocabulary import ClaimType

_TOKEN = re.compile(r"[^a-z0-9]+")

# Line extraction rules shared between compiler and migration.
# Order matters: the first matching rule wins for a given line.
_LINE_RULES: tuple[tuple[ClaimType, str, re.Pattern[str]], ...] = (
    (
        ClaimType.PROJECT_PURPOSE,
        "purpose",
        re.compile(r"^(?:project\s+)?purpose\s*:\s*(.+)$", re.I),
    ),
    (
        ClaimType.RUNTIME_DEPENDENCY,
        "runtime",
        re.compile(r"^(?:requires|runtime|dependency)\s*:\s*(.+)$", re.I),
    ),
    (
        ClaimType.DEPLOYMENT_TARGET,
        "deployment",
        re.compile(
            r"^(?:deployment(?:\s+target)?|deploy(?:ed|ment)?\s+target|target)"
            r"\s*:\s*(.+)$",
            re.I,
        ),
    ),
    (
        ClaimType.SETUP_REQUIREMENT,
        "setup",
        re.compile(r"^(?:setup|install(?:ation)?|requirement)\s*:\s*(.+)$", re.I),
    ),
    (
        ClaimType.TEST_RESULT,
        "validation",
        re.compile(r"^(?:test|validation|acceptance)\s*(?:result|status)?\s*:\s*(.+)$", re.I),
    ),
    (ClaimType.ROADMAP_STATUS, "roadmap", re.compile(r"^(?:roadmap|status)\s*:\s*(.+)$", re.I)),
    (
        ClaimType.WORK_PACKAGE_STATUS,
        "work-package",
        re.compile(r"^(?:work[- ]package)\s*:\s*(.+)$", re.I),
    ),
    (ClaimType.DECISION, "decision", re.compile(r"^(?:decision)\s*:\s*(.+)$", re.I)),
    (ClaimType.RISK, "risk", re.compile(r"^(?:risk|blocker)\s*:\s*(.+)$", re.I)),
    (
        ClaimType.OPERATIONAL_INSTRUCTION,
        "operations",
        re.compile(r"^(?:run|operate|command|instruction)\s*:\s*(.+)$", re.I),
    ),
)

_SUPERSESSION_RULE = re.compile(
    r"^(?:supersedes|replaces)\s*:\s*([A-Za-z0-9][A-Za-z0-9._-]*)$", re.I
)
_EXPLICIT_ID = re.compile(r"\{#([A-Za-z0-9][A-Za-z0-9._-]*)\}")


class UnresolvedLocatorError(ValueError):
    """A recognized claim line has no durable semantic locator."""

    def __init__(self, line: str) -> None:
        self.line = line
        super().__init__(f"no stable locator found for recognized claim: {line}")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    result = _TOKEN.sub("-", value.lower()).strip("-")
    return result or "unknown"


def canonical_identity_key(
    project_identity: str,
    source_identity: str,
    claim_type: str,
    field: str,
    locator: str,
) -> str:
    """Return a canonical, delimiter-safe identity key for a claim.

    The key is a compact JSON array so that embedded delimiters in the
    component values cannot collide with the serialization boundaries.
    """
    return json.dumps(
        ["v2", project_identity, source_identity, claim_type, field, locator],
        separators=(",", ":"),
    )


def claim_id_from_key(identity_key: str) -> str:
    """Derive the deterministic public claim id from a canonical identity key."""
    return f"claim-{_digest(identity_key)[:20]}"


def v2_claim_id(
    project_identity: str,
    source_identity: str,
    claim_type: str,
    field: str,
    locator: str,
) -> str:
    """Return the canonical v2 claim id for the given identity components."""
    return claim_id_from_key(
        canonical_identity_key(project_identity, source_identity, claim_type, field, locator)
    )


def resolve_locator(
    line: str,
    current_heading: str | None,
    *,
    schema_key: str | None = None,
    is_project_manifest: bool = False,
) -> str | None:
    """Resolve a stable semantic locator for a matched claim line.

    Priority:
    1. Explicit validated ID: `{#id}` in the claim line.
    2. Schema key (compiler only): `schema:<key>`.
    3. Project manifest marker: `schema:project-manifest`.
    4. Heading with explicit ID: `heading:<id>`.
    5. Heading slug: `heading:<slug>`.
    6. Unresolved: return ``None``.
    """
    explicit_match = _EXPLICIT_ID.search(line)
    if explicit_match:
        return f"id:{explicit_match.group(1).strip()}"
    if schema_key:
        return f"schema:{schema_key}"
    if is_project_manifest:
        return "schema:project-manifest"
    if current_heading:
        heading_id_match = _EXPLICIT_ID.search(current_heading)
        if heading_id_match:
            return f"heading:{heading_id_match.group(1).strip()}"
        return f"heading:{_slug(current_heading)}"
    return None


def normalize_claim_value(value: str) -> str:
    """Collapse whitespace in a claim value the same way in compiler and migration."""
    return " ".join(value.split())


def extract_claims(
    text: str,
    *,
    schema_key: str | None = None,
    is_project_manifest: bool = False,
    classification: str | None = None,
    reject_unresolved: bool = False,
) -> list[dict[str, Any]]:
    """Extract raw claim records from source text using shared rules.

    Each record contains the normalized current value, the unmodified
    ``legacy_value`` used by the v1 compiler, and the durable v2 locator.
    This is used by the compiler and migration so both agree on the complete
    candidate set while the migration can still reconstruct historical IDs.
    """
    claims: list[dict[str, Any]] = []
    predecessor_id: str | None = None
    current_heading: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("- ").strip()
        supersession = _SUPERSESSION_RULE.match(line)
        if supersession:
            predecessor_id = supersession.group(1)
            continue

        if raw_line.startswith("#"):
            current_heading = raw_line.lstrip("#").strip()
            continue

        for claim_type, field, pattern in _LINE_RULES:
            match = pattern.match(line)
            if not match:
                continue
            claim_value = match.group(1)
            legacy_value = normalize_claim_value(match.group(1))
            explicit_match = _EXPLICIT_ID.search(line)
            if explicit_match:
                claim_value = claim_value.replace(explicit_match.group(0), "").strip()

            locator = resolve_locator(
                line,
                current_heading,
                schema_key=schema_key,
                is_project_manifest=is_project_manifest,
            )
            if locator is None:
                if reject_unresolved:
                    raise UnresolvedLocatorError(line)
                break

            claims.append(
                {
                    "claim_type": claim_type.value,
                    "field": field,
                    "value": normalize_claim_value(claim_value),
                    "legacy_value": legacy_value,
                    "locator": locator,
                    "predecessor_id": predecessor_id,
                }
            )
            break

    if classification == "architecture" and not claims:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            locator = resolve_locator(
                raw_line,
                current_heading,
                schema_key=schema_key,
                is_project_manifest=is_project_manifest,
            )
            if locator is None:
                if reject_unresolved:
                    raise UnresolvedLocatorError(line)
                break
            explicit_match = _EXPLICIT_ID.search(line)
            value = (
                line.replace(explicit_match.group(0), "").strip()
                if explicit_match
                else line
            )
            claims.append(
                {
                    "claim_type": ClaimType.ARCHITECTURE.value,
                    "field": "architecture",
                    "value": normalize_claim_value(value),
                    "legacy_value": normalize_claim_value(line),
                    "locator": locator,
                    "predecessor_id": predecessor_id,
                }
            )
            break

    return claims
