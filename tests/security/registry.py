"""Canonical map of Alpha security regression classes → remedi owners.

STATUS values here are suite-seed bookkeeping only.
They are NOT Codex validation outcomes.
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
    """Open remedi PR number as string, or None if still landing."""

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
        remedi_pr=None,  # S02 still finishing
        primary_tests=(
            "tests/integration/test_codex_sec_001_002_provenance.py",
        ),
        probe="project_atlas.ingestion:ingest",
        notes=(
            "S02 landing tests under tests/integration/test_codex_sec_001_002_provenance.py. "
            "Invariant: PROMOTED_BYTES_SHA256 == APPROVED_PROVENANCE_SHA256; "
            "manifest root must not self-authorize."
        ),
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-021",),
        class_id="trusted_exec",
        title="Trusted normalizer / executable selection",
        remedi_pr="261",
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec021_trusted_exec.py",
        ),
        probe="atlas-vault-documentation.internal.trusted_exec:authorize_executable",
        notes=(
            "Control-plane suite (not under tests/). Property: "
            "UNTRUSTED_REPOSITORY_CONFIG != EXECUTION_AUTHORITY."
        ),
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-001",),
        class_id="root_auth",
        title="Authorized source-root binding (ingestion)",
        remedi_pr=None,  # covered with provenance in S02
        primary_tests=(
            "tests/integration/test_codex_sec_001_002_provenance.py",
        ),
        probe="project_atlas.ingestion:ingest",
        notes="Root-substitution / self-authorize cases share S02 provenance suite.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-004", "CODEX-SEC-014", "CODEX-SEC-017", "CODEX-SEC-018"),
        class_id="path",
        title="Path containment / Windows-safe components",
        remedi_pr="263",
        primary_tests=("tests/unit/test_sec_004_018_path_containment.py",),
        probe="atlas_contracts.paths:safe_relative_component",
        notes="Canonical helpers in atlas_contracts.paths (#263).",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-006",),
        class_id="secrets",
        title="Secret import metadata-only / no raw persistence",
        remedi_pr="262",
        primary_tests=("tests/unit/test_codex_sec_006_secret_import.py",),
        probe="project_atlas.secrets:redact_text",
        notes="DETECT → ABORT/REDACT → METADATA-ONLY; synthetic credentials only.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-009",),
        class_id="request_auth",
        title="LIVE_API request principal (loopback ≠ auth)",
        remedi_pr="264",
        primary_tests=("tests/unit/test_as_sec_009_api_auth.py",),
        probe="project_atlas.authz:mint_api_session",
        notes="Unauthenticated/wrong credential DENY; read≠mutate; privileged explicit.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-019",),
        class_id="capability",
        title="REQUEST ≠ GRANT ≠ AUTHORIZATION ≠ EXECUTION",
        remedi_pr="265",
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.authority",
        notes="Control-plane authority issuance (#265); CLI must not self-grant.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-015",),
        class_id="readiness",
        title="Readiness fail-closed (missing config DENY)",
        remedi_pr="265",
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.readiness",
        notes="Missing readiness must DENY, not legacy-authorize.",
    ),
    SecurityRegressionClass(
        finding_ids=("CODEX-SEC-016",),
        class_id="receipt",
        title="Receipt authenticity (self-asserted receipt ≠ authority)",
        remedi_pr="265",
        primary_tests=(
            "atlas-vault-documentation/tests/test_sec_015_016_019_authority.py",
        ),
        probe="atlas-vault-documentation.agent_control.receipt_gate",
        notes="Receipt is evidence, not grant authority.",
    ),
)


REQUIRED_CLASS_IDS: frozenset[str] = frozenset(
    item.class_id for item in SECURITY_REGRESSION_CLASSES
)
