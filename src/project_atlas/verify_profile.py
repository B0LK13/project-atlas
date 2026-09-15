"""Registered VERIFY structured document profile (AS-EXT-001A, directive §7.6).

The real VERIFY document (`docs/architecture-governance/VERIFY-*.md`) is
Markdown whose body opens with an unfenced YAML-like metadata block. The
legacy line parser sees repeated sibling keys (``status:`` at lines 3/22/30,
``merge_authorized: false`` at lines 25/33) under one nearest heading and
fails closed with ``ambiguous identity boundary``.

This registered profile parses the leading metadata block structurally
(bounded safe YAML, §8) and emits parser records with block-scoped subjects
and canonical ``yamlpath:`` locators. Expected output includes distinct
subjects and locators for ``status``, ``decision``,
``verify_disposition.status``, and ``as_ret_disposition.status`` — zero
collision, zero false semantic conflict, zero whole-run abort. No one-off
line numbers or claim values are embedded in locators. V1 supports registered
profiles only; there is no unrestricted YAML-in-Markdown autodetection (§7.3,
file-level parser exclusivity).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from project_atlas.domain import (
    AmbiguityStatus,
    AuthorityLevel,
    ClaimType,
    LocatorConfidence,
    LocatorKind,
    ParserOutput,
    SemanticSubject,
    SourceSpan,
)
from project_atlas.status_dimensions import refine_status_dimension
from project_atlas.yaml_structured import (
    YamlSecurityError,
    iter_leaf_paths,
    load_safe_yaml,
    yaml_path_locator,
)

PARSER_ID = "verify-profile"
PARSER_VERSION = "1.0.0"

_HEADING = re.compile(r"^#{1,6}\s")

#: Claim fields of the VERIFY profile: path -> (claim_type, raw_field, block_subject).
#: Block subjects remain distinct so repeated sibling keys never collide (§7.6).
#: AS-CORE-004 serializes them as ``review:<block>`` and refines status dimensions.
_CLAIM_FIELDS: dict[tuple[str, ...], tuple[ClaimType, str, str]] = {
    ("status",): (ClaimType.ROADMAP_STATUS, "status", "verify"),
    ("decision",): (ClaimType.DECISION, "decision", "verify"),
    ("verify_disposition", "status"): (
        ClaimType.ROADMAP_STATUS,
        "status",
        "verify-disposition",
    ),
    ("as_ret_disposition", "status"): (
        ClaimType.ROADMAP_STATUS,
        "status",
        "as-ret-disposition",
    ),
}


@dataclass(frozen=True)
class VerifyProfileResult:
    """Structured parse result: claims, visible metadata, diagnostics."""

    records: tuple[ParserOutput, ...]
    metadata_paths: tuple[str, ...]
    diagnostics: tuple[str, ...]


def _metadata_block(text: str) -> tuple[str, int] | None:
    """Return the unfenced YAML-like block after the H1 and its line offset.

    The block runs from the first line after the document H1 to the next
    heading of any level. Returns ``None`` when no H1-led block exists.
    """
    lines = text.splitlines()
    h1 = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if h1 is None:
        return None
    end = next(
        (i for i in range(h1 + 1, len(lines)) if _HEADING.match(lines[i])),
        len(lines),
    )
    block = "\n".join(lines[h1 + 1 : end])
    if not block.strip():
        return None
    return block, h1 + 2  # 1-based line number of the block start


def parse_verify_document(text: str, *, source_path: str) -> VerifyProfileResult:
    """Parse one registered VERIFY document into parser records (§7.6).

    Parse failures produce diagnostics, never exceptions: the profile must
    not abort an independent run (§7.6 zero whole-run abort).
    """
    located = _metadata_block(text)
    if located is None:
        return VerifyProfileResult(
            records=(),
            metadata_paths=(),
            diagnostics=("verify profile: no H1-led metadata block found",),
        )
    block, block_start = located
    try:
        tree = load_safe_yaml(block.encode("utf-8"))
    except YamlSecurityError as exc:
        return VerifyProfileResult(
            records=(),
            metadata_paths=(),
            diagnostics=(f"verify profile: metadata block rejected: {exc.code}: {exc}",),
        )
    if not isinstance(tree, dict):
        return VerifyProfileResult(
            records=(),
            metadata_paths=(),
            diagnostics=("verify profile: metadata block is not a mapping",),
        )

    records: list[ParserOutput] = []
    metadata: list[str] = []
    block_lines = block.splitlines()
    for path, value in iter_leaf_paths(tree):
        key_path = tuple(str(element) for element in path)
        locator = yaml_path_locator(path)
        claim = _CLAIM_FIELDS.get(key_path)
        scalar = "" if value is None else str(value)
        if claim is None:
            # Non-claim structured fields stay visible as metadata (§7.5
            # unknown-field preservation applied to the profile as well).
            metadata.append(locator)
            continue
        claim_type, raw_field, block_subject = claim
        subject = SemanticSubject.review(block_subject).serialize()
        dimension = refine_status_dimension(
            field=raw_field,
            subject=subject,
            structural_path=key_path,
            profile="verify-structured",
        )
        field = dimension.field
        span = SourceSpan()
        if len(key_path) == 1:
            top_line = next(
                (
                    index
                    for index, line in enumerate(block_lines)
                    if re.match(rf"^{re.escape(key_path[0])}\s*:", line)
                ),
                None,
            )
            if top_line is not None:
                line_number = block_start + top_line
                span = SourceSpan(start_line=line_number, end_line=line_number)
        records.append(
            ParserOutput(
                parser_id=PARSER_ID,
                parser_version=PARSER_VERSION,
                source_kind="structured-markdown",
                document_profile="verify-structured",
                claim_type=claim_type,
                subject=subject,
                normalized_field=field,
                raw_value=scalar,
                normalized_value=" ".join(scalar.split()),
                stable_semantic_locator=locator,
                locator_kind=LocatorKind.YAMLPATH,
                locator_confidence=LocatorConfidence.STABLE,
                source_path=source_path,
                source_span=span,
                structural_context=key_path[:-1],
                authority_hint=AuthorityLevel.MAINTAINED,
                ambiguity_status=AmbiguityStatus.UNAMBIGUOUS,
            )
        )
    return VerifyProfileResult(
        records=tuple(records),
        metadata_paths=tuple(metadata),
        diagnostics=(),
    )
