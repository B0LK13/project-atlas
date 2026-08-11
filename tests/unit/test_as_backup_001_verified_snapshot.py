"""AS-BACKUP-001 Verified Atlas Snapshot — fixture certification tests.

Contract: gen4-parallel-wave-007/AS-BACKUP-001-CONTRACT.md
Entry gate: gen4-next-wave-parallel-001/AS-BACKUP-001-ENTRY-GATE.md

Certification path (fixture / disposable only — INV-006):
  CREATE → SNAPSHOT → CORRUPT COPY → RESTORE → VALIDATE → COMPARE

Does not touch knowledge_compiler, Graph-003, or MODEL-001B surfaces.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas.backup import (
    BackupError,
    collect_identity_samples,
    compare_member_digests,
    create_snapshot,
    find_promote_orphans,
    protected_region_digest,
    read_vault_logical_id,
    restore_bundle,
    verify_bundle,
)
from project_atlas.cli import main
from project_atlas.indexes import build_indexes
from project_atlas.scaffold import create_scaffold
from project_atlas.schema import validate_record
from project_atlas.validation import validate

VAULT_LOGICAL_ID = "fixture-backup-001-vault"
PROJECT_UUID = "11111111-2222-4333-8444-555555555555"
SOURCE_LINEAGE_ID = "lineage-backup-001-fixture"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def _fixture_vault(tmp_path: Path) -> Path:
    """Disposable cold-certifiable vault (D1-D4 + D6; optional D5 omitted)."""
    vault = tmp_path / "source-vault"
    create_scaffold(vault)
    _write(
        vault / ".atlas" / "vault.json",
        {
            "vault_logical_id": VAULT_LOGICAL_ID,
            "vault_uuid": VAULT_LOGICAL_ID,
            "vault_id": "atlas-backup-fixture",
        },
    )
    _write(
        vault / ".atlas-project.yaml",
        f"project: backup-fixture\nproject_uuid: {PROJECT_UUID}\n",
    )
    evidence = vault / "sources" / "imported-documents" / "brief.md"
    _write(evidence, "# Brief\n\nFixture evidence for AS-BACKUP-001.\n")
    project_note = vault / "projects" / "backup-fixture" / "project.md"
    _write(
        project_note,
        (
            "# Backup Fixture\n\n"
            "<!-- BEGIN HUMAN: notes -->\n"
            "Operator note — must survive restore byte-for-byte.\n"
            "<!-- END HUMAN: notes -->\n"
        ),
    )
    _write(
        vault / "state" / "sources.json",
        {
            "schema_version": 1,
            "sources": [
                {
                    "source_id": "src-backup-001",
                    "source_lineage_id": SOURCE_LINEAGE_ID,
                    "sha256": "a" * 64,
                    "current_content_sha256": "a" * 64,
                    "canonical_project_id": PROJECT_UUID,
                    "current_path": "sources/imported-documents/brief.md",
                }
            ],
        },
    )
    _write(
        vault / "routing" / "receipts" / "session-receipt.json",
        {
            "receipt_id": "rcp-backup-001",
            "skill_sha256": "b" * 64,
            "outcome": "ok",
        },
    )
    # Optional warm D5 present on source vault but omitted from cold bundle.
    _write(
        vault / "generated" / "indexes" / "sources.json",
        {"schema_version": 1, "ids": [SOURCE_LINEAGE_ID]},
    )
    # EPHEMERAL orphans must be excluded when cleaned; tests inject separately.
    return vault


def test_canonical_fixture_create_snapshot_corrupt_restore_validate_compare(
    tmp_path: Path,
) -> None:
    """BACKUP-001 acceptance #1 — full disposable drill (§7 / §28 restore)."""
    vault = _fixture_vault(tmp_path)
    before = collect_identity_samples(vault)
    note = (vault / "projects" / "backup-fixture" / "project.md").read_text(encoding="utf-8")
    region_before = protected_region_digest(note)

    bundle = tmp_path / "bundle"
    created = create_snapshot(vault, bundle, include_d5=False)
    assert "D5" not in created["domains_included"]
    assert set(created["domains_included"]) >= {"D1", "D2", "D3", "D4", "D6"}
    verify_bundle(bundle)
    validate_record(created["manifest"], "backup-manifest")
    validate_record(created["receipt"], "backup-receipt")

    # Corrupt only a disposable copy — never the sole good snapshot.
    damaged = tmp_path / "damaged-copy"
    from project_atlas.backup import copy_tree

    copy_tree(vault, damaged)
    damaged_note = damaged / "projects" / "backup-fixture" / "project.md"
    damaged_note.write_text("# CORRUPTED\n", encoding="utf-8")
    (damaged / "state" / "sources.json").unlink()

    target = tmp_path / "restored"
    restored = restore_bundle(bundle, target, tier="T3")
    assert restored["identity_samples"]["vault_logical_id"] == before["vault_logical_id"]
    assert restored["identity_samples"]["project_uuids"] == before["project_uuids"]
    assert restored["identity_samples"]["source_lineage_ids"] == before["source_lineage_ids"]

    restored_note = (target / "projects" / "backup-fixture" / "project.md").read_text(
        encoding="utf-8"
    )
    assert protected_region_digest(restored_note) == region_before
    assert "Operator note — must survive restore byte-for-byte." in restored_note
    assert not (target / "generated" / "indexes" / "sources.json").exists()

    build_indexes(target)
    result = validate(target)
    assert result["ok"], result["errors"]

    compare_member_digests(bundle, target, domains=["D1", "D2", "D3", "D4", "D6"])
    # Damaged copy remains damaged — restore did not heal it in place.
    assert damaged_note.read_text(encoding="utf-8") == "# CORRUPTED\n"


