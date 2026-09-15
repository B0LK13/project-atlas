"""Specific-first deterministic source classification (AS-EXT-001A, §7.1).

The legacy keyword classifier (`project_atlas.ingestion.CLASS_RULES`) lets
content keywords such as ``architecture`` and ``design`` override structural
reality — the P0 corpus showed evidence receipts classified as ``validation``
while their YAML structure went unrecognized, contributing to the 29 locator
failures. This module implements the directive §7.1 precedence:

1. explicit recognized schema or type marker;
2. known evidence path/profile;
3. known ADR path/title profile;
4. known work-package path/profile;
5. known backlog, roadmap or WORKLOG path;
6. dedicated YAML/YML source;
7. registered structured YAML-in-Markdown profile;
8. generic Markdown;
9. unsupported/other.

Content keywords never override a more specific structural classification:
they are consulted only inside the generic-Markdown tier as a profile hint.

Every classification records ``source_kind``, ``document_profile``,
``classification_rule``, ``classification_confidence``, and the selected
parser (§7.1). Parser ids are the static dispatch surface of §7.3 —
file-level parser exclusivity, no plugin framework.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from project_atlas.domain.sources import SourceRecord

__all__ = [
    "ClassificationConfidence",
    "ClassificationRecord",
    "ParserSelection",
    "apply_classification_method",
    "classify_source",
]

#: Deterministic confidence that the fired rule identified the source.
ClassificationConfidence = Literal["high", "medium", "low"]

#: Static parser-dispatch surface (§7.3 / AS-D-006). ``none`` means unsupported.
#: Consumed by ``project_atlas.parser_registry``; do not invent plugin ids here.
ParserSelection = Literal[
    "project-manifest", "evidence-yaml", "adr", "verify-profile", "kv-markdown", "none"
]

_EVIDENCE_PATH = re.compile(r"^docs/evidence/[^/]+\.ya?ml$")
_ADR_PATH = re.compile(r"^docs/adr/ADR-[A-Za-z0-9-]+\.md$")
_ADR_TITLE = re.compile(r"^#\s+ADR-\d+", re.M)
_WORK_PACKAGE_PATH = re.compile(r"^docs/work-packages/[^/]+\.md$")
_BACKLOG_PATH = re.compile(r"^docs/backlog\.md$")
_ROADMAP_PATH = re.compile(r"(?:^|/)[^/]*roadmap[^/]*\.md$", re.I)
_WORKLOG_PATH = re.compile(r"^WORKLOG\.md$", re.I)
_YAML_EXTENSION = re.compile(r"\.ya?ml$", re.I)
_MARKDOWN_EXTENSION = re.compile(r"\.md$", re.I)
_PROJECT_MANIFEST = re.compile(r"(?:^|/)\.atlas-project\.yaml$")

# Explicit recognized schema/type marker (precedence tier 1): a YAML mapping
# carrying both a schema version and a recognized receipt type marker.
_SCHEMA_MARKER = re.compile(r"^schema_version\s*:\s*\d+\s*$", re.M)
_RECEIPT_TYPE_MARKER = re.compile(r"^receipt_type\s*:\s*atlas-[A-Za-z0-9-]+\s*$", re.M)

# Registered structured YAML-in-Markdown profiles (§7.6: V1 registered
# profiles only, no unrestricted autodetection).
_REGISTERED_MARKDOWN_PROFILES: tuple[tuple[re.Pattern[str], str, ParserSelection], ...] = (
    (
        re.compile(r"^docs/architecture-governance/VERIFY-[A-Za-z0-9-]+\.md$"),
        "verify-structured",
        "verify-profile",
    ),
)


@dataclass(frozen=True)
class ClassificationRecord:
    """What a source is, how we know, and which parser owns it (§7.1)."""

    source_kind: str
    document_profile: str
    classification_rule: str
    classification_confidence: ClassificationConfidence
    parser_id: ParserSelection


def apply_classification_method(
    source: SourceRecord,
    classification: ClassificationRecord,
) -> SourceRecord:
    """AS-E-006: stamp ``SourceRecord.classification_method`` from EXT rule id.

    Consumes :class:`ClassificationRecord` only — does **not** rewrite EXT-001A
    precedence. Excluded sources keep ``classification_method`` null.
    Unsupported / ``no-matching-rule`` outcomes map to ``unknown`` state.
    """
    from project_atlas.domain.vocabulary import ClassificationState

    if source.classification_state is ClassificationState.EXCLUDED:
        return source.model_copy(update={"classification_method": None})

    method = classification.classification_rule
    if classification.source_kind == "unsupported" or method == "no-matching-rule":
        state = ClassificationState.UNKNOWN
    else:
        state = ClassificationState.CLASSIFIED
    return source.model_copy(
        update={
            "classification_state": state,
            "classification_method": method,
        }
    )


def classify_source(path: str, text: str) -> ClassificationRecord:
    """Classify one source deterministically using specific-first precedence.

    ``path`` is the vault-relative source path; ``text`` is the decoded source
    content. The same input always yields the same record (NFR-001).
    """
    normalized_path = path.replace("\\", "/")

    # Tier 1 — explicit recognized schema or type marker.
    if _PROJECT_MANIFEST.search(normalized_path):
        return ClassificationRecord(
            source_kind="project-manifest",
            document_profile="atlas-project-manifest",
            classification_rule="path:.atlas-project.yaml",
            classification_confidence="high",
            parser_id="project-manifest",
        )
    if _YAML_EXTENSION.search(normalized_path) and (
        _SCHEMA_MARKER.search(text) and _RECEIPT_TYPE_MARKER.search(text)
    ):
        return ClassificationRecord(
            source_kind="evidence-yaml",
            document_profile="atlas-receipt",
            classification_rule="marker:schema_version+receipt_type",
            classification_confidence="high",
            parser_id="evidence-yaml",
        )

    # Tier 2 — known evidence path/profile.
    if _EVIDENCE_PATH.match(normalized_path):
        return ClassificationRecord(
            source_kind="evidence-yaml",
            document_profile="atlas-receipt",
            classification_rule="path:docs/evidence/*.yaml",
            classification_confidence="high",
            parser_id="evidence-yaml",
        )

    # Tier 3 — known ADR path/title profile.
    if _ADR_PATH.match(normalized_path):
        return ClassificationRecord(
            source_kind="adr",
            document_profile="adr",
            classification_rule="path:docs/adr/ADR-*.md",
            classification_confidence="high",
            parser_id="adr",
        )
    if _MARKDOWN_EXTENSION.search(normalized_path) and _ADR_TITLE.search(text):
        return ClassificationRecord(
            source_kind="adr",
            document_profile="adr",
            classification_rule="title:# ADR-NNN",
            classification_confidence="high",
            parser_id="adr",
        )

    # Tier 4 — known work-package path/profile.
    if _WORK_PACKAGE_PATH.match(normalized_path):
        return ClassificationRecord(
            source_kind="work-package",
            document_profile="work-package",
            classification_rule="path:docs/work-packages/*.md",
            classification_confidence="high",
            parser_id="kv-markdown",
        )

    # Tier 5 — known backlog, roadmap or WORKLOG path.
    if _BACKLOG_PATH.match(normalized_path):
        return ClassificationRecord(
            source_kind="backlog",
            document_profile="backlog",
            classification_rule="path:docs/backlog.md",
            classification_confidence="high",
            parser_id="kv-markdown",
        )
    if _WORKLOG_PATH.match(normalized_path):
        return ClassificationRecord(
            source_kind="worklog",
            document_profile="worklog",
            classification_rule="path:WORKLOG.md",
            classification_confidence="high",
            parser_id="kv-markdown",
        )
    if _ROADMAP_PATH.search(normalized_path):
        return ClassificationRecord(
            source_kind="roadmap",
            document_profile="roadmap",
            classification_rule="path:*roadmap*.md",
            classification_confidence="high",
            parser_id="kv-markdown",
        )

    # Tier 6 — dedicated YAML/YML source without a recognized marker.
    if _YAML_EXTENSION.search(normalized_path):
        return ClassificationRecord(
            source_kind="structured-yaml",
            document_profile="unknown-yaml-profile",
            classification_rule="extension:yaml",
            classification_confidence="medium",
            parser_id="evidence-yaml",
        )

    # Tier 7 — registered structured YAML-in-Markdown profile (§7.6).
    for pattern, profile, parser_id in _REGISTERED_MARKDOWN_PROFILES:
        if pattern.match(normalized_path):
            return ClassificationRecord(
                source_kind="structured-markdown",
                document_profile=profile,
                classification_rule=f"registered-profile:{profile}",
                classification_confidence="high",
                parser_id=parser_id,
            )

    # Tier 8 — generic Markdown.
    if _MARKDOWN_EXTENSION.search(normalized_path):
        return ClassificationRecord(
            source_kind="markdown",
            document_profile="generic-markdown",
            classification_rule="extension:md",
            classification_confidence="low",
            parser_id="kv-markdown",
        )

    # Tier 9 — unsupported/other.
    return ClassificationRecord(
        source_kind="unsupported",
        document_profile="unsupported",
        classification_rule="no-matching-rule",
        classification_confidence="high",
        parser_id="none",
    )
