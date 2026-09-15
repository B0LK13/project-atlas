"""AS-BACKUP-001 — RECOVERY_GATE portable journey (full certified path).

Exercises the end-to-end recovery contract on a real vault built from the
committed demo estate fixture:

    init → discover → ingest → build-indexes → build-portfolio → stamp identity
      → validate → verified snapshot → destroy → restore → validate
      → rebuild derived → SEMANTIC fingerprint equals original cold content.

This is the regression that would have caught the F1 omission: before the
completeness fix the OKF category directories, root ``log.md`` and
``receipts/claims/*.json`` were silently dropped from the cold bundle and were
ABSENT after restore, so the restored vault was not a byte-complete
reproduction of the original's contract-guaranteed content.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from project_atlas.backup import create_snapshot, restore_bundle, verify_bundle
from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.integration

DEMO_ESTATE = Path("tests/fixtures/demo/estate")
VAULT_LOGICAL_ID = "fixture-recovery-gate-journey"
_EPHEMERAL_MARKERS = (".atlas-stage", ".atlas-backup")


def _stamp_identity(vault: Path) -> None:
    (vault / ".atlas").mkdir(parents=True, exist_ok=True)
    (vault / ".atlas" / "vault.json").write_text(
        json.dumps(
            {
                "vault_logical_id": VAULT_LOGICAL_ID,
                "vault_uuid": VAULT_LOGICAL_ID,
                "vault_id": "recovery-gate-journey",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _build_vault(source: Path, tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert (
        main(
            ["ingest", "--manifest", str(manifest), "--vault", str(vault), "--source", str(source)]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    _stamp_identity(vault)
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


def _cold_files(root: Path) -> dict[str, bytes]:
    """Persisted, non-ephemeral files except warm-derived D5 (generated/)."""
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


def test_recovery_gate_portable_journey(tmp_path: Path) -> None:
    source = tmp_path / "estate"
    shutil.copytree(DEMO_ESTATE, source)
    vault = _build_vault(source, tmp_path)

    original = _cold_files(vault)
    original_fingerprint = _fingerprint(original)

    # Content classes F1 used to drop must exist in the built vault.
    assert "log.md" in original
    assert any(k.startswith("receipts/claims/") for k in original)
    assert {"capabilities", "decisions", "infrastructure", "standards", "technologies"} <= {
        k.split("/", 1)[0] for k in original
    }

    bundle = tmp_path / "bundle"
    create_snapshot(vault, bundle, include_d5=False)
    verify_bundle(bundle)

    # Destroy the live vault, then restore onto a fresh empty target.
    shutil.rmtree(vault)
    target = tmp_path / "restored"
    restore_bundle(bundle, target, tier="T3", expected_vault_logical_id=VAULT_LOGICAL_ID)

    restored = _cold_files(target)
    missing = sorted(set(original) - set(restored))
    assert not missing, f"F1 regression: cold content absent after restore: {missing}"
    for rel in sorted(original):
        assert restored[rel] == original[rel], f"byte drift after restore: {rel}"

    # Contract-guaranteed semantic fingerprint is reproduced exactly.
    assert _fingerprint({k: restored[k] for k in original}) == original_fingerprint

    # Rebuild the derived plane (D5) and re-validate the restored vault.
    assert main(["build-indexes", "--vault", str(target)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(target)]) == EXIT_OK
    assert main(["validate", "--vault", str(target)]) == EXIT_OK
