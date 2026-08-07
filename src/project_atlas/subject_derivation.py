"""Per-record semantic subject derivation (AS-CORE-004 S2).

Priority (fail closed — never silent ``subject = project`` fallback):

1. explicit semantic ID
2. registered profile-specific semantic identifier
3. structured stable semantic identifier
4. durable source identity for generic documents
5. unresolved / ambiguous semantic-subject diagnostic

Source path is provenance, not semantic identity. Generic documents use
``doc:<source_id>`` (or equivalent durable source identity).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from project_atlas.classification import ClassificationRecord
from project_atlas.domain import (
    SemanticSubject,
    SemanticSubjectError,
    SemanticSubjectKind,
    normalize_subject_key,
)

#: ADR id from path or H1 title.
_ADR_ID = re.compile(r"(ADR-\d+)", re.I)

#: Work-package / package ids used across Atlas corpora.
_WP_ID = re.compile(r"\b(AS-[A-Z]+-\d+[A-Z]?)\b")

#: Explicit semantic id markers in markdown / yaml text.
#: Key charset validated by :func:`normalize_subject_key` (Unicode letters ok).
_EXPLICIT_SUBJECT = re.compile(
    r"(?im)^(?:semantic[_-]?subject|subject[_-]?id|stable[_-]?id)\s*:\s*"
    r"(\S+)\s*$"
)
_EXPLICIT_KIND = re.compile(
    r"(?im)^(?:semantic[_-]?kind|subject[_-]?kind)\s*:\s*"
    r"(project|wp|adr|doc|review|experiment|roadmap-item|evidence)\s*$"
)

_RECEIPT_WP_KEYS = frozenset({"work_package", "work_package_id", "package", "work-package"})


@dataclass(frozen=True)
class SubjectDerivationResult:
    """Outcome of deriving one semantic subject."""

    subject: SemanticSubject | None
    reason: str | None = None
    ambiguous: bool = False

    @property
    def resolved(self) -> bool:
        return self.subject is not None and not self.ambiguous

    def serialized(self) -> str | None:
        if self.subject is None:
            return None
        return self.subject.serialize()


def _safe_subject(kind: SemanticSubjectKind, key: str) -> SubjectDerivationResult:
    try:
        subject = SemanticSubject(kind=kind, key=normalize_subject_key(key))
    except (SemanticSubjectError, ValueError) as exc:
        return SubjectDerivationResult(
            subject=None,
            reason=f"invalid semantic subject key: {exc}",
            ambiguous=True,
        )
    return SubjectDerivationResult(subject=subject)


def _durable_document_subject(source_id: str) -> SubjectDerivationResult:
    key = source_id.strip()
    if not key:
        return SubjectDerivationResult(
            subject=None,
            reason="missing durable source identity for document subject",
            ambiguous=True,
        )
    return _safe_subject(SemanticSubjectKind.DOCUMENT, key)


def _explicit_from_text(text: str) -> SubjectDerivationResult | None:
    key_match = _EXPLICIT_SUBJECT.search(text)
    if key_match is None:
        return None
    kind_match = _EXPLICIT_KIND.search(text)
    kind_token = kind_match.group(1).lower() if kind_match else "doc"
    kind = SemanticSubjectKind(kind_token)
    return _safe_subject(kind, key_match.group(1))


def _adr_id(path: str, text: str) -> str | None:
    normalized = path.replace("\\", "/")
    for candidate in (_ADR_ID.search(normalized), _ADR_ID.search(text)):
        if candidate is None:
            continue
        digits = re.search(r"(\d+)", candidate.group(1))
        if digits:
            return f"ADR-{digits.group(1)}"
    return None


def _work_package_id_from_path(path: str) -> str | None:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    match = _WP_ID.search(stem)
    return match.group(1) if match else None


def _work_package_id_from_text(text: str) -> str | None:
    # Prefer explicit package header fields.
    for pattern in (
        r"(?im)^(?:work[_-]?package(?:_id)?|package)\s*:\s*(AS-[A-Z]+-\d+[A-Z]?)\s*$",
        r"(?im)^#\s*(AS-[A-Z]+-\d+[A-Z]?)\b",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    match = _WP_ID.search(text)
    return match.group(1) if match else None


def _receipt_work_package_id(tree: dict[str, Any] | None) -> str | None:
    if not isinstance(tree, dict):
        return None
    for key, value in tree.items():
        if str(key) in _RECEIPT_WP_KEYS and isinstance(value, str):
            match = _WP_ID.search(value)
            if match:
                return match.group(1)
    return None


def derive_semantic_subject(
    *,
    project: str,
    source_id: str,
    path: str,
    text: str,
    classification: ClassificationRecord,
    receipt_tree: dict[str, Any] | None = None,
    verify_block_subject: str | None = None,
) -> SubjectDerivationResult:
    """Derive the semantic subject for one source / record context."""
    # 1. Explicit semantic ID in source text.
    explicit = _explicit_from_text(text)
    if explicit is not None:
        return explicit

    parser_id = classification.parser_id
    profile = classification.document_profile

    # 2/3. Profile-specific / structured stable identifiers.
    if parser_id == "project-manifest" or profile == "atlas-project-manifest":
        return _safe_subject(SemanticSubjectKind.PROJECT, project)

    if parser_id == "adr" or profile == "adr":
        adr_id = _adr_id(path, text)
        if adr_id is None:
            return SubjectDerivationResult(
                subject=None,
                reason="ADR source missing stable ADR-NNN identifier",
                ambiguous=True,
            )
        return _safe_subject(SemanticSubjectKind.ADR, adr_id)

    if profile == "work-package" or classification.source_kind == "work-package":
        wp_id = _work_package_id_from_path(path) or _work_package_id_from_text(text)
        if wp_id is None:
            return SubjectDerivationResult(
                subject=None,
                reason="work-package source missing stable package identifier",
                ambiguous=True,
            )
        return _safe_subject(SemanticSubjectKind.WORK_PACKAGE, wp_id)

    if parser_id == "evidence-yaml":
        wp_id = _receipt_work_package_id(receipt_tree) or _work_package_id_from_text(text)
        if wp_id is not None:
            # Receipt is evidence *about* the work package, not the subject itself.
            return _safe_subject(SemanticSubjectKind.WORK_PACKAGE, wp_id)
        return _durable_document_subject(source_id)

    if parser_id == "verify-profile":
        # Preserve VERIFY block-scoped collision avoidance as review subjects
        # until status-dimension refinement (S3) can separate fields.
        if verify_block_subject:
            key = verify_block_subject.replace("_", "-")
            return _safe_subject(SemanticSubjectKind.REVIEW, key)
        return _durable_document_subject(source_id)

    if profile in {"roadmap", "backlog"}:
        # Item-level IDs are optional; durable document subject is safe default.
        return _durable_document_subject(source_id)

    # 4. Durable source identity for generic documents.
    if parser_id in {"kv-markdown", "project-manifest"} or classification.source_kind in {
        "markdown",
        "worklog",
        "roadmap",
        "backlog",
    }:
        return _durable_document_subject(source_id)

    # 5. Unresolved — do not silently fall back to project.
    return SubjectDerivationResult(
        subject=None,
        reason=(
            f"unable to derive semantic subject for profile "
            f"{profile!r} / parser {parser_id!r}"
        ),
        ambiguous=True,
    )


def detect_duplicate_semantic_subjects(
    assignments: list[tuple[str, str, str]],
) -> list[tuple[str, str, tuple[str, ...]]]:
    """Fail closed on illegitimate duplicate stable subject IDs.

    ``assignments`` entries are ``(source_id, path, serialized_subject)``.
    Returns list of ``(serialized_subject, kind_key, source_ids)`` collisions
    where the same non-project semantic subject is defined by multiple sources.

    Ordering of inputs must not affect which collision is reported — never
    pick a winner by path sort, mtime, or parser order.
    """
    by_subject: dict[str, set[str]] = {}
    for source_id, _path, serialized in assignments:
        if serialized.startswith("project:"):
            continue
        by_subject.setdefault(serialized, set()).add(source_id)
    collisions: list[tuple[str, str, tuple[str, ...]]] = []
    for serialized, sources in sorted(by_subject.items()):
        if len(sources) > 1:
            collisions.append((serialized, serialized, tuple(sorted(sources))))
    return collisions
