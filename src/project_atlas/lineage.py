"""AS-ID-001 source-registry migration and evidence-scoped resolution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from project_atlas.domain.source_registry import PathHistoryEntry, SourceLineageRecord
from project_atlas.domain.sources import LineageResolution
from project_atlas.domain.vocabulary import DocumentLifecycle, SourceChangeState
from project_atlas.source_identity import canonicalize_project_path, lineage_id


class UnresolvedIdentityError(ValueError):
    """Deterministic, structured finding for continuity that cannot be proven."""

    def __init__(
        self,
        *,
        project_uuid: str,
        path: str,
        content_sha256: str | None = None,
        reason: str,
        candidate_ids: Iterable[str] = (),
    ) -> None:
        canonical_path = canonicalize_project_path(path)
        candidates = sorted(set(str(value) for value in candidate_ids))
        identity = {
            "project_uuid": project_uuid,
            "observed_path": canonical_path,
            "observed_content_sha256": content_sha256,
            "reason": reason,
            "candidate_lineage_ids": candidates,
        }
        finding_id = "unresolved-" + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        self.finding = {
            "schema_version": 1,
            "finding_type": "unresolved-source-identity",
            "finding_id": finding_id,
            **identity,
            "resolution_required": True,
        }
        super().__init__(
            json.dumps(self.finding, sort_keys=True, separators=(",", ":"))
            + " (unresolved-identity)"
        )


@dataclass(frozen=True)
class _LegacyChain:
    members: tuple[dict[str, Any], ...]
    origin: dict[str, Any]
    latest: dict[str, Any]
    ordering_key: tuple[str, str, str]


def _legacy_key(item: dict[str, Any]) -> tuple[str, str, str]:
    path = canonicalize_project_path(str(item.get("path", "")))
    digest = str(item.get("sha256", ""))
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"incomplete legacy source history for {item.get('source_id')!r}")
    if not item.get("source_id"):
        raise ValueError("legacy source history is missing source_id")
    return str(item.get("first_seen") or ""), path, digest


def _reference_target(
    reference: str,
    records: list[dict[str, Any]],
    by_source_id: dict[str, int],
) -> int:
    source_match = by_source_id.get(reference)
    path_matches = [
        index
        for index, item in enumerate(records)
        if canonicalize_project_path(str(item.get("path", "")))
        == canonicalize_project_path(reference)
    ]
    if source_match is not None and path_matches and source_match not in path_matches:
        raise ValueError(f"contradictory legacy continuity reference: {reference}")
    if source_match is not None:
        return source_match
    if len(path_matches) != 1:
        raise ValueError(f"incomplete or ambiguous legacy continuity reference: {reference}")
    return path_matches[0]


def _legacy_chains(previous: list[dict[str, Any]]) -> list[_LegacyChain]:
    records = [dict(item) for item in previous]
    keys = [_legacy_key(item) for item in records]
    by_source_id: dict[str, int] = {}
    for index, item in enumerate(records):
        source_id = str(item["source_id"])
        if source_id in by_source_id:
            raise ValueError(f"duplicate legacy source_id: {source_id}")
        by_source_id[source_id] = index

    successors: dict[int, int] = {}
    predecessors: dict[int, int] = {}
    edges: dict[int, set[int]] = {index: set() for index in range(len(records))}

    def add_edge(start: int, end: int) -> None:
        if start == end or (start in successors and successors[start] != end):
            raise ValueError("contradictory legacy continuity edges")
        if end in predecessors and predecessors[end] != start:
            raise ValueError("contradictory legacy continuity edges")
        successors[start] = end
        predecessors[end] = start
        edges[start].add(end)
        edges[end].add(start)

    for index, item in enumerate(records):
        renamed_from = item.get("renamed_from")
        if renamed_from:
            add_edge(_reference_target(str(renamed_from), records, by_source_id), index)
        restored_as = item.get("restored_as")
        if restored_as:
            add_edge(index, _reference_target(str(restored_as), records, by_source_id))

    visited: set[int] = set()
    chains: list[_LegacyChain] = []
    for start in sorted(edges):
        if start in visited:
            continue
        component: set[int] = set()
        stack = [start]
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component.add(index)
            visited.add(index)
            stack.extend(edges[index] - component)

        # A continuity chain must be a directed path, not a cycle.
        head = next((index for index in component if index not in predecessors), None)
        if head is None:
            raise ValueError("cycle in legacy continuity history")
        ordered: list[int] = []
        seen: set[int] = set()
        current = head
        while current in component:
            if current in seen:
                raise ValueError("cycle in legacy continuity history")
            seen.add(current)
            ordered.append(current)
            if current not in successors:
                break
            current = successors[current]
        if seen != component:
            raise ValueError("disconnected or contradictory legacy continuity history")
        members = tuple(records[index] for index in sorted(ordered, key=lambda i: keys[i]))
        origin = min(members, key=_legacy_key)
        latest = max(
            members,
            key=lambda item: (
                str(item.get("last_seen") or item.get("first_seen") or ""),
                *_legacy_key(item)[1:],
            ),
        )
        chains.append(
            _LegacyChain(
                members=members,
                origin=origin,
                latest=latest,
                ordering_key=_legacy_key(origin),
            )
        )
    return sorted(chains, key=lambda chain: chain.ordering_key)


def migrate_v1_records_with_receipts(
    previous: Iterable[dict[str, Any]], project_uuid: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Migrate v1 records after validating continuity chains and ordering."""
    chains = _legacy_chains(list(previous))
    generations: dict[str, int] = {}
    migrated: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for sequence, chain in enumerate(chains, start=1):
        origin_path = canonicalize_project_path(str(chain.origin["path"]))
        generation = generations.get(origin_path, 0) + 1
        generations[origin_path] = generation
        source_lineage_id = lineage_id(
            project_uuid,
            origin_path,
            str(chain.origin["sha256"]),
            generation,
        )
        history = [
            PathHistoryEntry(
                path=canonicalize_project_path(str(member["path"])),
                from_sequence=sequence + member_index,
                to_sequence=(
                    sequence + member_index + 1
                    if member_index + 1 < len(chain.members)
                    else None
                ),
            )
            for member_index, member in enumerate(chain.members)
        ]
        latest = chain.latest
        record = SourceLineageRecord(
            source_id=str(latest["source_id"]),
            source_lineage_id=source_lineage_id,
            lineage_generation=generation,
            canonical_project_id=project_uuid,
            first_seen_path=origin_path,
            current_path=canonicalize_project_path(str(latest["path"])),
            path_history=history,
            first_content_sha256=str(chain.origin["sha256"]),
            current_content_sha256=str(latest["sha256"]),
            first_seen_sequence=sequence,
            document_lifecycle=DocumentLifecycle(str(latest.get("document_lifecycle", "verified"))),
            source_change_state=SourceChangeState(
                str(latest.get("source_change_state", latest.get("lifecycle", "unchanged")))
            ),
            renamed_from=(
                canonicalize_project_path(str(latest["renamed_from"]))
                if latest.get("renamed_from")
                else None
            ),
            path=canonicalize_project_path(str(latest["path"])),
            sha256=str(latest["sha256"]),
            compatibility_repaired=bool(latest.get("compatibility_repaired", False)),
            compatibility_repair_reason=latest.get("compatibility_repair_reason"),
        )
        migrated.append(record.model_dump(mode="json"))
        receipts.append(
            {
                "schema_version": 1,
                "receipt_type": "source-lineage-migration",
                "project_uuid": project_uuid,
                "source_ids": [str(member["source_id"]) for member in chain.members],
                "source_lineage_id": source_lineage_id,
                "lineage_generation": generation,
                "origin_path": origin_path,
                "origin_sha256": str(chain.origin["sha256"]),
                "ordering_key": {
                    "first_seen": chain.ordering_key[0],
                    "canonical_origin_path": chain.ordering_key[1],
                    "first_content_sha256": chain.ordering_key[2],
                },
                "chain_members": [str(member["source_id"]) for member in chain.members],
                "continuity_chain": [str(member["source_id"]) for member in chain.members],
                "evidence_edges": [
                    {
                        "from": str(chain.members[index]["source_id"]),
                        "to": str(chain.members[index + 1]["source_id"]),
                        "relationship": (
                            "renamed_from"
                            if str(chain.members[index + 1].get("renamed_from", ""))
                            in {
                                str(chain.members[index]["source_id"]),
                                canonicalize_project_path(str(chain.members[index]["path"])),
                            }
                            else "restored_as"
                            if str(chain.members[index].get("restored_as", ""))
                            in {
                                str(chain.members[index + 1]["source_id"]),
                                canonicalize_project_path(str(chain.members[index + 1]["path"])),
                            }
                            else "approved_transition"
                        ),
                        "evidence_reference": (
                            f"v1:{chain.members[index]['source_id']}->"
                            f"{chain.members[index + 1]['source_id']}"
                        ),
                    }
                    for index in range(len(chain.members) - 1)
                ],
                "schema_transition": "1-to-2",
            }
        )
    return migrated, receipts


