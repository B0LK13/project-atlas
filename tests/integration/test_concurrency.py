"""AS-CORE-003 concurrency and OCC rollback behavior."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from project_atlas import ingestion as ingestion_module
from project_atlas.cli import EXIT_OK, main
from project_atlas.ingestion import _assert_state_compare_and_swap, ingest
from project_atlas.source_identity import canonical_source_sha256_bytes

pytestmark = pytest.mark.integration


def _sha256(text: str) -> str:
    return canonical_source_sha256_bytes(
        text.encode("utf-8"), relative_path="DECISION.md"
    )


def _write_lf(path: Path, text: str) -> bytes:
    payload = text.encode("utf-8")
    path.write_bytes(payload)
    return payload


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix() + ("/" if path.is_dir() else ""): (
            None if path.is_dir() else path.read_bytes()
        )
        for path in sorted(root.rglob("*"))
    }


def test_ingestion_occ_rollback(tmp_path: Path) -> None:
    """A mutation of a transaction precondition aborts ingestion before promotion."""
    source = tmp_path / "source"
    source.mkdir()
    _write_lf(
        source / ".atlas-project.yaml",
        "schema_version: 1\nproject:\n  id: occ-fixture\n",
    )
    text = "# Overview\n- decision: we use OCC {#occ}\n"
    decision_bytes = _write_lf(source / "DECISION.md", text)

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
                        "size_bytes": len(decision_bytes),
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
        ingest(manifest_path, vault, authorized_source_root=source)

    # CAS rejects the transaction before promotion begins.
    claims_dir = vault / "state" / "claims"
    assert not any(path.name.startswith("occ-fixture") for path in claims_dir.glob("*.json"))

    # Externally injected race state is preserved, not overwritten.
    lifecycle_after = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    assert [c["claim_id"] for c in lifecycle_after["claims"]] == ["concurrent"]

    assert not list(vault.rglob("*.atlas-stage"))
    assert not list(vault.rglob("*.atlas-backup"))

    # Project identity lock is released after abort.
    remaining_locks = set((vault / ".atlas").glob("*.lock"))
    assert remaining_locks == lock_files

    # A clean retry converges, and replaying that retry is byte-identical.
    # Rediscover after genesis so approved marker provenance matches disk.
    assert main(["discover", "--source", str(source), "--output", str(manifest_path)]) == EXIT_OK
    ingest(manifest_path, vault, authorized_source_root=source)
    assert main(["discover", "--source", str(source), "--output", str(manifest_path)]) == EXIT_OK
    second_retry = ingest(manifest_path, vault, authorized_source_root=source)
    second_snapshot = _snapshot(vault)
    third_retry = ingest(manifest_path, vault, authorized_source_root=source)
    third_snapshot = _snapshot(vault)
    assert second_retry == third_retry
    assert second_snapshot == third_snapshot
    assert not list(vault.rglob("*.tmp"))


def test_ingestion_mid_promotion_failure_rolls_back_every_file(tmp_path: Path) -> None:
    """A failure after one canonical replacement restores the full snapshot."""
    source = tmp_path / "source"
    source.mkdir()
    _write_lf(
        source / ".atlas-project.yaml",
        "schema_version: 1\nproject:\n  id: promotion-fixture\n",
    )
    document = source / "DECISION.md"
    first_text = "# Overview\n- decision: first value {#promotion}\n"
    first_bytes = _write_lf(document, first_text)
    manifest_path = tmp_path / "manifest.json"

    def write_manifest(text: str, payload: bytes) -> None:
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source_root": str(source),
                    "duplicates": {},
                    "inventory_sha256": _sha256(text),
                    "sources": [
                        {
                            "likely_project": "promotion-fixture",
                            "source_id": "decision",
                            "path": "DECISION.md",
                            "media_type": "text/markdown",
                            "sha256": _sha256(text),
                            "size_bytes": len(payload),
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    write_manifest(first_text, first_bytes)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    ingest(manifest_path, vault, authorized_source_root=source)
    assert main(["discover", "--source", str(source), "--output", str(manifest_path)]) == EXIT_OK
    before = _snapshot(vault)

    second_text = "# Overview\n- decision: second value {#promotion}\n"
    second_bytes = _write_lf(document, second_text)
    write_manifest(second_text, second_bytes)
    original_replace = ingestion_module._replace_path
    staged_promotions = 0
    injected = False

    def fail_second_staged_replace(source_path: Path, destination: Path) -> None:
        nonlocal staged_promotions, injected
        if source_path.name.endswith(".atlas-stage"):
            staged_promotions += 1
            if staged_promotions == 2 and not injected:
                injected = True
                raise OSError("injected mid-promotion failure")
        original_replace(source_path, destination)

    with patch(
        "project_atlas.ingestion._replace_path",
        side_effect=fail_second_staged_replace,
    ), pytest.raises(OSError, match="injected mid-promotion failure"):
        ingest(manifest_path, vault, authorized_source_root=source)

    # The promotion-failure quarantine report is diagnostic evidence, not
    # canonical state; exclude it from the rollback comparison (AS-EXT-001A).
    after_failure = {
        key: value
        for key, value in _snapshot(vault).items()
        if not key.startswith("quarantine/")
    }
    assert injected and staged_promotions >= 2
    assert after_failure == before
    assert not list(vault.rglob("*.atlas-stage"))
    assert not list(vault.rglob("*.atlas-backup"))
    assert not list((vault / ".atlas" / "identity-locks").glob("*.lock"))

    first_retry = ingest(manifest_path, vault, authorized_source_root=source)
    retry_snapshot = _snapshot(vault)
    second_retry = ingest(manifest_path, vault, authorized_source_root=source)
    replay_snapshot = _snapshot(vault)
    assert first_retry == second_retry
    assert retry_snapshot == replay_snapshot
