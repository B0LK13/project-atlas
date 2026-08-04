"""AS-CORE-003 concurrency and OCC rollback behavior."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.ingestion import _assert_state_compare_and_swap, ingest

pytestmark = pytest.mark.integration
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_ingestion_occ_rollback(tmp_path: Path) -> None:
    """A mutation of a transaction precondition aborts ingestion before promotion."""
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: occ-fixture\n", encoding="utf-8"
    )
    text = "# Overview\n- decision: we use OCC {#occ}\n"
    (source / "DECISION.md").write_text(text, encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_root": str(source),
                "duplicates": {},
                "inventory_sha256": _sha256("occ-fixture"),
                "sources": [
                    {
                        "likely_project": "occ-fixture",
                        "source_id": "decision",
                        "path": "DECISION.md",
                        "media_type": "text/markdown",
                        "sha256": _sha256(text),
                        "size_bytes": len(text.encode("utf-8")),
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK

    lifecycle_path = vault / "state" / "claim-lifecycle" / "occ-fixture.json"
    lifecycle_path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_path.write_text(
        json.dumps({"schema_version": 1, "claims": []}), encoding="utf-8"
    )

    original_assert = _assert_state_compare_and_swap

    def side_effect(preconditions: dict[Path, bytes | None]) -> None:
        lifecycle_path.write_text(
            json.dumps(
                {
                        "schema_version": 1,
                        "claims": [
                            {
                                "claim_id": "concurrent",
                                "project_id": "occ-fixture",
                                "lifecycle": "new",
                                "content_sha256": "0" * 64,
                            }
                        ],
                }
            ),
            encoding="utf-8",
        )
        original_assert(preconditions)

    lock_files = set((vault / ".atlas").glob("*.lock"))

    with patch(
        "project_atlas.ingestion._assert_state_compare_and_swap", side_effect=side_effect
    ), pytest.raises(ValueError, match="state changed during transaction"):
        ingest(manifest_path, vault)

    # Zero-write proof: no partial canonical promotion occurred.
    claims_dir = vault / "state" / "claims"
    assert not any(path.name.startswith("occ-fixture") for path in claims_dir.glob("*.json"))

    # Externally injected race state is preserved, not overwritten.
    lifecycle_after = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    assert [c["claim_id"] for c in lifecycle_after["claims"]] == ["concurrent"]

    # No temporary artifact was promoted to canonical state.
    assert not (vault / "state" / "claim-lifecycle" / "occ-fixture.json.tmp").exists()

    # Project identity lock is released after abort.
    remaining_locks = set((vault / ".atlas").glob("*.lock"))
    assert remaining_locks == lock_files

    # A clean retry converges, and replaying that retry is byte-identical.
    ingest(manifest_path, vault)
    second_retry = ingest(manifest_path, vault)
    second_snapshot = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }
    third_retry = ingest(manifest_path, vault)
    third_snapshot = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }
    assert second_retry == third_retry
    assert second_snapshot == third_snapshot
    assert not list(vault.rglob("*.tmp"))
