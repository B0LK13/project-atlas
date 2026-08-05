"""Evidence receipt profiles (AS-EXT-001A, directive §7.5).

The 31 real receipts are schema-heterogeneous: 231 distinct top-level keys,
0 universal keys, ``status`` in 28/31, ``receipt_type`` in 13/31 (P0
synthesis §6). One rigid universal receipt schema cannot work. This module
implements:

- COMMON SEMANTIC CONCEPT MAPPING — work package, status, implementation
  state, review state, certification state, merge authorization, validation
  results, supersession, limitations, candidate/base/commit provenance;
- PROFILE-SPECIFIC ADAPTERS — a known receipt-type registry plus a strict
  profile signature (mapping + schema marker + common receipt keys) as the
  false-positive control;
- UNKNOWN STRUCTURED FIELD PRESERVATION — unknown fields stay visible as
  UNKNOWN STRUCTURED METADATA; they are never dropped and never become
  claims.

Every receipt receives exactly one support status: ``recognized``,
``partially-recognized``, ``unknown-profile``, or ``invalid``. No evidence
receipt ever falls back to generic Markdown or line-regex parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from project_atlas.yaml_structured import (
    DEFAULT_YAML_LIMITS,
    YamlSecurityError,
    iter_leaf_paths,
    load_safe_yaml,
    yaml_path_locator,
)


class ReceiptFieldClass(StrEnum):
    """Field classification per directive §7.5."""

    USER_FACING_CLAIM = "user-facing-claim"
    PROVENANCE_METADATA = "provenance-metadata"
    EVIDENCE_METADATA = "evidence-metadata"
    UNKNOWN_STRUCTURED_METADATA = "unknown-structured-metadata"
    DIAGNOSTIC_ONLY = "diagnostic-only"


class ReceiptSupportStatus(StrEnum):
    """Per-receipt support/profile status (§7.5)."""

    RECOGNIZED = "recognized"
    PARTIALLY_RECOGNIZED = "partially-recognized"
    UNKNOWN_PROFILE = "unknown-profile"
    INVALID = "invalid"


#: Known receipt-type registry (observed across the 31-receipt P0 corpus).
KNOWN_RECEIPT_TYPES: frozenset[str] = frozenset(
    {
        "atlas-core-certification",
        "atlas-core-milestone",
        "atlas-core-work-package",
        "atlas-integration-certification",
        "atlas-integration-work-package",
        "isolated-technical-review",
        "isolated-technical-review-addendum",
        "v2-identity-candidate-evidence",
        "v2-identity-remediation",
    }
)

#: Root-key concept map: key -> (common semantic concept, field class).
#: Nested leaves inherit their root segment's classification.
_ROOT_CONCEPTS: dict[str, tuple[str, ReceiptFieldClass]] = {
    # User-facing claims (P0 synthesis §6).
    "package": ("work-package", ReceiptFieldClass.USER_FACING_CLAIM),
    "work_package": ("work-package", ReceiptFieldClass.USER_FACING_CLAIM),
    "work_package_id": ("work-package", ReceiptFieldClass.USER_FACING_CLAIM),
    "status": ("status", ReceiptFieldClass.USER_FACING_CLAIM),
    "title": ("title", ReceiptFieldClass.USER_FACING_CLAIM),
    # Evidence metadata: profile markers and receipt-state blocks.
    "schema_version": ("profile-marker", ReceiptFieldClass.EVIDENCE_METADATA),
    "receipt_type": ("profile-marker", ReceiptFieldClass.EVIDENCE_METADATA),
    "scope": ("scope", ReceiptFieldClass.EVIDENCE_METADATA),
    "implementation_state": ("implementation-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "review": ("review-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "governor_review": ("review-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "independent_verification": ("review-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "architecture": ("review-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "certification": ("certification-state", ReceiptFieldClass.EVIDENCE_METADATA),
    "merge_authorized": ("merge-authorization", ReceiptFieldClass.EVIDENCE_METADATA),
    "merge_authorization": ("merge-authorization", ReceiptFieldClass.EVIDENCE_METADATA),
    "superseded_by": ("supersession", ReceiptFieldClass.EVIDENCE_METADATA),
    "supersedes": ("supersession", ReceiptFieldClass.EVIDENCE_METADATA),
    "supersession": ("supersession", ReceiptFieldClass.EVIDENCE_METADATA),
    "limitations": ("limitations", ReceiptFieldClass.EVIDENCE_METADATA),
    "known_limitations": ("limitations", ReceiptFieldClass.EVIDENCE_METADATA),
    "deferred_items": ("limitations", ReceiptFieldClass.EVIDENCE_METADATA),
    # Candidate/base/commit provenance.
    "candidate": ("candidate-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    "branch": ("commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    "base_commit": ("commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    "previous_certified_mainline": ("commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    "historical_references": ("commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    "milestone_tag": ("commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA),
    # Diagnostic-only detail blocks (P0 synthesis §6).
    "validation": ("validation-results", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "test_accounting": ("validation-results", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "control_plane": ("control-plane-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "transaction": ("transaction-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "transaction_probe": ("transaction-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "identity": ("identity-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "authority": ("authority-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
    "conflicts": ("conflict-detail", ReceiptFieldClass.DIAGNOSTIC_ONLY),
}

#: Keys proving receipt shape for the profile signature (false-positive
#: control): a mapping must carry a schema marker and at least two of these.
_SIGNATURE_KEYS: frozenset[str] = frozenset(
    {"status", "validation", "package", "work_package", "work_package_id", "branch", "title"}
)


def classify_root_key(key: str) -> tuple[str | None, ReceiptFieldClass]:
    """Classify one top-level receipt key into concept + field class."""
    mapped = _ROOT_CONCEPTS.get(key)
    if mapped is not None:
        return mapped
    if key.endswith("_commit"):
        return "commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA
    if key.endswith("_at"):
        # Timestamp provenance such as merged_to_main_at (2/31 files).
        return "commit-provenance", ReceiptFieldClass.PROVENANCE_METADATA
    return None, ReceiptFieldClass.UNKNOWN_STRUCTURED_METADATA


def _profile_id(tree: dict[Any, Any]) -> str | None:
    receipt_type = tree.get("receipt_type")
    if isinstance(receipt_type, str) and (
        receipt_type in KNOWN_RECEIPT_TYPES or receipt_type.startswith("atlas-")
    ):
        return receipt_type
    # Signature fallback: schema marker + common receipt keys (receipt_type
    # exists in only 13/31 real receipts, so it cannot be required).
    if "schema_version" in tree:
        hits = sum(1 for key in _SIGNATURE_KEYS if key in tree) + sum(
            1 for key in tree if isinstance(key, str) and key.endswith("_commit")
        )
        if hits >= 2:
            receipt_type_text = receipt_type if isinstance(receipt_type, str) else "unsigned"
            return f"atlas-receipt-signature:{receipt_type_text}"
    return None


@dataclass(frozen=True)
class ReceiptFieldAssessment:
    """One classified leaf field; unknown fields remain visible (§7.5)."""

    path: tuple[str, ...]
    locator: str
    key: str
    concept: str | None
    field_class: ReceiptFieldClass


@dataclass(frozen=True)
class ReceiptAssessment:
    """Support status + classified fields + diagnostics for one receipt."""

    status: ReceiptSupportStatus
    profile_id: str | None
    fields: tuple[ReceiptFieldAssessment, ...]
    diagnostics: tuple[str, ...]

    @property
    def counts(self) -> dict[str, int]:
        """Field-class tallies for compilation counters and reporting."""
        tally: dict[str, int] = {}
        for field in self.fields:
            tally[field.field_class.value] = tally.get(field.field_class.value, 0) + 1
        return tally


def assess_receipt(tree: Any) -> ReceiptAssessment:
    """Classify a parsed YAML document into a receipt assessment (§7.5)."""
    if not isinstance(tree, dict) or not tree:
        return ReceiptAssessment(
            status=ReceiptSupportStatus.INVALID,
            profile_id=None,
            fields=(),
            diagnostics=("invalid receipt: top level is not a non-empty mapping",),
        )

    profile = _profile_id(tree)
    fields: list[ReceiptFieldAssessment] = []
    unknown = 0
    for path, _value in iter_leaf_paths(tree):
        key_path = tuple(str(element) for element in path)
        concept, field_class = classify_root_key(key_path[0])
        if field_class is ReceiptFieldClass.UNKNOWN_STRUCTURED_METADATA:
            unknown += 1
        fields.append(
            ReceiptFieldAssessment(
                path=key_path,
                locator=yaml_path_locator(path),
                key=key_path[-1],
                concept=concept,
                field_class=field_class,
            )
        )

    diagnostics: list[str] = []
    if profile is None:
        diagnostics.append("unknown receipt profile: no known receipt_type or signature")
        status = ReceiptSupportStatus.UNKNOWN_PROFILE
    elif unknown:
        diagnostics.append(
            f"partially recognized receipt: {unknown} unknown structured field(s) preserved"
        )
        status = ReceiptSupportStatus.PARTIALLY_RECOGNIZED
    else:
        status = ReceiptSupportStatus.RECOGNIZED
    return ReceiptAssessment(
        status=status,
        profile_id=profile,
        fields=tuple(fields),
        diagnostics=tuple(diagnostics),
    )


def assess_receipt_bytes(data: bytes, limits: Any = DEFAULT_YAML_LIMITS) -> ReceiptAssessment:
    """Parse and assess one receipt; parse/security failures become INVALID.

    INVALID always carries the underlying error code as a diagnostic — a
    rejected input is never silently skipped (§8).
    """
    try:
        tree = load_safe_yaml(data, limits)
    except YamlSecurityError as exc:
        return ReceiptAssessment(
            status=ReceiptSupportStatus.INVALID,
            profile_id=None,
            fields=(),
            diagnostics=(f"invalid receipt: {exc.code}: {exc}",),
        )
    return assess_receipt(tree)
