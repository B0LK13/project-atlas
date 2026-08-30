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
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from project_atlas.orchestration.origination.facts import SourceFact, SourceFactKind
from project_atlas.project_roadmap import (
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
_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DONE_STATUSES = frozenset({"IMPLEMENTED", "VERIFIED_COMPLETION"})


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
    item_digest: str
    title: str
    status: str
    lifecycle: str
    depends_on: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence: tuple[str, ...]
    roadmap_text: str
    roadmap_digest: str


def _safe_project_file(project_root: Path, ref: str) -> tuple[str, Path] | None:
    """Resolve one project-relative path once and keep reads inside the root.

    The returned canonical relative path and resolved file refer to the same
    object. This avoids the historical ``lstrip('./')`` mismatch where a
    traversal-shaped reference could be checked under one path and read under
    another, and it rejects symlink escapes before any file content is opened.
    """
    if not ref or ref.startswith(("http://", "https://")):
        return None
    normalized = ref.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    try:
        root = project_root.resolve(strict=True)
        candidate = root.joinpath(*relative.parts).resolve(strict=True)
        canonical = candidate.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None
    if not candidate.is_file() or not canonical:
        return None
    return canonical, candidate


def _item_digest(raw_item: dict[str, Any]) -> str:
    """Digest one structured roadmap item, independent of sibling edits."""
    canonical = json.dumps(
        raw_item,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _digest(canonical)


def _declared_blockers(raw_item: dict[str, Any]) -> tuple[str, ...]:
    raw = raw_item.get("blockers") or []
    if not isinstance(raw, list):
        return ()
    blockers: list[str] = []
    for blocker in raw:
        if isinstance(blocker, str) and blocker.strip():
            blockers.append(blocker.strip())
        elif isinstance(blocker, dict):
            normalized = {
                "reason": str(blocker.get("reason") or "UNKNOWN"),
                "unlock_condition": blocker.get("unlock_condition"),
                "waiting_on": blocker.get("waiting_on"),
            }
            blockers.append(
                json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            )
    return tuple(blockers[:32])


def eligible_roadmap_items(project_root: Path) -> tuple[EligibleRoadmapItem, ...]:
    """Parse ``<project_root>/docs/ROADMAP.md`` and return every item whose
    normalized status is NOT_STARTED/IN_PROGRESS and normalized lifecycle
    is READY. Empty tuple (never raises) when there's no roadmap file, no
    fenced record, or nothing eligible -- all valid, common outcomes."""
    resolved_roadmap = _safe_project_file(project_root, "docs/ROADMAP.md")
    if resolved_roadmap is None:
        return ()
    _, roadmap_path = resolved_roadmap
    try:
        text = roadmap_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ()
    record = _parse_fenced_record(text)
    if record is None:
        return ()
    digest = _digest(text.encode("utf-8"))

    raw_items = _roadmap_items(record)
    item_statuses: dict[str, str] = {}
    item_id_counts: dict[str, int] = {}
    for raw_item in raw_items:
        raw_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
        if not _ITEM_ID_RE.fullmatch(raw_id):
            continue
        status, _ = _normalize_status(raw_item.get("status") or raw_item.get("lifecycle"))
        item_statuses[raw_id] = status
        item_id_counts[raw_id] = item_id_counts.get(raw_id, 0) + 1

    items: list[EligibleRoadmapItem] = []
    for raw_item in raw_items:
        status, notes = _normalize_status(raw_item.get("status") or raw_item.get("lifecycle"))
        lifecycle = _normalize_lifecycle(raw_item.get("lifecycle"), progress=status, notes=notes)
        if status not in _ELIGIBLE_STATUSES or lifecycle not in _ELIGIBLE_LIFECYCLES:
            continue
        item_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
        if not _ITEM_ID_RE.fullmatch(item_id):
            continue
        title = str(raw_item.get("title") or raw_item.get("name") or item_id)
        declared_dependencies = tuple(
            str(dep).strip()
            for dep in (raw_item.get("depends_on") or raw_item.get("dependencies") or [])
            if str(dep).strip()
        )
        blockers = list(_declared_blockers(raw_item))
        if item_id_counts.get(item_id, 0) > 1:
            blockers.append(f"duplicate roadmap item id: {item_id}")
        if item_id in declared_dependencies:
            blockers.append(f"self dependency: {item_id}")
        for dependency in declared_dependencies:
            if dependency not in item_statuses:
                blockers.append(f"missing dependency id: {dependency}")
        depends_on = tuple(
            dependency
            for dependency in declared_dependencies
            if dependency != item_id
            and item_statuses.get(dependency) not in _DONE_STATUSES
        )
        evidence_raw = raw_item.get("evidence") or []
        evidence: tuple[str, ...] = ()
        if isinstance(evidence_raw, list):
            safe_refs: list[str] = []
            for raw_ref in evidence_raw:
                resolved = _safe_project_file(project_root, str(raw_ref).strip())
                if resolved is not None:
                    safe_refs.append(resolved[0])
            evidence = tuple(dict.fromkeys(safe_refs))
        items.append(
            EligibleRoadmapItem(
                item_id=item_id,
                item_digest=_item_digest(raw_item),
                title=title,
                status=status,
                lifecycle=lifecycle,
                depends_on=depends_on,
                blockers=tuple(dict.fromkeys(blockers))[:32],
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
                subject_id=item.item_id,
                subject_digest=item.item_digest,
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
        resolved = _safe_project_file(project_root, ref)
        if resolved is None:
            continue
        canonical_ref, candidate = resolved
        try:
            raw_bytes = candidate.read_bytes()
        except OSError:
            continue
        head = "".join(
            raw_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)[
                :_MAX_SCAN_LINES
            ]
        )
        match = _SKIP_MARK_RE.search(head)
        if match is None:
            continue
        facts.append(
            SourceFact(
                kind=SourceFactKind.CORROBORATING_SPEC_TEST,
                project_id=project_id,
                location=canonical_ref,
                content_digest=_digest(raw_bytes),
                excerpt=head[: _MAX_EXCERPT],
            )
        )
    return tuple(facts)
