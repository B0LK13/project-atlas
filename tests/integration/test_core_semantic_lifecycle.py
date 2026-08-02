"""AS-CORE-002 lifecycle, secret and regeneration behavior through CLI."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.discovery import discover, write_manifest
from project_atlas.ingestion import ingest


def _snapshot(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }


def _workflow(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: semantic-fixture\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# Semantic Fixture\n", encoding="utf-8")
    (source / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")
    (source / "secret-notes.txt").write_text(
        "password = 'fixture-only-secret-value'\n", encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return source, manifest, vault


def test_rich_project_record_secret_report_and_human_region(tmp_path: Path) -> None:
    source, manifest, vault = _workflow(tmp_path)
    project = vault / "projects" / "semantic-fixture" / "project.md"
    assert "schema_version: 1" in project.read_text(encoding="utf-8")
    report = json.loads(
        (vault / "generated" / "reports" / "secret-findings.json").read_text(encoding="utf-8")
    )
    assert report[0]["pattern"] == "password-assignment"
    project.write_text(
        project.read_text(encoding="utf-8")
        + "\n## Human notes\n\nKeep this text.\n",
        encoding="utf-8",
    )
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert "Keep this text." in project.read_text(encoding="utf-8")
    assert source.is_dir()


def test_removed_source_is_retained_as_lifecycle_state(tmp_path: Path) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    (source / "ARCHITECTURE.md").unlink()
    next_manifest = tmp_path / "manifest-2.json"
    assert main(["discover", "--source", str(source), "--output", str(next_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(next_manifest), "--vault", str(vault)]) == EXIT_OK
    state = json.loads((vault / "state" / "sources.json").read_text(encoding="utf-8"))
    assert any(item["source_change_state"] == "deleted" for item in state["sources"])


def test_malformed_generated_markers_fail_closed(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    project = vault / "projects" / "semantic-fixture" / "project.md"
    before = project.read_bytes()
    project.write_text("<!-- atlas:generated:start -->\nuser text\n", encoding="utf-8")
    malformed = project.read_bytes()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert project.read_bytes() == malformed
    assert project.read_bytes() != before


def test_unchanged_ingestion_has_zero_filesystem_writes(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    tracked = [
        vault / "projects" / "semantic-fixture" / "project.md",
        vault / "state" / "sources.json",
        vault / "generated" / "reports" / "ingestion-report.json",
    ]
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    before = {path: (path.read_bytes(), os.stat(path).st_mtime_ns) for path in tracked}
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    after = {path: (path.read_bytes(), os.stat(path).st_mtime_ns) for path in tracked}
    assert after == before


def test_corrupt_source_state_fails_closed_before_ingestion_writes(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    state_path = vault / "state" / "sources.json"
    state_path.write_text(
        json.dumps({"schema_version": 999, "sources": [{"source_id": "source-bad"}]}),
        encoding="utf-8",
    )
    project = vault / "projects" / "semantic-fixture" / "project.md"
    before = project.read_bytes()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert project.read_bytes() == before


def test_deleted_source_then_immediate_noop_remains_valid_and_zero_write(
    tmp_path: Path,
) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    (source / "ARCHITECTURE.md").unlink()
    deleted_manifest = tmp_path / "deleted.json"
    assert main(["discover", "--source", str(source), "--output", str(deleted_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(deleted_manifest), "--vault", str(vault)]) == EXIT_OK
    state = json.loads((vault / "state/sources.json").read_text())
    assert any(item["source_change_state"] == "deleted" for item in state["sources"])
    before = _snapshot(vault)
    assert main(["ingest", "--manifest", str(deleted_manifest), "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_modified_restore_and_rename_source_states_are_separate(tmp_path: Path) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    (source / "README.md").write_text("# Changed\n", encoding="utf-8")
    modified_manifest = tmp_path / "modified.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(modified_manifest)])
        == EXIT_OK
    )
    assert main(["ingest", "--manifest", str(modified_manifest), "--vault", str(vault)]) == EXIT_OK
    modified_state = json.loads((vault / "state/sources.json").read_text())
    assert any(item["source_change_state"] == "modified" for item in modified_state["sources"])
    assert main(["ingest", "--manifest", str(modified_manifest), "--vault", str(vault)]) == EXIT_OK
    stable = _snapshot(vault)
    assert main(["ingest", "--manifest", str(modified_manifest), "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == stable

    (source / "ARCHITECTURE.md").unlink()
    deleted_manifest = tmp_path / "deleted-for-restore.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(deleted_manifest)])
        == EXIT_OK
    )
    assert main(["ingest", "--manifest", str(deleted_manifest), "--vault", str(vault)]) == EXIT_OK
    deleted_state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    architecture_lineage = next(
        item["source_lineage_id"]
        for item in deleted_state["sources"]
        if item["current_path"] == "ARCHITECTURE.md"
    )
    (source / "ARCHITECTURE.md").write_text("# Restored with changed content\n", encoding="utf-8")
    restored_manifest = tmp_path / "restored.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(restored_manifest)])
        == EXIT_OK
    )
    restored_payload = json.loads(restored_manifest.read_text(encoding="utf-8"))
    for item in restored_payload["sources"]:
        if item["path"] == "ARCHITECTURE.md":
            item["source_lineage_id"] = architecture_lineage
    restored_manifest.write_text(json.dumps(restored_payload), encoding="utf-8")
    assert main(["ingest", "--manifest", str(restored_manifest), "--vault", str(vault)]) == EXIT_OK
    restored_state = json.loads((vault / "state/sources.json").read_text())
    assert any(item["source_change_state"] == "restored" for item in restored_state["sources"])

    (source / "ARCHITECTURE.md").unlink()
    rename_deleted = tmp_path / "rename-deleted.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(rename_deleted)])
        == EXIT_OK
    )
    assert (
        main(["ingest", "--manifest", str(rename_deleted), "--vault", str(vault)])
        == EXIT_OK
    )
    (source / "ARCHITECTURE-renamed.md").write_text(
        "# Restored with changed content\n", encoding="utf-8"
    )
    renamed_manifest = tmp_path / "renamed.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(renamed_manifest)])
        == EXIT_OK
    )
    renamed_payload = json.loads(renamed_manifest.read_text(encoding="utf-8"))
    for item in renamed_payload["sources"]:
        if item["path"] == "ARCHITECTURE-renamed.md":
            item["source_lineage_id"] = architecture_lineage
    renamed_manifest.write_text(json.dumps(renamed_payload), encoding="utf-8")
    assert main(["ingest", "--manifest", str(renamed_manifest), "--vault", str(vault)]) == EXIT_OK
    renamed_state = json.loads((vault / "state/sources.json").read_text())
    assert any(
        item["source_change_state"] == "restored-elsewhere"
        for item in renamed_state["sources"]
    )
    renamed = next(
        item
        for item in renamed_state["sources"]
        if item["source_change_state"] == "restored-elsewhere"
    )
    assert renamed["source_lineage_id"]
    assert {entry["path"] for entry in renamed["path_history"]} >= {
        "ARCHITECTURE.md",
        "ARCHITECTURE-renamed.md",
    }
    assert len(
        {item["source_lineage_id"] for item in renamed_state["sources"]}
    ) == len(renamed_state["sources"])


def test_known_legacy_source_lifecycle_values_are_repaired_with_receipt(
    tmp_path: Path,
) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    state_path = vault / "state/sources.json"
    state = json.loads(state_path.read_text())
    legacy = []
    for item in state["sources"]:
        item = dict(item)
        legacy_value = "modified" if not legacy else "deleted"
        item.pop("document_lifecycle", None)
        item.pop("source_change_state", None)
        item["lifecycle"] = legacy_value
        legacy.append(item)
    state_path.write_text(json.dumps({"schema_version": 1, "sources": legacy}), encoding="utf-8")
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    repaired = json.loads(state_path.read_text())
    assert all("lifecycle" not in item for item in repaired["sources"])
    assert all(item["compatibility_repaired"] for item in repaired["sources"])
    receipts = list((vault / "receipts/source-lifecycle").glob("repair-*.json"))
    assert len(receipts) == 1
    assert "compatibility-repair" in receipts[0].read_text()
    migration_receipts = list((vault / "receipts/source-lineage").glob("migration-*.json"))
    assert len(migration_receipts) == len(repaired["sources"])
    before_replay = _snapshot(vault)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before_replay
    assert len(list((vault / "receipts/source-lineage").glob("migration-*.json"))) == len(
        repaired["sources"]
    )


def test_unknown_legacy_lifecycle_rejected_without_mutation(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    state_path = vault / "state/sources.json"
    state = json.loads(state_path.read_text())
    state["sources"][0]["lifecycle"] = "invented-state"
    before = _snapshot(vault)
    state_path.write_text(json.dumps(state), encoding="utf-8")
    after_corruption = _snapshot(vault)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    assert _snapshot(vault) == after_corruption
    assert before != after_corruption


def test_failed_genesis_leaves_marker_and_allocation_receipt_absent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    marker = source / ".atlas-project.yaml"
    marker.write_text("schema_version: 1\nproject:\n  id: failed-genesis\n", encoding="utf-8")
    (source / "README.md").write_text("# failed\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    project = vault / "projects" / "failed-genesis" / "project.md"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text("<!-- atlas:generated:start -->\n", encoding="utf-8")
    original_marker = marker.read_bytes()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    assert marker.read_bytes() == original_marker
    assert not list((vault / "receipts/source-lineage").glob("project-*.json"))


def test_project_directory_move_preserves_persisted_uuid(tmp_path: Path) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    marker = source / ".atlas-project.yaml"
    first_uuid = next(
        line.split(":", 1)[1].strip()
        for line in marker.read_text(encoding="utf-8").splitlines()
        if line.startswith("project_uuid:")
    )
    moved = tmp_path / "moved-source"
    source.rename(moved)
    moved_manifest = tmp_path / "moved.json"
    assert main(["discover", "--source", str(moved), "--output", str(moved_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(moved_manifest), "--vault", str(vault)]) == EXIT_OK
    moved_marker = moved / ".atlas-project.yaml"
    assert f"project_uuid: {first_uuid}" in moved_marker.read_text(encoding="utf-8")
    registry = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    assert {item["canonical_project_id"] for item in registry["sources"]} == {first_uuid}


def test_same_run_file_directory_move_preserves_lineage(tmp_path: Path) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    before = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    original = next(
        item["source_lineage_id"]
        for item in before["sources"]
        if item["current_path"] == "README.md"
    )
    moved_dir = source / "docs"
    moved_dir.mkdir()
    (source / "README.md").rename(moved_dir / "README.md")
    moved_manifest = tmp_path / "file-move.json"
    assert main(["discover", "--source", str(source), "--output", str(moved_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(moved_manifest), "--vault", str(vault)]) == EXIT_OK
    after = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    moved = next(item for item in after["sources"] if item["current_path"] == "docs/README.md")
    assert moved["source_lineage_id"] == original
    assert moved["source_change_state"] == "renamed"


@pytest.mark.parametrize("replacement", [b"# Architecture\n", b"# Changed architecture\n"])
def test_public_same_path_explicit_new_generation_uses_resolution(
    tmp_path: Path, replacement: bytes
) -> None:
    source, initial_manifest, vault = _workflow(tmp_path)
    initial_payload = json.loads(initial_manifest.read_text(encoding="utf-8"))
    original = next(
        item for item in initial_payload["sources"] if item["path"] == "ARCHITECTURE.md"
    )
    (source / "ARCHITECTURE.md").unlink()
    deleted_manifest = tmp_path / "deleted-slot.json"
    assert main(["discover", "--source", str(source), "--output", str(deleted_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(deleted_manifest), "--vault", str(vault)]) == EXIT_OK
    deleted_state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    old = next(
        item for item in deleted_state["sources"] if item["source_id"] == original["source_id"]
    )
    (source / "ARCHITECTURE.md").write_bytes(replacement)
    recreated_manifest = tmp_path / "recreated-slot.json"
    assert (
        main(["discover", "--source", str(source), "--output", str(recreated_manifest)])
        == EXIT_OK
    )
    recreated_payload = json.loads(recreated_manifest.read_text(encoding="utf-8"))
    recreated = next(
        item for item in recreated_payload["sources"] if item["path"] == "ARCHITECTURE.md"
    )
    assert recreated["source_id"] == old["source_id"]
    recreated["lineage_resolution"] = {
        "outcome": "create_new_generation",
        "authority": "curator_approved",
        "candidate_lineage_ids": [old["source_lineage_id"]],
        "reason": "explicit same-path new logical source",
    }
    recreated_manifest.write_text(json.dumps(recreated_payload), encoding="utf-8")
    assert main(["ingest", "--manifest", str(recreated_manifest), "--vault", str(vault)]) == EXIT_OK
    state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    current = next(
        item
        for item in state["sources"]
        if item["current_path"] == "ARCHITECTURE.md"
        and item["source_lineage_id"] != old["source_lineage_id"]
    )
    prior = next(
        item for item in state["sources"] if item["source_lineage_id"] == old["source_lineage_id"]
    )
    assert current["lineage_generation"] == 2
    assert current["source_lineage_id"] != old["source_lineage_id"]
    assert current["supersedes_lineage"] == old["source_lineage_id"]
    assert prior["superseded_by_lineage"] == current["source_lineage_id"]
    assert len(list((vault / "receipts/source-lineage").glob("generation-*.json"))) == 1
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    before = _snapshot(vault)
    assert main(["ingest", "--manifest", str(recreated_manifest), "--vault", str(vault)]) == EXIT_OK
    assert _snapshot(vault) == before


def test_public_same_path_explicit_new_generation_uses_highest_retired_generation(
    tmp_path: Path,
) -> None:
    source, initial_manifest, vault = _workflow(tmp_path)
    initial_payload = json.loads(initial_manifest.read_text(encoding="utf-8"))
    original = next(
        item for item in initial_payload["sources"] if item["path"] == "ARCHITECTURE.md"
    )
    (source / "ARCHITECTURE.md").unlink()
    first_deleted = tmp_path / "first-deleted.json"
    assert main(["discover", "--source", str(source), "--output", str(first_deleted)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(first_deleted), "--vault", str(vault)]) == EXIT_OK
    for content, index in ((b"# Second generation\n", 2), (b"# Third generation\n", 3)):
        (source / "ARCHITECTURE.md").write_bytes(content)
        manifest = tmp_path / f"generation-{index}.json"
        assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        prior_state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
        retired = [
            item
            for item in prior_state["sources"]
            if item["source_id"] == original["source_id"]
            or item.get("supersedes_lineage")
        ]
        for item in payload["sources"]:
            if item["path"] == "ARCHITECTURE.md":
                item["lineage_resolution"] = {
                    "outcome": "create_new_generation",
                    "authority": "curator_approved",
                    "candidate_lineage_ids": [item["source_lineage_id"] for item in retired],
                    "reason": "explicit successive same-path generation",
                }
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
        state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
        assert max(item["lineage_generation"] for item in state["sources"]) == index
        if index == 2:
            (source / "ARCHITECTURE.md").unlink()
            retire_manifest = tmp_path / "retire-second.json"
            assert (
                main(["discover", "--source", str(source), "--output", str(retire_manifest)])
                == EXIT_OK
            )
            assert (
                main(["ingest", "--manifest", str(retire_manifest), "--vault", str(vault)])
                == EXIT_OK
            )


def test_independent_projects_receive_distinct_project_uuids(tmp_path: Path) -> None:
    source = tmp_path / "projects"
    first = source / "first"
    second = source / "second"
    first.mkdir(parents=True)
    second.mkdir()
    for directory, project in ((first, "first-independent"), (second, "second-independent")):
        (directory / ".atlas-project.yaml").write_text(
            f"schema_version: 1\nproject:\n  id: {project}\n", encoding="utf-8"
        )
        (directory / "README.md").write_text("# identical\n", encoding="utf-8")
    manifest = tmp_path / "independent.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert ingest(manifest, vault)["ok"] is True
    uuids = {
        line.split(":", 1)[1].strip()
        for directory in (first, second)
        for line in (directory / ".atlas-project.yaml").read_text(encoding="utf-8").splitlines()
        if line.startswith("project_uuid:")
    }
    assert len(uuids) == 2


def test_project_uuid_genesis_is_injected_once_and_replay_is_zero_write(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    marker = source / ".atlas-project.yaml"
    marker.write_text("schema_version: 1\nproject:\n  id: genesis-fixture\n", encoding="utf-8")
    (source / "README.md").write_bytes(b"raw\x00bytes\n")
    manifest = tmp_path / "manifest.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    expected = "00000000-0000-4000-8000-000000000011"
    calls = 0

    def provider() -> str:
        nonlocal calls
        calls += 1
        return expected

    assert ingest(manifest, vault, uuid_provider=provider)["ok"] is True
    assert calls == 1
    assert f"project_uuid: {expected}" in marker.read_text(encoding="utf-8")
    allocation_receipts = list((vault / "receipts/source-lineage").glob("project-*.json"))
    assert len(allocation_receipts) == 1
    before = _snapshot(vault)
    assert ingest(manifest, vault, uuid_provider=lambda: (_ for _ in ()).throw(AssertionError()))[
        "ok"
    ] is True
    assert _snapshot(vault) == before


def test_concurrent_project_initializers_have_one_uuid_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    marker = source / ".atlas-project.yaml"
    marker.write_text("schema_version: 1\nproject:\n  id: concurrent-fixture\n", encoding="utf-8")
    (source / "README.md").write_text("# concurrent\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    candidates = iter(
        [
            "00000000-0000-4000-8000-000000000021",
            "00000000-0000-4000-8000-000000000022",
        ]
    )

    def provider() -> str:
        return next(candidates)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _index: ingest(manifest, vault, uuid_provider=provider),
                range(2),
            )
        )
    assert all(result["ok"] for result in results)
    marker_uuid = next(
        line.split(":", 1)[1].strip()
        for line in marker.read_text(encoding="utf-8").splitlines()
        if line.startswith("project_uuid:")
    )
    assert marker_uuid in {
        "00000000-0000-4000-8000-000000000021",
        "00000000-0000-4000-8000-000000000022",
    }
    assert len(list((vault / "receipts/source-lineage").glob("project-*.json"))) == 1
    assert not list((vault / ".atlas/identity-locks").glob("*.lock"))


def test_public_multiprocess_initializers_have_one_committed_uuid(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: process-fixture\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# process\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    command = [
        sys.executable,
        "-m",
        "project_atlas.cli",
        "ingest",
        "--manifest",
        str(manifest),
        "--vault",
        str(vault),
    ]
    processes = [
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=30) for process in processes]
    assert [process.returncode for process in processes] == [EXIT_OK, EXIT_OK]
    assert all(stdout for stdout, _stderr in results)
    marker = source / ".atlas-project.yaml"
    committed_uuid = next(
        line.split(":", 1)[1].strip()
        for line in marker.read_text(encoding="utf-8").splitlines()
        if line.startswith("project_uuid:")
    )
    state = json.loads((vault / "state/sources.json").read_text(encoding="utf-8"))
    assert {item["canonical_project_id"] for item in state["sources"]} == {committed_uuid}
    assert len(list((vault / "receipts/source-lineage").glob("project-*.json"))) == 1
    assert not list((vault / ".atlas/identity-locks").glob("*.lock"))


def test_duplicate_active_project_uuid_fails_before_promotion(tmp_path: Path) -> None:
    source = tmp_path / "source"
    first = source / "first"
    second = source / "second"
    first.mkdir(parents=True)
    second.mkdir()
    shared_uuid = "00000000-0000-4000-8000-000000000031"
    for directory, project in ((first, "first-project"), (second, "second-project")):
        (directory / ".atlas-project.yaml").write_text(
            f"schema_version: 1\nproject:\n  id: {project}\nproject_uuid: {shared_uuid}\n",
            encoding="utf-8",
        )
        (directory / "README.md").write_text(f"# {project}\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    write_manifest(discover(source), manifest)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    before = _snapshot(vault)
    with pytest.raises(ValueError, match="duplicate active project_uuid"):
        ingest(manifest, vault)
    assert _snapshot(vault) == before


def test_malformed_marker_in_one_project_aborts_before_other_project_writes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "multi-source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: project-a\n", encoding="utf-8"
    )
    (nested / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: project-b\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# A\n", encoding="utf-8")
    (nested / "README.md").write_text("# B\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    target = vault / "projects" / "project-b" / "project.md"
    target.write_text("<!-- atlas:generated:start -->\n", encoding="utf-8")
    imported_before = sorted((vault / "sources" / "imported-documents").iterdir())
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert sorted((vault / "sources" / "imported-documents").iterdir()) == imported_before


def test_cross_project_preflight_preserves_vault_until_marker_is_fixed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "multi-source"
    first = source / "aaa"
    second = source / "zzz"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: aaa-first\n", encoding="utf-8"
    )
    (second / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: zzz-second\n", encoding="utf-8"
    )
    (first / "README.md").write_text("# First\n", encoding="utf-8")
    (second / "README.md").write_text("# Second\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK

    (first / "NOTES.md").write_text("# Newly added\n", encoding="utf-8")
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    malformed = vault / "projects" / "zzz-second" / "project.md"
    malformed.write_text("<!-- atlas:generated:start -->\n", encoding="utf-8")
    before = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }

    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    after = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert after == before

    malformed.write_text(
        malformed.read_text(encoding="utf-8")
        + "<!-- atlas:generated:end -->\n",
        encoding="utf-8",
    )
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    notes_record = next(
        item
        for item in json.loads(manifest.read_text())["sources"]
        if item["path"] == "aaa/NOTES.md"
    )
    imported = vault / "sources" / "imported-documents" / f"{notes_record['source_id']}.md"
    assert imported.read_text(encoding="utf-8") == "# Newly added\n"
    assert (
        len(
            list(
                (vault / "sources" / "imported-documents").glob(
                    f"{notes_record['source_id']}.*"
                )
            )
        )
        == 1
    )
    state = json.loads((vault / "state" / "sources.json").read_text(encoding="utf-8"))
    assert sum(item["path"] == "aaa/NOTES.md" for item in state["sources"]) == 1