def migrate_v1_records(
    previous: Iterable[dict[str, Any]], project_uuid: str
) -> list[dict[str, Any]]:
    """Compatibility wrapper returning only migrated registry records."""
    return migrate_v1_records_with_receipts(previous, project_uuid)[0]


def _entry_lineage(entry: dict[str, Any]) -> str | None:
    value = entry.get("source_lineage_id")
    return str(value) if value else None


def build_project_registry(
    project_uuid: str,
    entries: list[dict[str, Any]],
    previous: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve observations using unique fingerprint and lineage evidence."""
    prior = [SourceLineageRecord.model_validate(item) for item in previous]
    lineage_ids = [record.source_lineage_id for record in prior]
    if len(lineage_ids) != len(set(lineage_ids)):
        raise ValueError("lineage-ID collision in source registry")
    by_source_id: dict[str, SourceLineageRecord] = {}
    for record in prior:
        if record.source_id in by_source_id:
            raise ValueError(f"duplicate source_id in source registry: {record.source_id}")
        by_source_id[record.source_id] = record
    used_lineages: set[str] = set()
    superseded_by: dict[str, str] = {}
    current: list[SourceLineageRecord] = []
    next_sequence = max((record.first_seen_sequence for record in prior), default=0) + 1

    def compatible_candidates(
        path: str, digest: str, explicit: str | None
    ) -> list[SourceLineageRecord]:
        eligible = [
            record
            for record in prior
            if record.source_lineage_id not in used_lineages
            and record.source_change_state
            in {SourceChangeState.DELETED, SourceChangeState.RESTORED_ELSEWHERE}
        ]
        if explicit:
            return [record for record in eligible if record.source_lineage_id == explicit]
        return [record for record in eligible if record.current_content_sha256 == digest]

    ordered_entries = sorted(
        entries,
        key=lambda item: (
            0 if str(item["source_id"]) in by_source_id else 1,
            canonicalize_project_path(str(item["path"])),
        ),
    )
    for entry in ordered_entries:
        source_id = str(entry["source_id"])
        path = canonicalize_project_path(str(entry["path"]))
        digest = str(entry["sha256"])
        explicit = _entry_lineage(entry)
        raw_resolution = entry.get("lineage_resolution")
        try:
            resolution = (
                LineageResolution.model_validate(raw_resolution)
                if raw_resolution is not None
                else None
            )
        except ValueError as exc:
            raise ValueError(f"invalid lineage resolution for {source_id}: {exc}") from exc
        if resolution is not None:
            known_ids = {record.source_lineage_id for record in prior}
            if set(resolution.candidate_lineage_ids) - known_ids:
                raise ValueError("lineage resolution contains unknown or cross-project candidates")
            if resolution.outcome == "unresolved":
                raise UnresolvedIdentityError(
                    project_uuid=project_uuid,
                    path=path,
                    content_sha256=digest,
                    reason=resolution.reason,
                    candidate_ids=resolution.candidate_lineage_ids,
                )
        source_record = by_source_id.get(source_id)
        if source_record is not None and source_record.source_lineage_id in used_lineages:
            source_record = None
        if source_record is not None:
            if explicit and explicit != source_record.source_lineage_id:
                raise UnresolvedIdentityError(
                    project_uuid=project_uuid,
                    path=path,
                    content_sha256=digest,
                    reason="source_id and explicit lineage evidence disagree",
                    candidate_ids=[source_record.source_lineage_id, explicit],
                )
            changed_path = source_record.current_path != path
            changed_content = source_record.current_content_sha256 != digest
            if source_record.source_change_state is SourceChangeState.DELETED:
                if changed_content and explicit != source_record.source_lineage_id:
                    raise UnresolvedIdentityError(
                        project_uuid=project_uuid,
                        path=path,
                        content_sha256=digest,
                        reason="changed-content restoration lacks explicit continuity evidence",
                        candidate_ids=[source_record.source_lineage_id],
                    )
                state = SourceChangeState.RESTORED
            else:
                state = (
                    SourceChangeState.RENAMED
                    if changed_path
                    else SourceChangeState.MODIFIED
                    if changed_content
                    else source_record.source_change_state
                )
            used_lineages.add(source_record.source_lineage_id)
            history = list(source_record.path_history)
            if changed_path:
                history[-1] = history[-1].model_copy(update={"to_sequence": next_sequence - 1})
                history.append(PathHistoryEntry(path=path, from_sequence=next_sequence))
            current.append(
                source_record.model_copy(
                    update={
                        "current_path": path,
                        "path_history": history,
                        "current_content_sha256": digest,
                        "source_change_state": state,
                        "path": path,
                        "sha256": digest,
                        "restored_as": (
                            path
                            if state is SourceChangeState.RESTORED
                            else source_record.restored_as
                        ),
                    }
                )
            )
            next_sequence += 1
            continue

        candidates = compatible_candidates(path, digest, explicit)
        path_candidates = [
            record
            for record in prior
            if record.source_lineage_id not in used_lineages
            and record.source_change_state
            in {SourceChangeState.DELETED, SourceChangeState.RESTORED_ELSEWHERE}
            and (
                record.current_path == path
                or any(history.path == path for history in record.path_history)
            )
        ]
        active_same_hash = [
            record
            for record in prior
            if record.source_lineage_id not in used_lineages
            and record.source_change_state
            not in {SourceChangeState.DELETED, SourceChangeState.RESTORED_ELSEWHERE}
            and record.current_content_sha256 == digest
        ]
        if resolution is not None and resolution.outcome == "continue_existing":
            selected = resolution.selected_lineage_id
            if selected is None or resolution.candidate_lineage_ids != [selected]:
                raise ValueError("continue_existing requires exactly one selected candidate")
            selected_records = [
                record for record in prior
                if record.source_lineage_id == selected
                and record.source_lineage_id not in used_lineages
            ]
            if len(selected_records) != 1 or selected_records[0] not in path_candidates:
                raise UnresolvedIdentityError(
                    project_uuid=project_uuid,
                    path=path,
                    content_sha256=digest,
                    reason="selected lineage is not uniquely compatible with the observed slot",
                    candidate_ids=resolution.candidate_lineage_ids,
                )
            candidates = selected_records
            path_candidates = selected_records
        if resolution is not None and resolution.outcome == "create_new_generation":
            if not path_candidates:
                raise ValueError("create_new_generation requires a retained historical slot")
            candidate_ids = {record.source_lineage_id for record in path_candidates}
            if set(resolution.candidate_lineage_ids) != candidate_ids:
                raise ValueError(
                    "create_new_generation candidates must describe the complete retired slot"
                )
            prior_slot = max(path_candidates, key=lambda record: record.lineage_generation)
            generation = max(
                (record.lineage_generation for record in prior if record.first_seen_path == path),
                default=0,
            ) + 1
            new_lineage = lineage_id(project_uuid, path, digest, generation)
            superseded_by[prior_slot.source_lineage_id] = new_lineage
            new_record = SourceLineageRecord(
                source_id=source_id,
                source_lineage_id=new_lineage,
                lineage_generation=generation,
                canonical_project_id=project_uuid,
                first_seen_path=path,
                current_path=path,
                path_history=[PathHistoryEntry(path=path, from_sequence=next_sequence)],
                first_content_sha256=digest,
                current_content_sha256=digest,
                first_seen_sequence=next_sequence,
                document_lifecycle=DocumentLifecycle.VERIFIED,
                source_change_state=SourceChangeState.NEW,
                supersedes_lineage=prior_slot.source_lineage_id,
                path=path,
                sha256=digest,
            )
            current.append(new_record)
            used_lineages.add(new_lineage)
            next_sequence += 1
            continue
        if not explicit and active_same_hash and candidates:
            raise UnresolvedIdentityError(
                project_uuid=project_uuid,
                path=path,
                content_sha256=digest,
                reason="copy-versus-restoration has competing active and retired evidence",
                candidate_ids=[
                    record.source_lineage_id
                    for record in (*candidates, *active_same_hash)
                ],
            )
        if len(candidates) > 1 or (not candidates and path_candidates):
            raise UnresolvedIdentityError(
                project_uuid=project_uuid,
                path=path,
                content_sha256=digest,
                reason=(
                    "multiple compatible retired lineages"
                    if len(candidates) > 1
                    else "retired path has incompatible content"
                ),
                candidate_ids=[
                    record.source_lineage_id
                    for record in (*candidates, *path_candidates)
                ],
            )
        if len(candidates) == 1:
            record = candidates[0]
            used_lineages.add(record.source_lineage_id)
            history = list(record.path_history)
            if record.current_path != path:
                history.append(PathHistoryEntry(path=path, from_sequence=next_sequence))
            current.append(
                record.model_copy(
                    update={
                        "source_id": source_id,
                        "current_path": path,
                        "path_history": history,
                        "renamed_from": (
                            record.current_path
                            if record.current_path != path
                            else record.renamed_from
                        ),
                        "source_change_state": (
                            SourceChangeState.RESTORED
                            if record.current_path == path
                            else SourceChangeState.RESTORED_ELSEWHERE
                        ),
                        "current_content_sha256": digest,
                        "path": path,
                        "sha256": digest,
                        "restored_as": path,
                    }
                )
            )
            next_sequence += 1
            continue
        if active_same_hash and not explicit:
            if len(active_same_hash) > 1:
                raise UnresolvedIdentityError(
                    project_uuid=project_uuid,
                    path=path,
                    content_sha256=digest,
                    reason="multiple active lineages match a move or copy",
                    candidate_ids=[record.source_lineage_id for record in active_same_hash],
                )
            record = active_same_hash[0]
            used_lineages.add(record.source_lineage_id)
            history = list(record.path_history)
            history[-1] = history[-1].model_copy(update={"to_sequence": next_sequence - 1})
            history.append(PathHistoryEntry(path=path, from_sequence=next_sequence))
            current.append(
                record.model_copy(
                    update={
                        "source_id": source_id,
                        "current_path": path,
                        "path_history": history,
                        "renamed_from": record.current_path,
                        "source_change_state": SourceChangeState.RENAMED,
                        "current_content_sha256": digest,
                        "path": path,
                        "sha256": digest,
                    }
                )
            )
            next_sequence += 1
            continue

        slot_generations = [
            record.lineage_generation for record in prior if record.first_seen_path == path
        ]
        generation = max(slot_generations, default=0) + 1
        new_lineage = lineage_id(project_uuid, path, digest, generation)
        new_record = SourceLineageRecord(
            source_id=source_id,
            source_lineage_id=new_lineage,
            lineage_generation=generation,
            canonical_project_id=project_uuid,
            first_seen_path=path,
            current_path=path,
            path_history=[PathHistoryEntry(path=path, from_sequence=next_sequence)],
            first_content_sha256=digest,
            current_content_sha256=digest,
            first_seen_sequence=next_sequence,
            document_lifecycle=DocumentLifecycle.VERIFIED,
            source_change_state=SourceChangeState.NEW,
            path=path,
            sha256=digest,
        )
        current.append(new_record)
        used_lineages.add(new_lineage)
        next_sequence += 1

    for record in prior:
        if record.source_lineage_id in used_lineages:
            continue
        current.append(
            record.model_copy(
                update={
                    "document_lifecycle": DocumentLifecycle.HISTORICAL,
                    "source_change_state": SourceChangeState.DELETED,
                    "superseded_by_lineage": superseded_by.get(
                        record.source_lineage_id, record.superseded_by_lineage
                    ),
                }
            )
        )
    result = [
        record.model_dump(mode="json")
        for record in sorted(current, key=lambda item: item.source_lineage_id)
    ]
    lineage_ids = [str(item["source_lineage_id"]) for item in result]
    if len(lineage_ids) != len(set(lineage_ids)):
        raise ValueError("lineage-ID collision in emitted source registry")
    return result
