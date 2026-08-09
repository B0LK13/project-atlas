"""AS-ADV-RELEASE-001 — Fixture-safe advanced release certification suite.

Combines recovery, determinism, and performance-baseline cases on disposable
vaults. Operational certification only — never stamps RELEASE CERTIFIED,
ESTATE PILOT PASSED, or WEB APPLICATION ACCEPTED.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from project_atlas.backup import create_snapshot, restore_bundle, verify_bundle
from project_atlas.discovery import discover, write_manifest
from project_atlas.indexes import build_indexes
from project_atlas.ingestion import ingest, recover_promote_orphans
from project_atlas.scaffold import create_scaffold
from project_atlas.schema import validate_record
from project_atlas.validation import validate

GENERATOR_ID = "atlas-adv-release-001"
PACKAGE_ID = "AS-ADV-RELEASE-001"
REPORT_SCHEMA = "adv-release-cert-report"
REPORT_RELATIVE = Path("generated") / "ops" / "adv-release-cert-report.json"

CaseId = Literal[
    "recovery_promote_noop",
    "recovery_snapshot_roundtrip",
    "determinism_pipeline",
    "perf_baseline_fixture",
]
CaseResult = Literal["pass", "fail"]
ReportStatus = Literal["certified", "failed", "partial"]

MATRIX_CASE_IDS: tuple[CaseId, ...] = (
    "recovery_promote_noop",
    "recovery_snapshot_roundtrip",
    "determinism_pipeline",
    "perf_baseline_fixture",
)


class AdvReleaseCertError(ValueError):
    """Raised when advanced release certification cannot proceed safely."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)




def _seed_source(source: Path) -> None:
    source.mkdir(parents=True, exist_ok=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: 11111111-2222-4333-8444-555555555555\n"
        "  name: adv-release-fixture\n",
        encoding="utf-8",
    )
    (source / "README.md").write_text(
        "# ADV-RELEASE fixture\n\nDeterministic evidence for certification.\n",
        encoding="utf-8",
    )


