"""AS-ID-001 source registry resolution and v1 compatibility migration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from project_atlas.domain.source_registry import PathHistoryEntry, SourceLineageRecord
from project_atlas.domain.vocabulary import DocumentLifecycle, SourceChangeState
from project_atlas.source_identity import canonicalize_project_path, lineage_id


def _legacy_to_v2(
    previous: dict[str, Any], project_uuid: str, sequence: int
) -> SourceLineageRecord:
    """Convert one known v1 record; continuity is resolved by the caller."""
    path = canonicalize_project_path(str(previous.get("path", "")))
    digest = str(previous.get("sha256", ""))
    source_id = str(previous.get("source_id", ""))
    source_lineage_id = lineage_id(project_uuid, path, digest, 1)
    return SourceLineageRecord(
        source_id=source_id,
        source_lineage_id=source_lineage_id,
        lineage_generation=1,
        canonical_project_id=project_uuid,
        first_seen_path=path,
        current_path=path,
        path_history=[PathHistoryEntry(path=path, from_sequence=sequence)],
        first_content_sha256=digest,
        current_content_sha256=digest,
        first_seen_sequence=sequence,
        document_lifecycle=DocumentLifecycle(str(previous.get("document_lifecycle", "verified"))),
        source_change_state=SourceChangeState(
            str(previous.get("source_change_state", previous.get("lifecycle", "unchanged")))
        ),
        renamed_from=previous.get("renamed_from"),
    )


def migrate_v1_records(
    previous: Iterable[dict[str, Any]], project_uuid: str
) -> list[dict[str, Any]]:
    """Migrate known v1 records in canonical recorded-state order."""
    ordered = sorted(
        previous,
        key=lambda item: (
            str(item.get("first_seen") or ""),
            canonicalize_project_path(str(item.get("path", ""))),
            str(item.get("sha256", "")),
        ),
    )
    migrated = [
        _legacy_to_v2(item, project_uuid, sequence)
        for sequence, item in enumerate(ordered, start=1)
    ]
    return [record.model_dump(mode="json") for record in migrated]


def build_project_registry(
    project_uuid: str,
    entries: list[dict[str, Any]],
    previous: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve current observations against retained v2 lineage history."""
    prior = [SourceLineageRecord.model_validate(item) for item in previous]
    by_source_id = {record.source_id: record for record in prior}
    used_lineages: set[str] = set()
    current: list[SourceLineageRecord] = []
    next_sequence = max((record.first_seen_sequence for record in prior), default=0) + 1

    for entry in sorted(entries, key=lambda item: canonicalize_project_path(str(item["path"]))):
        source_id = str(entry["source_id"])
        path = canonicalize_project_path(str(entry["path"]))
        digest = str(entry["sha256"])
        record = by_source_id.get(source_id)
        if record is not None:
            used_lineages.add(record.source_lineage_id)
            changed_path = record.current_path != path
            changed_content = record.current_content_sha256 != digest
            state = (
                SourceChangeState.RESTORED
                if record.source_change_state is SourceChangeState.DELETED
                else SourceChangeState.RENAMED
                if changed_path
                else SourceChangeState.MODIFIED
                if changed_content
                else record.source_change_state
            )
            history = list(record.path_history)
            if changed_path:
                history[-1] = history[-1].model_copy(update={"to_sequence": next_sequence - 1})
                history.append(PathHistoryEntry(path=path, from_sequence=next_sequence))
            current.append(
                record.model_copy(
                    update={
                        "current_path": path,
                        "path_history": history,
                        "current_content_sha256": digest,
                        "source_change_state": state,
                    }
                )
            )
            next_sequence += 1
            continue

        candidates = [
            record
            for record in prior
            if record.source_lineage_id not in used_lineages
            and record.source_change_state
            in {SourceChangeState.DELETED, SourceChangeState.RESTORED_ELSEWHERE}
        ]
        if len(candidates) > 1:
            raise ValueError(f"unresolved source identity for path: {path}")
        if len(candidates) == 1:
            record = candidates[0]
            used_lineages.add(record.source_lineage_id)
            history = list(record.path_history)
            if record.current_path != path:
                history.append(
                    PathHistoryEntry(path=path, from_sequence=next_sequence)
                )
            current.append(
                record.model_copy(
                    update={
                        "source_id": source_id,
                        "current_path": path,
                        "path_history": history,
                        "renamed_from": (
                            record.current_path if record.current_path != path else record.renamed_from
                        ),
                        "source_change_state": (
                            SourceChangeState.RESTORED
                            if candidates[0].current_path == path
                            else SourceChangeState.RENAMED
                        ),
                        "current_content_sha256": digest,
                    }
                )
            )
            next_sequence += 1
            continue

        slot_generations = [
            record.lineage_generation
            for record in prior
            if record.first_seen_path == path
        ]
        generation = max(slot_generations, default=0) + 1
        new_lineage = lineage_id(project_uuid, path, digest, generation)
        current.append(
            SourceLineageRecord(
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
            )
        )
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
                }
            )
        )
    return [record.model_dump(mode="json") for record in sorted(current, key=lambda item: item.source_lineage_id)]