def test_manifest_excludes_ephemeral_and_matches_digests(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    orphan = vault / "projects" / "backup-fixture" / ".project.md.tx1.atlas-backup"
    orphan.write_text("orphan", encoding="utf-8")
    assert find_promote_orphans(vault)

    with pytest.raises(BackupError, match="orphans"):
        create_snapshot(vault, tmp_path / "bundle-refuse")

    orphan.unlink()
    # Inject ephemeral into tree after clean gate would pass — still excluded if present
    # under a path that classify would otherwise include: stage beside evidence.
    stage = vault / "sources" / "imported-documents" / ".brief.md.tx.atlas-stage"
    stage.write_text("secret-looking-stage-payload", encoding="utf-8")
    # Clean gate still refuses.
    with pytest.raises(BackupError, match="orphans"):
        create_snapshot(vault, tmp_path / "bundle-stage")

    stage.unlink()
    bundle = tmp_path / "bundle-ok"
    created = create_snapshot(vault, bundle)
    paths = {m["path"] for m in created["manifest"]["members"]}
    assert not any(".atlas-stage" in p or ".atlas-backup" in p for p in paths)
    verify_bundle(bundle)


def test_digest_mismatch_fail_closed(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    bundle = tmp_path / "bundle"
    create_snapshot(vault, bundle)
    member = next(
        p
        for p in (bundle / "domains" / "d2-vault").rglob("*.md")
        if p.is_file()
    )
    member.write_bytes(member.read_bytes() + b"\n# tamper\n")
    with pytest.raises(BackupError, match="digest mismatch"):
        verify_bundle(bundle)


def test_wrong_mount_refuse(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    bundle = tmp_path / "bundle"
    create_snapshot(vault, bundle)
    with pytest.raises(BackupError, match="wrong-mount"):
        restore_bundle(
            bundle,
            tmp_path / "empty-target",
            expected_vault_logical_id="other-vault-id",
        )


def test_refuse_nonempty_restore_target(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    bundle = tmp_path / "bundle"
    create_snapshot(vault, bundle)
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "stale.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(BackupError, match="non-empty"):
        restore_bundle(bundle, dirty, tier="T2")


def test_missing_d3_restore_identity_stable(tmp_path: Path) -> None:
    """RS-03 style: drop state on a copy, restore D3 from bundle."""
    vault = _fixture_vault(tmp_path)
    before = collect_identity_samples(vault)
    bundle = tmp_path / "bundle"
    create_snapshot(vault, bundle)
    target = tmp_path / "restored-d3"
    restore_bundle(bundle, target, tier="T2")
    after = collect_identity_samples(target)
    assert after == before
    assert (target / "state" / "sources.json").is_file()


def test_replay_deterministic_manifest(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    a = create_snapshot(vault, tmp_path / "bundle-a")
    b = create_snapshot(vault, tmp_path / "bundle-b")
    assert a["snapshot_id"] == b["snapshot_id"]
    assert a["manifest"]["members"] == b["manifest"]["members"]
    text_a = (tmp_path / "bundle-a" / "MANIFEST.json").read_text(encoding="utf-8")
    text_b = (tmp_path / "bundle-b" / "MANIFEST.json").read_text(encoding="utf-8")
    assert text_a == text_b
    assert "generated.at" not in text_a


def test_receipt_has_no_secret_matched_content(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    secretish = "AKIAIOSFODNN7EXAMPLE"
    _write(vault / "sources" / "imported-documents" / "notes.md", f"token={secretish}\n")
    created = create_snapshot(vault, tmp_path / "bundle")
    receipt_text = json.dumps(created["receipt"])
    assert secretish not in receipt_text
    restored = restore_bundle(tmp_path / "bundle", tmp_path / "out", tier="T3")
    assert secretish not in json.dumps(restored["receipt"])


def test_unbalanced_markers_fail_closed(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    bad = vault / "projects" / "backup-fixture" / "broken.md"
    _write(bad, "<!-- BEGIN HUMAN: notes -->\nno end\n")
    with pytest.raises(BackupError, match="unbalanced protection markers"):
        create_snapshot(vault, tmp_path / "bundle")


def test_path_safety_rejects_home(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    with pytest.raises(BackupError, match="home directory"):
        create_snapshot(vault, Path.home())


def test_create_snapshot_refuses_file_symlink_escape(tmp_path: Path) -> None:
    """SEC-ADV004B-A-001: file symlink → outside bytes must not pack."""
    vault = _fixture_vault(tmp_path)
    outside = tmp_path / "outside-secret.md"
    outside.write_text("FILE_SYMLINK_LEAK_XYZ\n", encoding="utf-8")
    link = vault / "projects" / "backup-fixture" / "leak.md"
    try:
        link.symlink_to(outside)
    except OSError as exc:  # pragma: no cover - environment without symlink privilege
        pytest.skip(f"symlink unavailable: {exc}")
    assert link.is_symlink()
    assert Path(os.path.realpath(link)) == Path(os.path.realpath(outside))
    with pytest.raises(BackupError, match="symlink/junction escape"):
        create_snapshot(vault, tmp_path / "bundle-symlink")
    assert read_vault_logical_id(vault) == VAULT_LOGICAL_ID


def test_create_snapshot_refuses_windows_junction_escape(tmp_path: Path) -> None:
    """SEC-ADV004B-A-001: Windows dir junction (is_symlink=False) must refuse."""
    if sys.platform != "win32":
        pytest.skip("Windows junction vector only")

    vault = _fixture_vault(tmp_path)
    outside = tmp_path / "outside-tree"
    outside.mkdir()
    (outside / "jsecret.md").write_text("JUNCTION_LEAK_XYZ\n", encoding="utf-8")
    # Replace vault/projects with a junction to outside (Path.is_symlink()==False).
    projects = vault / "projects"
    shutil.rmtree(projects)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(projects), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip(f"mklink /J unavailable: {completed.stderr or completed.stdout}")
    assert projects.is_dir()
    assert not projects.is_symlink(), "junction must not report as symlink"
    assert "JUNCTION_LEAK_XYZ" in (projects / "jsecret.md").read_text(encoding="utf-8")
    real_secret = Path(os.path.realpath(projects / "jsecret.md"))
    real_vault = Path(os.path.realpath(vault))
    assert not real_secret.is_relative_to(real_vault)
    with pytest.raises(BackupError, match="symlink/junction escape"):
        create_snapshot(vault, tmp_path / "bundle-junction")


def test_read_vault_logical_id_refuses_symlinked_identity(tmp_path: Path) -> None:
    """SEC-ADV004B-A-002: symlinked .atlas/vault.json must not stamp outside id."""
    vault = _fixture_vault(tmp_path)
    outside = tmp_path / "evil.json"
    outside.write_text(
        json.dumps({"vault_logical_id": "EVIL_OUTSIDE"}, indent=2) + "\n",
        encoding="utf-8",
    )
    identity = vault / ".atlas" / "vault.json"
    identity.unlink()
    try:
        identity.symlink_to(outside)
    except OSError as exc:  # pragma: no cover
        pytest.skip(f"symlink unavailable: {exc}")
    assert identity.is_symlink()
    with pytest.raises(BackupError, match="symlink/reparse escape"):
        read_vault_logical_id(vault)
    with pytest.raises(BackupError, match="symlink/reparse escape"):
        create_snapshot(vault, tmp_path / "bundle-evil-id")


def test_cli_snapshot_verify_and_restore(tmp_path: Path) -> None:
    vault = _fixture_vault(tmp_path)
    bundle = tmp_path / "cli-bundle"
    assert main(["snapshot", "--vault", str(vault), "--output", str(bundle)]) == 0
    assert main(["snapshot", "--verify", "--bundle", str(bundle)]) == 0
    target = tmp_path / "cli-restored"
    assert (
        main(
            [
                "restore",
                "--bundle",
                str(bundle),
                "--output",
                str(target),
                "--tier",
                "T3",
                "--expect-vault-logical-id",
                VAULT_LOGICAL_ID,
            ]
        )
        == 0
    )
    assert (target / ".atlas" / "vault.json").is_file()
    assert main(["restore", "--bundle", str(bundle), "--output", str(target)]) == 1
