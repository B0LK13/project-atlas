"""Integration acceptance for AS-INGEST-MANIFEST-001."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.integration
PILOTS = Path("tests/fixtures/pilots")


def _copy_pilots(tmp_path: Path) -> Path:
    pilots = tmp_path / "pilots-copy"
    shutil.copytree(PILOTS, pilots)
    return pilots


def test_in_batch_deletion_drops_snapshot_row(tmp_path: Path) -> None:
    """Full rediscover of one project that removed a file tombstones registry
    and removes that source_id from the merged discovery snapshot.
    """
    pilots = _copy_pilots(tmp_path)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK

    manifest_1 = tmp_path / "m1.json"
    assert main(["discover", "--source", str(pilots), "--output", str(manifest_1)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest_1),
            "--vault",
            str(vault),
            "--source",
            str(pilots),
        ]
    ) == EXIT_OK

    before = json.loads(
        (vault / "sources" / "manifests" / "source-manifest.json").read_text(encoding="utf-8")
    )
    target = next(
        item
        for item in before["sources"]
        if item["likely_project"] == "nebula" and item["path"].endswith("README.md")
    )
    removed_id = target["source_id"]
    (pilots / "nebula" / "README.md").unlink()

    manifest_2 = tmp_path / "m2.json"
    assert main(["discover", "--source", str(pilots), "--output", str(manifest_2)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest_2),
            "--vault",
            str(vault),
            "--source",
            str(pilots),
        ]
    ) == EXIT_OK

    after = json.loads(
        (vault / "sources" / "manifests" / "source-manifest.json").read_text(encoding="utf-8")
    )
    assert removed_id not in {item["source_id"] for item in after["sources"]}
    assert {item["likely_project"] for item in after["sources"]} == {
        "nebula",
        "black-agency-os",
        "dark-factory",
    }

    registry = json.loads((vault / "state" / "sources.json").read_text(encoding="utf-8"))
    removed_record = next(
        item for item in registry["sources"] if item.get("source_id") == removed_id
    )
    assert removed_record["source_change_state"] in {"deleted", "restored-elsewhere"}


def test_identical_ingest_replay_is_byte_stable_for_merged_snapshot(tmp_path: Path) -> None:
    pilots = _copy_pilots(tmp_path)
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK

    manifest = tmp_path / "m.json"
    assert main(["discover", "--source", str(pilots), "--output", str(manifest)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest),
            "--vault",
            str(vault),
            "--source",
            str(pilots),
        ]
    ) == EXIT_OK

    # SEC-002: rediscover after genesis, then baseline + replay must be byte-stable.
    assert main(["discover", "--source", str(pilots), "--output", str(manifest)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest),
            "--vault",
            str(vault),
            "--source",
            str(pilots),
        ]
    ) == EXIT_OK

    snapshot_path = vault / "sources" / "manifests" / "source-manifest.json"
    report_path = vault / "generated" / "reports" / "ingestion-report.json"
    first_snapshot = snapshot_path.read_bytes()
    first_report = report_path.read_bytes()

    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest),
            "--vault",
            str(vault),
            "--source",
            str(pilots),
        ]
    ) == EXIT_OK
    assert snapshot_path.read_bytes() == first_snapshot
    assert report_path.read_bytes() == first_report
