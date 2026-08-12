"""AS-DEMO-2.2-RECOVERY-ID-001 — fresh bootstrap is recovery-capable.

Product-level regression for D-PROJECT-ATLAS-CLOUD-DEMO-RECOVERY-019:

    fresh temp vault
      → atlas init (establishes .atlas/vault.json)
      → discover / ingest / build-indexes / build-portfolio / validate
      → assert canonical identity exists
      → snapshot
      → destroy disposable target
      → restore
      → rebuild derived
      → validate
      → post-restore identity equality + semantic cold fingerprint

This test fails on main before remediation (init left no vault.json).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from project_atlas.app_service import open_app_service
from project_atlas.ask2 import ask_atlas_2
from project_atlas.backup import create_snapshot, restore_bundle, verify_bundle
from project_atlas.cli import EXIT_OK, main
from project_atlas.knowledge_diff import diff_knowledge, read_as_of
from project_atlas.vault_identity import read_vault_identity

pytestmark = pytest.mark.integration

DEMO_ESTATE = Path("tests/fixtures/demo/estate")
PROJECT = "harbor-api"
KNOWN_QUESTION = "audit logging"
UNKNOWN_QUESTION = "kubernetes gpu quota autoscaling"
CONFLICT_QUESTION = "postgresql"
KDIFF_SUBJECT = "doc:harbor-api-datastore"
KDIFF_FIELD = "runtime"
T1 = "2024-03-01"
T2 = "2024-10-01"
_EPHEMERAL_MARKERS = (".atlas-stage", ".atlas-backup")


def _cold_files(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(seg in {".tmp", "__pycache__", ".git"} for seg in rel.split("/")):
            continue
        if path.name.endswith(_EPHEMERAL_MARKERS):
            continue
        if rel.startswith("generated/"):
            continue
        out[rel] = path.read_bytes()
    return out


def _fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(files[rel]).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _pipeline(vault: Path, source: Path, manifest: Path) -> None:
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert (vault / ".atlas" / "vault.json").is_file(), "FRESH_BOOTSTRAP_IDENTITY"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_fresh_bootstrap_identity_and_snapshot_pipeline(tmp_path: Path) -> None:
    source = tmp_path / "estate"
    shutil.copytree(DEMO_ESTATE, source)
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
    _pipeline(vault, source, manifest)

    identity = read_vault_identity(vault)
    assert identity.vault_id == "atlas-main"
    assert identity.vault_uuid
    identity_bytes = (vault / ".atlas" / "vault.json").read_bytes()

    # BOOTSTRAP_IDEMPOTENCY: second init preserves identity bytes.
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert (vault / ".atlas" / "vault.json").read_bytes() == identity_bytes

    # Golden product surface still works after identity-bearing bootstrap.
    known = ask_atlas_2(vault, question=KNOWN_QUESTION, project_id=PROJECT)
    assert known["status"] == "known"
    unknown = ask_atlas_2(vault, question=UNKNOWN_QUESTION, project_id=PROJECT)
    assert unknown["status"] == "unknown"
    conflict = ask_atlas_2(vault, question=CONFLICT_QUESTION, project_id=PROJECT)
    assert conflict["status"] == "conflict"
    at_t1 = read_as_of(vault, project_id=PROJECT, as_of_valid_time=T1)
    at_t2 = read_as_of(vault, project_id=PROJECT, as_of_valid_time=T2)
    assert at_t1 and at_t2
    diff = diff_knowledge(vault, project_id=PROJECT, t1=T1, t2=T2)
    value_changed = {(d["subject"], d["field"]) for d in diff.get("value_changed", [])}
    assert (KDIFF_SUBJECT, KDIFF_FIELD) in value_changed

    original = _cold_files(vault)
    before_fp = _fingerprint(original)
    before_identity = identity_bytes
    logical_id = identity.vault_uuid

    bundle = tmp_path / "bundle"
    assert main(["snapshot", "--vault", str(vault), "--output", str(bundle)]) == EXIT_OK
    verify_bundle(bundle)

    shutil.rmtree(vault)
    target = tmp_path / "restored"
    restore_bundle(bundle, target, tier="T3", expected_vault_logical_id=logical_id)

    restored = _cold_files(target)
    missing = sorted(set(original) - set(restored))
    assert not missing, f"cold content absent after restore: {missing}"
    for rel in sorted(original):
        assert restored[rel] == original[rel], f"byte drift after restore: {rel}"
    assert _fingerprint({k: restored[k] for k in original}) == before_fp, "POST_RESTORE_EQUIVALENCE"

    restored_identity = (target / ".atlas" / "vault.json").read_bytes()
    assert restored_identity == before_identity, "POST_RESTORE_IDENTITY_EQUALITY"
    assert read_vault_identity(target).vault_uuid == identity.vault_uuid

    assert main(["build-indexes", "--vault", str(target)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(target)]) == EXIT_OK
    assert main(["validate", "--vault", str(target)]) == EXIT_OK

    # POST_RESTART_EQUIVALENCE: reopen product surface on restored vault.
    service = open_app_service(target)
    health = service.health()
    assert "package_id" in health
    assert "vault_health" in health
    known2 = ask_atlas_2(target, question=KNOWN_QUESTION, project_id=PROJECT)
    assert known2["status"] == "known"
    unknown2 = ask_atlas_2(target, question=UNKNOWN_QUESTION, project_id=PROJECT)
    assert unknown2["status"] == "unknown"
    conflict2 = ask_atlas_2(target, question=CONFLICT_QUESTION, project_id=PROJECT)
    assert conflict2["status"] == "conflict"
    snap = service.snapshot()
    assert snap["schema_version"] == 1


def test_fresh_init_alone_mints_identity_readable_by_backup(tmp_path: Path) -> None:
    """Init alone mints identity; backup reader accepts it (snapshot needs corpus)."""
    from project_atlas.backup import read_vault_logical_id

    vault = tmp_path / "empty-vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    marker = vault / ".atlas" / "vault.json"
    assert marker.is_file()
    logical = read_vault_logical_id(vault)
    assert logical
    # Snapshot remains non-minting and still requires cold-domain corpus.
    with pytest.raises(Exception, match=r"missing required domain|incomplete"):
        create_snapshot(vault, tmp_path / "empty-bundle")
