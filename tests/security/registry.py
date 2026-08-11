"""Canonical map of Alpha security regression classes → remedi owners.

STATUS values here are suite-seed bookkeeping only.
They are NOT Codex validation outcomes.

After #267/#261/#265/#264/#262/#263 merged to main, remedi_pr is None
for every class below — seed tests exercise (do not skip).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecurityRegressionClass:
    """One vulnerability class that must keep an executable regression."""

    finding_ids: tuple[str, ...]
    class_id: str
    title: str
    remedi_pr: str | None
    """Merged remedi PR number as string for history, or None when on main."""

    primary_tests: tuple[str, ...]
    """Paths (repo-relative) of the authoritative remedi regression tests."""

    probe: str
    """Dotted import path used by the seed to detect remedi landing."""

    notes: str


# Ordered by directive regression-suite list (SECURITY-ALPHA-CLOSURE-002 §14).
SECURITY_REGRESSION_CLASSES: tuple[SecurityRegressionClass, ...] = (
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-001", "CODEX-SEC-002"),
        class_id="provenance",
        title="Provenance / promoted-bytes integrity + root authorization",
        remedi_pr=None,  # #267 on main
        primary_tests=(
            "tests/integration/test_codex_sec_001_002_provenance.py",
        ),
        probe="project_atlas.ingestion:ingest",
        notes=(
            "Remedi on main (#267). "
            "Invariant: PROMOTED_BYTES_SHA256 == APPROVED_PROVENANCE_SHA256; "
            "manifest root must not self-authorize."
        ),
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-021",),
        class_id="trusted_exec",
        title="Trusted normalizer / executable selection",
        remedi_pr=None,  # #261 on main
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec021_trusted_exec.py",
        ),
        probe="atlas-vault-documentation.internal.trusted_exec:authorize_executable",
        notes=(
            "Remedi on main (#261). Control-plane suite (not under tests/). "
            "Property: UNTRUSTED_REPOSITORY_CONFIG != EXECUTION_AUTHORITY."
        ),
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-001",),
        class_id="root_auth",
        title="Authorized source-root binding (ingestion)",
        remedi_pr=None,  # #267 on main (shared provenance suite)
        primary_tests=(
            "tests/integration/test_codex_sec_001_002_provenance.py",
        ),
        probe="project_atlas.ingestion:ingest",
        notes="Root-substitution / self-authorize cases share provenance suite (#267).",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-004", "CODEX-SEC-014", "CODEX-SEC-017", "CODEX-SEC-018"),
        class_id="path",
        title="Path containment / Windows-safe components",
        remedi_pr=None,  # #263 on main
        primary_tests=("tests/unit/test_sec_004_018_path_containment.py",),
        probe="atlas_contracts.paths:safe_relative_component",
        notes="Remedi on main (#263). Canonical helpers in atlas_contracts.paths.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-006",),
        class_id="secrets",
        title="Secret import metadata-only / no raw persistence",
        remedi_pr=None,  # #262 on main
        primary_tests=("tests/unit/test_codex_sec_006_secret_import.py",),
        probe="project_atlas.secrets:redact_text",
        notes="Remedi on main (#262). DETECT → ABORT/REDACT → METADATA-ONLY.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-009",),
        class_id="request_auth",
        title="LIVE_API request principal (loopback ≠ auth)",
        remedi_pr=None,  # #264 on main
        primary_tests=("tests/unit/test_as_sec_009_api_auth.py",),
        probe="project_atlas.authz:mint_api_session",
        notes="Remedi on main (#264). Unauthenticated/wrong credential DENY.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-019",),
        class_id="capability",
        title="REQUEST ≠ GRANT ≠ AUTHORIZATION ≠ EXECUTION",
        remedi_pr=None,  # #265 on main
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.authority",
        notes="Remedi on main (#265). Control-plane authority; CLI must not self-grant.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-015",),
        class_id="readiness",
        title="Readiness fail-closed (missing config DENY)",
        remedi_pr=None,  # #265 on main
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.readiness",
        notes="Remedi on main (#265). Missing readiness must DENY, not legacy-authorize.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-016",),
        class_id="receipt",
        title="Receipt authenticity (self-asserted receipt ≠ authority)",
        remedi_pr=None,  # #265 on main
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.receipt_gate",
        notes="Remedi on main (#265). Receipt is evidence, not grant authority.",
    ),
)


REQUIRED_CLASS_IDS: frozenset[str] = frozenset(
    item.class_id for item in SECURITY_REGRESSION_CLASSES
)