def _pipeline(source: Path, vault: Path, work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    manifest = work / "manifest.json"
    write_manifest(discover(source), manifest)
    ingest(manifest, vault)
    build_indexes(vault)
    validate(vault)


def _case_recovery_promote_noop(work: Path) -> dict[str, Any]:
    vault = work / "vault-promote"
    create_scaffold(vault)
    first = recover_promote_orphans(vault)
    second = recover_promote_orphans(vault)
    ok = (
        first.orphan_count == 0
        and second.orphan_count == 0
        and first.transactions_recovered == 0
        and second.transactions_recovered == 0
    )
    return {
        "case_id": "recovery_promote_noop",
        "result": "pass" if ok else "fail",
        "expected": "recover_promote_orphans noop on clean vault",
        "observed": (
            f"first orphans={first.orphan_count} tx={first.transactions_recovered}; "
            f"second orphans={second.orphan_count} tx={second.transactions_recovered}"
        ),
    }


def _case_recovery_snapshot_roundtrip(work: Path) -> dict[str, Any]:
    source = work / "src-snap"
    vault = work / "vault-snap"
    bundle = work / "bundle"
    restored = work / "restored"
    _seed_source(source)
    create_scaffold(vault)
    (vault / ".atlas").mkdir(parents=True, exist_ok=True)
    (vault / ".atlas" / "vault.json").write_text(
        json.dumps(
            {
                "vault_logical_id": "fixture-adv-release-001",
                "vault_uuid": "fixture-adv-release-001",
                "vault_id": "adv-release-fixture",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _pipeline(source, vault, work / "snap-work")
    create_snapshot(vault, bundle, snapshot_id="adv-release-001-fixture")
    verified = verify_bundle(bundle)
    restore_bundle(bundle, restored, tier="T3")
    ok = bool(verified.get("snapshot_id")) and (restored / "state").is_dir()
    return {
        "case_id": "recovery_snapshot_roundtrip",
        "result": "pass" if ok else "fail",
        "expected": "CREATE→VERIFY→RESTORE on disposable vault",
        "observed": (
            f"snapshot_id={verified.get('snapshot_id')}; "
            f"restored_state={(restored / 'state').is_dir()}"
        ),
    }


def _case_determinism_pipeline(work: Path) -> dict[str, Any]:
    source = work / "src-det"
    _seed_source(source)
    vault = work / "vault-det"
    create_scaffold(vault)
    manifest = work / "manifest.json"
    write_manifest(discover(source), manifest)
    ingest(manifest, vault)
    build_indexes(vault)
    validate(vault)
    first = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
        and ".atlas-stage" not in path.parts
        and ".atlas-backup" not in path.parts
    }
    ingest(manifest, vault)
    build_indexes(vault)
    validate(vault)
    second = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
        and ".atlas-stage" not in path.parts
        and ".atlas-backup" not in path.parts
    }
    stable = {
        key
        for key in first
        if key.startswith(("projects/", "state/", "generated/indexes/", "00-system/"))
    }
    drifted = sorted(key for key in stable if first.get(key) != second.get(key))
    ok = not drifted
    return {
        "case_id": "determinism_pipeline",
        "result": "pass" if ok else "fail",
        "expected": "idempotent re-ingest/indexes/validate: stable planes byte-identical",
        "observed": "drift=[]" if ok else f"drift={drifted[:8]}",
    }


def _case_perf_baseline_fixture(work: Path) -> dict[str, Any]:
    source = work / "src-perf"
    vault = work / "vault-perf"
    _seed_source(source)
    create_scaffold(vault)
    timings_ms: dict[str, int] = {}
    steps: list[tuple[str, Any]] = [
        ("discover", lambda: write_manifest(discover(source), work / "perf-manifest.json")),
        ("ingest", lambda: ingest(work / "perf-manifest.json", vault)),
        ("build_indexes", lambda: build_indexes(vault)),
        ("validate", lambda: validate(vault)),
    ]
    for name, fn in steps:
        started = time.perf_counter()
        fn()
        timings_ms[name] = int((time.perf_counter() - started) * 1000)
    # Soft band: fixture-scale steps should complete (startup-bound OK).
    ok = all(v >= 0 for v in timings_ms.values()) and sum(timings_ms.values()) < 120_000
    return {
        "case_id": "perf_baseline_fixture",
        "result": "pass" if ok else "fail",
        "expected": "fixture-scale CLI timings recorded (ms); no RELEASE claim",
        "observed": json.dumps(timings_ms, sort_keys=True),
        "detail": "PERF BASELINE ≠ RELEASE CERTIFIED; cold import dominates small fixtures",
    }


_CASE_RUNNERS = {
    "recovery_promote_noop": _case_recovery_promote_noop,
    "recovery_snapshot_roundtrip": _case_recovery_snapshot_roundtrip,
    "determinism_pipeline": _case_determinism_pipeline,
    "perf_baseline_fixture": _case_perf_baseline_fixture,
}


def build_report(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for c in cases if c["result"] == "pass")
    failed = sum(1 for c in cases if c["result"] == "fail")
    status: ReportStatus
    if failed == 0 and passed == len(cases):
        status = "certified"
    elif passed == 0:
        status = "failed"
    else:
        status = "partial"
    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.adv_release_cert.report.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "ADV-RELEASE FIXTURE CERT ≠ RELEASE CERTIFIED / PILOT PASS / WEB ACCEPTED",
        "package": PACKAGE_ID,
        "status": status,
        "release_certified": False,
        "estate_pilot_passed": False,
        "web_application_accepted": False,
        "cases": list(cases),
        "counts": {"total": len(cases), "passed": passed, "failed": failed},
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(report, REPORT_SCHEMA)
    return report


def run_fixture_adv_release_certification(
    work_root: Path,
    *,
    case_ids: Sequence[CaseId] | None = None,
    report_vault: Path | None = None,
) -> dict[str, Any]:
    """Run the ADV-RELEASE fixture matrix under ``work_root``."""
    work_root = work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    selected = tuple(case_ids) if case_ids is not None else MATRIX_CASE_IDS
    unknown = [c for c in selected if c not in _CASE_RUNNERS]
    if unknown:
        raise AdvReleaseCertError(f"unknown case_ids: {unknown}")
    cases: list[dict[str, Any]] = []
    for case_id in selected:
        try:
            cases.append(_CASE_RUNNERS[case_id](work_root / case_id))
        except Exception as exc:
            cases.append(
                {
                    "case_id": case_id,
                    "result": "fail",
                    "expected": "case completes without exception",
                    "observed": f"{type(exc).__name__}: {exc}",
                }
            )
    report = build_report(cases)
    if report_vault is not None:
        write_report(report_vault, report)
    return report


def write_report(vault: Path, report: dict[str, Any]) -> Path:
    """Persist report under ``generated/ops/`` (ops plane only)."""
    validate_record(report, REPORT_SCHEMA)
    path = vault.expanduser().resolve() / REPORT_RELATIVE
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, payload)
    return path
