"""Structured evidence compilation orchestration (AS-EXT-001A, §7.3/§7.8/§7.9).

Per-source compilation with failure isolation. Each source is classified
(§7.1), dispatched to its exclusive parser (§7.3 file-level exclusivity),
and yields exactly one per-source outcome (§7.8) plus structured diagnostics
(§7.9):

- COMPLETE_CANDIDATE — extraction succeeded with zero withheld claims; only
  these sources contribute canonical claims (promotion is all-or-nothing per
  source);
- PARTIAL_CANDIDATE — extraction succeeded but at least one claim was
  withheld; staging-only, alters no canonical state, always carries
  diagnostics;
- FAILED — structural parse failure or unsupported source kind; contributes
  nothing and never aborts independent good sources.

Claim Identity v2 (`project_atlas.claim_identity`) remains the sole identity
contract: this module never derives claim ids. It returns boundary records
(`ExtractedRecord`, mirroring the §7.2 parser-output fields) and lets the
knowledge compiler derive identities unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from project_atlas.claim_identity import extract_claims
from project_atlas.classification import ClassificationRecord, classify_source
from project_atlas.compilation import CompilationCandidate, CompilationOutcome
from project_atlas.domain import (
    AmbiguityStatus,
    AuthorityLevel,
    CanonicalImpact,
    ClaimType,
    Diagnostic,
    DiagnosticCode,
    LocatorConfidence,
    LocatorKind,
    ParserOutput,
    Severity,
)
from project_atlas.evidence_profiles import (
    ReceiptFieldClass,
    ReceiptSupportStatus,
    assess_receipt,
    classify_root_key,
)
from project_atlas.verify_profile import parse_verify_document
from project_atlas.yaml_structured import (
    DuplicateKeyError,
    YamlSecurityError,
    iter_leaf_paths,
    load_safe_yaml,
    yaml_path_locator,
)

PARSER_VERSION = "1.0.0"

#: Receipt concept -> (claim type, claim field) for user-facing claim fields
#: (§7.5). Non-claim field classes never become claims.
_RECEIPT_CLAIM_CONCEPTS: dict[str, tuple[ClaimType, str]] = {
    "work-package": (ClaimType.WORK_PACKAGE_STATUS, "work-package"),
    "status": (ClaimType.ROADMAP_STATUS, "status"),
    "title": (ClaimType.WORK_PACKAGE_STATUS, "title"),
}


@dataclass(frozen=True)
class ExtractedRecord:
    """One extracted statement at the parser/compiler boundary (§7.2).

    Carries everything the knowledge compiler needs for Claim Identity v2
    derivation; never carries a claim id.
    """

    claim_type: str
    field: str
    value: str
    locator: str
    parser_id: str
    extraction_method: str
    withheld: bool = False
    predecessor_id: str | None = None


@dataclass(frozen=True)
class SourceExtraction:
    """Per-source structured compilation result (§7.8/§7.9)."""

    candidate: CompilationCandidate
    records: tuple[ExtractedRecord, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    parser_outputs: tuple[ParserOutput, ...] = ()


def _line_locator_kind(locator: str) -> LocatorKind:
    if locator.startswith("id:"):
        return LocatorKind.EXPLICIT_ID
    if locator == "schema:project-manifest":
        return LocatorKind.PROJECT_MANIFEST
    if locator.startswith("schema:"):
        return LocatorKind.SCHEMA_KEY
    if locator.startswith("headingpath:"):
        return LocatorKind.HEADING_PATH
    return LocatorKind.HEADING


def _extract_lines(
    project: str,
    path: str,
    text: str,
    entry: dict[str, Any],
    classification: ClassificationRecord,
) -> SourceExtraction:
    """Line-rule extraction for Markdown-like sources with withholding (§7.7/§7.8)."""
    schema_key = entry.get("schema_key")
    raw_records = extract_claims(
        text,
        schema_key=str(schema_key) if schema_key else None,
        is_project_manifest=classification.parser_id == "project-manifest",
        classification=str(entry.get("classification", "")),
        reject_unresolved=False,
        withhold_unresolvable=True,
    )
    records: list[ExtractedRecord] = []
    parser_outputs: list[ParserOutput] = []
    diagnostics: list[Diagnostic] = []
    messages: list[str] = []
    for raw in raw_records:
        locator = raw["locator"]
        withheld = bool(raw.get("withheld")) or locator is None
        if withheld:
            code = (
                DiagnosticCode.UNRESOLVED_LOCATOR
                if locator is None
                else DiagnosticCode.AMBIGUOUS_IDENTITY
            )
            reason = (
                f"claim withheld: no stable locator for field '{raw['field']}'"
                if locator is None
                else f"claim withheld: unresolvable identity collision at '{locator}'"
            )
            messages.append(reason)
            diagnostics.append(
                Diagnostic(
                    code=code,
                    severity=Severity.WARNING,
                    source_path=path,
                    parser=classification.parser_id,
                    profile=classification.document_profile,
                    subject=project,
                    field=str(raw["field"]),
                    locator=str(locator) if locator else None,
                    reason=reason,
                    remediation=(
                        "add an explicit ID or a stable heading/structured key, "
                        "then re-ingest"
                    ),
                    continued=True,
                    canonical_impact=CanonicalImpact.STAGING_ONLY,
                )
            )
            continue
        records.append(
            ExtractedRecord(
                claim_type=str(raw["claim_type"]),
                field=str(raw["field"]),
                value=str(raw["value"]),
                locator=str(locator),
                parser_id=classification.parser_id,
                # Legacy method string preserved: compiler/migration consistency
                # for line-derived claims is an existing contract (AS-CORE-003).
                extraction_method=f"semantic-locator:{locator}",
                predecessor_id=(
                    str(raw["predecessor_id"]) if raw.get("predecessor_id") else None
                ),
            )
        )
        parser_outputs.append(
            ParserOutput(
                parser_id=classification.parser_id,
                parser_version=PARSER_VERSION,
                source_kind=classification.source_kind,
                document_profile=classification.document_profile,
                claim_type=ClaimType(str(raw["claim_type"])),
                subject=project,
                normalized_field=str(raw["field"]),
                raw_value=str(raw["legacy_value"]),
                normalized_value=str(raw["value"]),
                stable_semantic_locator=str(locator),
                locator_kind=_line_locator_kind(str(locator)),
                locator_confidence=LocatorConfidence.STABLE,
                source_path=path,
                structural_context=tuple(str(part) for part in raw.get("heading_path") or ()),
                authority_hint=AuthorityLevel.INFERRED,
                ambiguity_status=AmbiguityStatus.UNAMBIGUOUS,
            )
        )
    outcome = (
        CompilationOutcome.PARTIAL_CANDIDATE
        if diagnostics
        else CompilationOutcome.COMPLETE_CANDIDATE
    )
    return SourceExtraction(
        candidate=CompilationCandidate(
            source_path=path,
            outcome=outcome,
            claims_extracted=len(records),
            claims_withheld=len(diagnostics),
            diagnostics=tuple(messages),
        ),
        records=tuple(records),
        diagnostics=tuple(diagnostics),
        parser_outputs=tuple(parser_outputs),
    )


def _extract_receipt(
    project: str,
    path: str,
    text: str,
    classification: ClassificationRecord,
) -> SourceExtraction:
    """Bounded safe-YAML receipt extraction with profile assessment (§7.4/§7.5)."""
    try:
        tree = load_safe_yaml(text.encode("utf-8"))
    except YamlSecurityError as exc:
        code = (
            DiagnosticCode.DUPLICATE_YAML_KEY
            if isinstance(exc, DuplicateKeyError)
            else DiagnosticCode.PARSER_FAILURE
        )
        reason = f"receipt rejected by bounded loader: {exc.code}"
        return SourceExtraction(
            candidate=CompilationCandidate(
                source_path=path,
                outcome=CompilationOutcome.FAILED,
                diagnostics=(f"{reason}: {exc}",),
            ),
            diagnostics=(
                Diagnostic(
                    code=code,
                    source_path=path,
                    parser="evidence-yaml",
                    profile=classification.document_profile,
                    reason=f"{reason}: {exc}",
                    remediation="fix the YAML structure and re-ingest",
                    continued=True,
                    canonical_impact=CanonicalImpact.BLOCKED,
                ),
            ),
        )
    assessment = assess_receipt(tree)
    if assessment.status is ReceiptSupportStatus.INVALID:
        reason = "invalid receipt: top level is not a non-empty mapping"
        return SourceExtraction(
            candidate=CompilationCandidate(
                source_path=path,
                outcome=CompilationOutcome.FAILED,
                diagnostics=(reason,),
            ),
            diagnostics=(
                Diagnostic(
                    code=DiagnosticCode.INVALID_RECEIPT,
                    source_path=path,
                    parser="evidence-yaml",
                    profile=classification.document_profile,
                    reason=reason,
                    remediation="provide a mapping receipt document and re-ingest",
                    continued=True,
                    canonical_impact=CanonicalImpact.BLOCKED,
                ),
            ),
        )

    records: list[ExtractedRecord] = []
    parser_outputs: list[ParserOutput] = []
    diagnostics: list[Diagnostic] = []
    messages: list[str] = []
    if assessment.status is ReceiptSupportStatus.UNKNOWN_PROFILE:
        reason = "unknown receipt profile: no known receipt_type or signature"
        messages.append(reason)
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.UNKNOWN_RECEIPT_PROFILE,
                severity=Severity.WARNING,
                source_path=path,
                parser="evidence-yaml",
                profile=classification.document_profile,
                reason=reason,
                remediation="register the receipt profile or add a recognized marker",
                continued=True,
                canonical_impact=CanonicalImpact.NONE,
            )
        )
    unknown_count = assessment.counts.get(
        ReceiptFieldClass.UNKNOWN_STRUCTURED_METADATA.value, 0
    )
    if unknown_count:
        reason = (
            f"{unknown_count} unknown structured field(s) preserved as metadata; "
            "they never become claims"
        )
        messages.append(reason)
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.UNKNOWN_STRUCTURED_FIELD,
                severity=Severity.WARNING,
                source_path=path,
                parser="evidence-yaml",
                profile=classification.document_profile,
                reason=reason,
                continued=True,
                canonical_impact=CanonicalImpact.NONE,
            )
        )

    for leaf_path, value in iter_leaf_paths(tree):
        key_path = tuple(str(element) for element in leaf_path)
        concept, field_class = classify_root_key(key_path[0])
        if field_class is not ReceiptFieldClass.USER_FACING_CLAIM or concept is None:
            continue
        claim_type, claim_field = _RECEIPT_CLAIM_CONCEPTS[concept]
        normalized = " ".join(("" if value is None else str(value)).split())
        if not normalized:
            continue
        locator = yaml_path_locator(leaf_path)
        confidence = (
            LocatorConfidence.PROVISIONAL
            if any(isinstance(element, int) for element in leaf_path)
            else LocatorConfidence.STABLE
        )
        records.append(
            ExtractedRecord(
                claim_type=claim_type.value,
                field=claim_field,
                value=normalized,
                locator=locator,
                parser_id="evidence-yaml",
                extraction_method=f"evidence-yaml:{locator}",
            )
        )
        parser_outputs.append(
            ParserOutput(
                parser_id="evidence-yaml",
                parser_version=PARSER_VERSION,
                source_kind=classification.source_kind,
                document_profile=classification.document_profile,
                claim_type=claim_type,
                subject=project,
                normalized_field=claim_field,
                raw_value="" if value is None else str(value),
                normalized_value=normalized,
                stable_semantic_locator=locator,
                locator_kind=LocatorKind.YAMLPATH,
                locator_confidence=confidence,
                source_path=path,
                structural_context=key_path[:-1],
                authority_hint=AuthorityLevel.MAINTAINED,
                ambiguity_status=AmbiguityStatus.UNAMBIGUOUS,
            )
        )
    return SourceExtraction(
        candidate=CompilationCandidate(
            source_path=path,
            outcome=CompilationOutcome.COMPLETE_CANDIDATE,
            claims_extracted=len(records),
            diagnostics=tuple(messages),
        ),
        records=tuple(records),
        diagnostics=tuple(diagnostics),
        parser_outputs=tuple(parser_outputs),
    )


def _extract_verify(
    project: str,
    path: str,
    text: str,
    classification: ClassificationRecord,
) -> SourceExtraction:
    """Registered VERIFY structured-document extraction (§7.6)."""
    result = parse_verify_document(text, source_path=path)
    if not result.records:
        failure_diagnostics = tuple(
            Diagnostic(
                code=DiagnosticCode.PARSER_FAILURE,
                source_path=path,
                parser="verify-profile",
                profile=classification.document_profile,
                reason=message,
                remediation="repair the VERIFY metadata block and re-ingest",
                continued=True,
                canonical_impact=CanonicalImpact.BLOCKED,
            )
            for message in result.diagnostics
        )
        return SourceExtraction(
            candidate=CompilationCandidate(
                source_path=path,
                outcome=CompilationOutcome.FAILED,
                diagnostics=tuple(result.diagnostics),
            ),
            diagnostics=failure_diagnostics,
        )
    diagnostics: list[Diagnostic] = []
    messages: list[str] = []
    if result.metadata_paths:
        reason = (
            f"{len(result.metadata_paths)} non-claim structured field(s) "
            "preserved as visible metadata"
        )
        messages.append(reason)
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.UNKNOWN_STRUCTURED_FIELD,
                severity=Severity.WARNING,
                source_path=path,
                parser="verify-profile",
                profile=classification.document_profile,
                reason=reason,
                continued=True,
                canonical_impact=CanonicalImpact.NONE,
            )
        )
    records = tuple(
        ExtractedRecord(
            claim_type=output.claim_type.value,
            field=output.normalized_field,
            value=output.normalized_value,
            locator=output.stable_semantic_locator,
            parser_id="verify-profile",
            extraction_method=f"verify-profile:{output.stable_semantic_locator}",
        )
        for output in result.records
    )
    return SourceExtraction(
        candidate=CompilationCandidate(
            source_path=path,
            outcome=CompilationOutcome.COMPLETE_CANDIDATE,
            claims_extracted=len(records),
            diagnostics=tuple(messages),
        ),
        records=records,
        diagnostics=tuple(diagnostics),
        parser_outputs=tuple(result.records),
    )


def _unsupported(
    path: str, classification: ClassificationRecord
) -> SourceExtraction:
    """Unsupported source kinds stay visible and never abort the batch (§7.1)."""
    reason = f"unsupported source kind: {classification.document_profile}"
    return SourceExtraction(
        candidate=CompilationCandidate(
            source_path=path,
            outcome=CompilationOutcome.FAILED,
            diagnostics=(reason,),
        ),
        diagnostics=(
            Diagnostic(
                code=DiagnosticCode.UNSUPPORTED_SOURCE_KIND,
                severity=Severity.WARNING,
                source_path=path,
                parser="none",
                profile=classification.document_profile,
                reason=reason,
                remediation="register a structured profile or add a recognized marker",
                continued=True,
                canonical_impact=CanonicalImpact.BLOCKED,
            ),
        ),
    )


def extract_source(project: str, entry: dict[str, Any]) -> SourceExtraction:
    """Compile one source entry in isolation (§7.8: zero whole-batch abort).

    Any unexpected parser error is converted into a FAILED candidate with a
    PARSER_FAILURE diagnostic so one bad source can never prevent extraction
    from independent good sources.
    """
    path = str(entry.get("path", ""))
    text = str(entry.get("text", ""))
    classification = classify_source(path, text)
    try:
        if classification.parser_id == "evidence-yaml":
            return _extract_receipt(project, path, text, classification)
        if classification.parser_id == "verify-profile":
            return _extract_verify(project, path, text, classification)
        if classification.parser_id == "none":
            return _unsupported(path, classification)
        return _extract_lines(project, path, text, entry, classification)
    except Exception as exc:  # deliberate failure-isolation boundary (§7.8)
        reason = f"unhandled parser error: {type(exc).__name__}: {exc}"
        return SourceExtraction(
            candidate=CompilationCandidate(
                source_path=path,
                outcome=CompilationOutcome.FAILED,
                diagnostics=(reason,),
            ),
            diagnostics=(
                Diagnostic(
                    code=DiagnosticCode.PARSER_FAILURE,
                    source_path=path,
                    parser=classification.parser_id,
                    profile=classification.document_profile,
                    reason=reason,
                    remediation="report the parser defect; the source is withheld",
                    continued=True,
                    canonical_impact=CanonicalImpact.BLOCKED,
                ),
            ),
        )
