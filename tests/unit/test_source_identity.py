"""AS-ID-001 identity contract tests."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from project_atlas.domain import PathHistoryEntry, SourceLineageRecord
from project_atlas.lineage import build_project_registry
from project_atlas.schema import validate_record
from project_atlas.source_identity import (
    canonicalize_project_path,
    lineage_id,
    validate_project_uuid,
)


def test_project_uuid_requires_uuidv4() -> None:
    value = str(uuid.uuid4())
    assert validate_project_uuid(value) == value
    with pytest.raises(ValueError):
        validate_project_uuid(str(uuid.uuid1()))
    with pytest.raises(ValueError):
        validate_project_uuid("not-a-uuid")


def test_canonical_path_is_host_independent_and_nfc_normalized() -> None:
    assert canonicalize_project_path("docs\\Cafe\u0301.md") == "docs/Caf\u00e9.md"
    with pytest.raises(ValueError):
        canonicalize_project_path("../outside.md")
    with pytest.raises(ValueError):
        canonicalize_project_path("/absolute.md")
    with pytest.raises(ValueError):
        canonicalize_project_path("C:/absolute.md")


def test_lineage_id_uses_amended_formula() -> None:
    project_uuid = "00000000-0000-4000-8000-000000000001"
    material = (
        "atlas/source-lineage/v1|" + project_uuid + "|docs/README.md|" + "a" * 64 + "|1"
    )
    expected = "sline-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    assert lineage_id(project_uuid, "docs/README.md", "a" * 64, 1) == expected


def test_source_registry_v2_is_strict_and_schema_locked() -> None:
    project_uuid = "00000000-0000-4000-8000-000000000001"
    record = SourceLineageRecord(
        source_id="source-1",
        source_lineage_id=lineage_id(project_uuid, "README.md", "a" * 64, 1),
        lineage_generation=1,
        canonical_project_id=project_uuid,
        first_seen_path="README.md",
        current_path="README.md",
        path_history=[PathHistoryEntry(path="README.md", from_sequence=1)],
        first_content_sha256="a" * 64,
        current_content_sha256="a" * 64,
        first_seen_sequence=1,
        document_lifecycle="verified",
        source_change_state="new",
    )
    validate_record(record, "source-registry")
    with pytest.raises(ValueError):
        SourceLineageRecord.model_validate({**record.model_dump(), "schema_version": 1})
    with pytest.raises(ValueError):
        validate_record(
            {**record.model_dump(), "canonical_project_id": str(uuid.uuid1())},
            "source-registry",
        )


def test_project_identity_lock_is_single_winner_and_releases(tmp_path: Path) -> None:
    from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

    lock_path = tmp_path / ".atlas" / "identity.lock"
    first = ProjectIdentityLock(lock_path, wait_seconds=0.01, poll_seconds=0.001)
    second = ProjectIdentityLock(lock_path, wait_seconds=0.01, poll_seconds=0.001)
    first.acquire()
    try:
        with pytest.raises(IdentityLockError):
            second.acquire()
        assert lock_path.is_file()
    finally:
        first.release()
    second.acquire()
    second.release()
    assert not lock_path.exists()


def test_copy_gets_distinct_lineage_and_ambiguous_restore_fails_closed() -> None:
    project_uuid = "00000000-0000-4000-8000-000000000041"
    first = {
        "source_id": "source-first",
        "path": "README.md",
        "sha256": "a" * 64,
    }
    initial = build_project_registry(project_uuid, [first], [])
    copied = build_project_registry(
        project_uuid,
        [first, {"source_id": "source-copy", "path": "COPY.md", "sha256": "a" * 64}],
        initial,
    )
    identities = {item["source_lineage_id"] for item in copied}
    assert len(identities) == 2
    tombstoned = build_project_registry(project_uuid, [], copied)
    assert all(item["source_change_state"] == "deleted" for item in tombstoned)
    with pytest.raises(ValueError, match="unresolved source identity"):
        build_project_registry(
            project_uuid,
            [{"source_id": "source-new", "path": "README.md", "sha256": "a" * 64}],
            tombstoned,
        )
