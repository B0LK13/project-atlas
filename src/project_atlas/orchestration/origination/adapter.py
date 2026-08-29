"""Generic extraction adapter — NORMAL PROJECT SOURCES -> SourceFact.

Reads a project's own working tree directly (never the Atlas vault
ingestion path -- see ADR-033 "MISSING_BOUNDARY" §3 for why: the semantic
compiler does not currently carry a source document's fenced roadmap
record through into a compiled ``project.md``, and that gap is an
owner-reserved product decision this adapter deliberately routes around).

Reuses the existing, already-correct pure parsing helpers from
``project_atlas.project_roadmap`` (``_parse_fenced_record``,
``_evidence_exists``, ``_normalize_status``, ``_normalize_lifecycle``) --
none of which are vault-coupled at the function-signature level; only
``_load_roadmap_source`` (not imported here) hard-codes the vault path
convention this adapter deliberately does not use.

TASK_017_SPECIAL_CASES = 0: nothing below matches on "TASK-017", a
project name, or any Gamma-estate string. Any project with a
``docs/ROADMAP.md`` fenced record whose declared evidence includes a
skip/xfail-marked test file produces the same two fact kinds.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.orchestration.origination.facts import SourceFact, SourceFactKind
from project_atlas.project_roadmap import (
    _evidence_exists,
    _normalize_lifecycle,
    _normalize_status,
    _parse_fenced_record,
)

ADAPTER_VERSION = "origination-adapter-v1"

#: Roadmap items in these normalized statuses are already done or not yet
#: ready; neither is eligible authoritative intent for a new proposal.
_ELIGIBLE_STATUSES = frozenset({"NOT_STARTED", "IN_PROGRESS"})
_ELIGIBLE_LIFECYCLES = frozenset({"READY"})

_SKIP_MARK_RE = re.compile(
    r"^\s*pytestmark\s*=\s*pytest\.mark\.(skip|xfail)\s*\(",
    re.MULTILINE,
)
_MAX_SCAN_LINES = 200
_MAX_EXCERPT = 400


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _roadmap_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("roadmap_items")
    if not isinstance(raw, list):
        raw = record.get("items")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


@dataclass(frozen=True)
class EligibleRoadmapItem:
    """A single roadmap-record item whose normalized status/lifecycle make
    it eligible authoritative intent. Structured for proposal construction
    -- ``SourceFact.excerpt`` deliberately stays a bounded string, so this
    is where the fuller id/title/evidence/depends_on detail lives instead.
    """

    item_id: str
    title: str
    status: str
    lifecycle: str
    depends_on: tuple[str, ...]
    evidence: tuple[str, ...]
    roadmap_text: str
    roadmap_digest: str


def eligible_roadmap_items(project_root: Path) -> tuple[EligibleRoadmapItem, ...]:
    """Parse ``<project_root>/docs/ROADMAP.md`` and return every item whose
    normalized status is NOT_STARTED/IN_PROGRESS and normalized lifecycle
    is READY. Empty tuple (never raises) when there's no roadmap file, no
    fenced record, or nothing eligible -- all valid, common outcomes."""
    roadmap_path = project_root / "docs" / "ROADMAP.md"
    if not roadmap_path.is_file():
        return ()
    try:
        text = roadmap_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ()
    record = _parse_fenced_record(text)
    if record is None:
        return ()
    digest = _digest(text.encode("utf-8"))

    items: list[EligibleRoadmapItem] = []
    for raw_item in _roadmap_items(record):
        status, notes = _normalize_status(raw_item.get("status") or raw_item.get("lifecycle"))
        lifecycle = _normalize_lifecycle(raw_item.get("lifecycle"), progress=status, notes=notes)
        if status not in _ELIGIBLE_STATUSES or lifecycle not in _ELIGIBLE_LIFECYCLES:
            continue
        item_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
        if not item_id:
            continue
        title = str(raw_item.get("title") or raw_item.get("name") or item_id)
        depends_on = tuple(
            str(dep) for dep in (raw_item.get("depends_on") or raw_item.get("dependencies") or [])
            if str(dep).strip()
        )
        evidence_raw = raw_item.get("evidence") or []
        evidence: tuple[str, ...] = ()
        if isinstance(evidence_raw, list):
            candidates = (str(ref).strip() for ref in evidence_raw)
            evidence = tuple(
                ref for ref in candidates if ref and _evidence_exists(project_root, ref)
            )
        items.append(
            EligibleRoadmapItem(
                item_id=item_id,
                title=title,
                status=status,
                lifecycle=lifecycle,
                depends_on=depends_on,
                evidence=evidence,
                roadmap_text=text,
                roadmap_digest=digest,
            )
        )
    return tuple(items)


def extract_authoritative_facts(project_root: Path, project_id: str) -> tuple[SourceFact, ...]:
    """One ``AUTHORITATIVE_ROADMAP_ITEM`` fact per currently-eligible
    roadmap item (see :func:`eligible_roadmap_items`)."""
    facts: list[SourceFact] = []
    for item in eligible_roadmap_items(project_root):
        evidence_str = ",".join(item.evidence)
        excerpt = f"id={item.item_id} title={item.title} evidence=[{evidence_str}]"[:_MAX_EXCERPT]
        facts.append(
            SourceFact(
                kind=SourceFactKind.AUTHORITATIVE_ROADMAP_ITEM,
                project_id=project_id,
                location="docs/ROADMAP.md",
                content_digest=item.roadmap_digest,
                excerpt=excerpt,
            )
        )
    return tuple(facts)


def extract_corroborating_facts(
    project_root: Path, project_id: str, evidence_paths: tuple[str, ...]
) -> tuple[SourceFact, ...]:
    """For each evidence path, if it resolves to a real file under
    ``project_root`` and its first ``_MAX_SCAN_LINES`` lines carry a
    module-level ``pytestmark = pytest.mark.skip(...)`` or ``.xfail(...)``,
    record one ``CORROBORATING_SPEC_TEST`` fact.

    Parses text with a regex only. Never imports, executes, or otherwise
    runs the scanned file -- it may be untrusted project content.
    """
    facts: list[SourceFact] = []
    for ref in evidence_paths:
        if not _evidence_exists(project_root, ref):
            continue
        candidate = project_root / ref
        head_lines: list[str] = []
        try:
            with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                for _ in range(_MAX_SCAN_LINES):
                    line = handle.readline()
                    if not line:
                        break
                    head_lines.append(line)
        except (OSError, UnicodeError):
            continue
        head = "".join(head_lines)
        match = _SKIP_MARK_RE.search(head)
        if match is None:
            continue
        raw_bytes = candidate.read_bytes()
        facts.append(
            SourceFact(
                kind=SourceFactKind.CORROBORATING_SPEC_TEST,
                project_id=project_id,
                location=ref,
                content_digest=_digest(raw_bytes),
                excerpt=head[: _MAX_EXCERPT],
            )
        )
    return tuple(facts)
