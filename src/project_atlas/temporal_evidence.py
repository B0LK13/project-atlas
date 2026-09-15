"""Extract temporal evidence from source text (AS-CORE-005).

Never treats Atlas observation/mtime as semantic event time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import yaml

_CANDIDATE_RE = re.compile(r"V2-0*(\d+)", re.I)
_SUPERSEDES_LIST_RE = re.compile(r"(?im)^supersedes\s*:\s*(?:\[([^\]]*)\]|(.+))$")
_SUPERSEDED_BY_RE = re.compile(r"(?im)^superseded_by\s*:\s*(.+)$")
_ORIGINAL_CERT_RE = re.compile(r"(?im)^original_certification\s*:\s*(.+)$")
_MERGED_AT_RE = re.compile(r"(?im)^merged_to_main_at\s*:\s*[\"']?([0-9T:+.-]+)[\"']?\s*$")
_TIMESTAMP_RE = re.compile(r"(?im)^timestamp\s*:\s*[\"']?([0-9T:+.-]+)[\"']?\s*$")
_NEXT_CANDIDATE_RE = re.compile(r"(?im)^next_candidate\s*:\s*(.+)$")
_PREV_IMPL_RE = re.compile(r"(?im)previous_implementation\s*:\s*[\"']?([0-9a-f]{7,40})[\"']?")
_SUPERSEDES_PROSE_RE = re.compile(r"(?i)this receipt supersedes\s+(.{10,160}?)(?:\.|$)")


@dataclass(frozen=True)
class SourceTemporalFacts:
    """Temporal facts extracted from one source document."""

    source_id: str
    path: str
    candidate_ordinal: int | None = None
    supersedes_tokens: tuple[str, ...] = ()
    superseded_by_token: str | None = None
    next_candidate_token: str | None = None
    original_certification: str | None = None
    merged_to_main_at: datetime | None = None
    document_timestamp: datetime | None = None
    previous_implementation: str | None = None
    supersedes_prose: str | None = None
    status_value: str | None = None
    title_value: str | None = None
    work_package_value: str | None = None
    has_post_merge_signal: bool = False
    raw_keys: tuple[str, ...] = ()


def _parse_dt(raw: str) -> datetime | None:
    text = raw.strip().strip("\"'")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _tokens_from_list(blob: str) -> tuple[str, ...]:
    parts = re.split(r"[\s,]+", blob.strip())
    return tuple(p.strip("\"'") for p in parts if p.strip("\"'"))


def _safe_yaml_root(text: str) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(text)
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _iter_mapping_nodes(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield root plus one-level nested mapping nodes (e.g. candidate:)."""
    nodes: list[dict[str, Any]] = [root]
    for value in root.values():
        if isinstance(value, dict):
            nodes.append(value)
    return nodes


def extract_source_temporal_facts(
    *,
    source_id: str,
    path: str,
    text: str,
) -> SourceTemporalFacts:
    """Extract bounded temporal facts from source text/path."""
    normalized_path = path.replace("\\", "/")
    root = _safe_yaml_root(text) or {}
    keys = tuple(sorted(str(k) for k in root if isinstance(k, str)))

    cand_match = _CANDIDATE_RE.search(normalized_path) or _CANDIDATE_RE.search(text)
    candidate_ordinal = int(cand_match.group(1)) if cand_match else None

    supersedes: list[str] = []
    for match in _SUPERSEDES_LIST_RE.finditer(text):
        blob = match.group(1) if match.group(1) is not None else match.group(2)
        if blob:
            supersedes.extend(_tokens_from_list(blob))
    # Nested candidate.supersedes (CORE-003 receipts) plus top-level.
    for node in _iter_mapping_nodes(root):
        raw_sup = node.get("supersedes")
        if isinstance(raw_sup, list):
            supersedes.extend(str(x) for x in raw_sup)
        elif isinstance(raw_sup, str):
            supersedes.append(raw_sup)

    superseded_by = None
    m = _SUPERSEDED_BY_RE.search(text)
    if m:
        superseded_by = m.group(1).strip().strip("\"'")
    for node in _iter_mapping_nodes(root):
        if isinstance(node.get("superseded_by"), str):
            superseded_by = node["superseded_by"]

    next_candidate = None
    m = _NEXT_CANDIDATE_RE.search(text)
    if m:
        next_candidate = m.group(1).strip().strip("\"'")
    for node in _iter_mapping_nodes(root):
        if isinstance(node.get("next_candidate"), str):
            next_candidate = node["next_candidate"]

    original_cert = None
    m = _ORIGINAL_CERT_RE.search(text)
    if m:
        original_cert = m.group(1).strip().strip("\"'")
    if isinstance(root.get("original_certification"), str):
        original_cert = root["original_certification"]

    merged_at = None
    m = _MERGED_AT_RE.search(text)
    if m:
        merged_at = _parse_dt(m.group(1))
    if isinstance(root.get("merged_to_main_at"), str):
        merged_at = _parse_dt(root["merged_to_main_at"]) or merged_at

    doc_ts = None
    m = _TIMESTAMP_RE.search(text)
    if m:
        doc_ts = _parse_dt(m.group(1))
    for key in ("timestamp", "recorded_at", "merged_to_main_at"):
        for node in _iter_mapping_nodes(root):
            if isinstance(node.get(key), str):
                doc_ts = _parse_dt(node[key]) or doc_ts

    prev_impl = None
    m = _PREV_IMPL_RE.search(text)
    if m:
        prev_impl = m.group(1)
    protected = root.get("protected_refs")
    if isinstance(protected, dict) and isinstance(protected.get("previous_implementation"), str):
        prev_impl = protected["previous_implementation"]

    prose = None
    m = _SUPERSEDES_PROSE_RE.search(text)
    if m:
        prose = m.group(1).strip()

    status = root.get("status") if isinstance(root.get("status"), str) else None
    title = root.get("title") if isinstance(root.get("title"), str) else None
    wp = None
    for key in ("work_package", "work_package_id", "package"):
        if isinstance(root.get(key), str):
            wp = root[key]
            break

    status_l = (status or "").lower()
    has_post_merge = bool(
        merged_at
        or "post-merge" in normalized_path.lower()
        or status_l.startswith("merged")
        or "merged-post-merge" in status_l
        or "merged-and-post-merge" in status_l
    )

    return SourceTemporalFacts(
        source_id=source_id,
        path=normalized_path,
        candidate_ordinal=candidate_ordinal,
        supersedes_tokens=tuple(dict.fromkeys(supersedes)),
        superseded_by_token=superseded_by,
        next_candidate_token=next_candidate,
        original_certification=original_cert,
        merged_to_main_at=merged_at,
        document_timestamp=doc_ts,
        previous_implementation=prev_impl,
        supersedes_prose=prose,
        status_value=status,
        title_value=title,
        work_package_value=wp,
        has_post_merge_signal=has_post_merge,
        raw_keys=keys,
    )


@dataclass
class ClaimTemporalContext:
    """Claim joined with its source temporal facts."""

    claim_id: str
    subject: str
    field: str
    value: str
    source_id: str
    authority: str
    facts: SourceTemporalFacts
    path: str = ""
