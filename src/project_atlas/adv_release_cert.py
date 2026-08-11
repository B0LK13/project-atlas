"""AS-ADV-RELEASE-001 — Fixture-safe advanced release certification suite.

Combines recovery, determinism, clean-clone replay, and performance-baseline
cases on disposable vaults. AS-ADV-RELEASE-002 deepens clean-clone RC hardening;
AS-ADV-RELEASE-003 adds objective fixture-scale counters and stable-plane digest
summaries; AS-ADV-RELEASE-004 adds deterministic interrupted-promotion recovery
replay without claiming RELEASE CERTIFIED. Operational certification only — never
stamps RELEASE CERTIFIED, ESTATE PILOT PASSED, or WEB APPLICATION ACCEPTED.
"""

from __future__ import annotations

import hashlib
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

_STABLE_PREFIXES = ("projects/", "state/", "generated/indexes/", "00-system/")

CaseId = Literal[
    "recovery_promote_noop",
    "recovery_snapshot_roundtrip",
    "migration_recovery_replay",
    "determinism_pipeline",
    "clean_clone_replay",
    "perf_baseline_fixture",
    "perf_budget_smoke",
]
CaseResult = Literal["pass", "fail"]
ReportStatus = Literal["certified", "failed", "partial"]

MATRIX_CASE_IDS: tuple[CaseId, ...] = (
    "recovery_promote_noop",
    "recovery_snapshot_roundtrip",
    "migration_recovery_replay",
    "determinism_pipeline",
    "clean_clone_replay",
    "perf_baseline_fixture",
    "perf_budget_smoke",
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
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)


def _vault_file_bytes(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
        and ".atlas-stage" not in path.parts
        and ".atlas-backup" not in path.parts
    }


def _stable_plane(files: dict[str, bytes]) -> dict[str, bytes]:
    return {
        key: value
        for key, value in files.items()
        if key.startswith(_STABLE_PREFIXES)
    }


def _stable_drift(left: dict[str, bytes], right: dict[str, bytes]) -> list[str]:
    keys = set(left) | set(right)
    return sorted(key for key in keys if left.get(key) != right.get(key))


def _stable_plane_summary(files: dict[str, bytes]) -> dict[str, Any]:
    """Return deterministic size signals and a framed stable-plane digest."""
    digest = hashlib.sha256()
    byte_count = 0
    for key in sorted(files):
        key_bytes = key.encode("utf-8")
        content = files[key]
        digest.update(len(key_bytes).to_bytes(8, "big"))
        digest.update(key_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        byte_count += len(content)
    return {
        "file_count": len(files),
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
    }


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


def _case_migration_recovery_replay(work: Path) -> dict[str, Any]:
    """Recover a deterministic stage-only interruption, then replay the pipeline."""
    source = work / "src-recovery"
    vault = work / "vault-recovery"
    manifest = work / "manifest.json"
    _seed_source(source)
    create_scaffold(vault)
    write_manifest(discover(source), manifest)
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)

    baseline = _stable_plane(_vault_file_bytes(vault))
    canonical_files = sorted((vault / "projects").rglob("*.md"))
    if not canonical_files:
        raise AdvReleaseCertError("recovery fixture produced no canonical project note")
    canonical = canonical_files[0]
    canonical_before = canonical.read_bytes()
    transaction_id = "4" * 32
    stage = canonical.parent / (
        f".{canonical.name}.{transaction_id}.atlas-stage"
    )
    stage.write_bytes(b"interrupted-promotion-fixture\n")

    recovery = recover_promote_orphans(vault)
    validate(vault)
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)
    replayed = _stable_plane(_vault_file_bytes(vault))
    second_recovery = recover_promote_orphans(vault)

    drifted = _stable_drift(baseline, replayed)
    baseline_summary = _stable_plane_summary(baseline)
    replayed_summary = _stable_plane_summary(replayed)
    ok = (
        recovery.orphan_count == 1
        and recovery.transactions_recovered == 1
        and recovery.receipt_path is not None
        and not stage.exists()
        and canonical.read_bytes() == canonical_before
        and second_recovery.orphan_count == 0
        and second_recovery.transactions_recovered == 0
        and not drifted
        and baseline_summary == replayed_summary
        and bool(baseline)
    )
    observed = {
        "baseline": baseline_summary,
        "canonical_preserved": canonical.read_bytes() == canonical_before,
        "drift": drifted[:8],
        "orphan_count": recovery.orphan_count,
        "replayed": replayed_summary,
        "second_orphan_count": second_recovery.orphan_count,
        "stage_removed": not stage.exists(),
        "transactions_recovered": recovery.transactions_recovered,
    }
    return {
        "case_id": "migration_recovery_replay",
        "result": "pass" if ok else "fail",
        "expected": (
            "stage-only interrupted promotion recovers cleanly; pipeline replay "
            "restores byte-identical stable planes"
        ),
        "observed": json.dumps(observed, sort_keys=True),
        "detail": (
            "AS-ADV-RELEASE-004 migration/recovery RC evidence only; "
            "RELEASE CERTIFIED remains false"
        ),
    }


def _case_determinism_pipeline(work: Path) -> dict[str, Any]:
    source = work / "src-det"
    _seed_source(source)
    vault = work / "vault-det"
    create_scaffold(vault)
    manifest = work / "manifest.json"
    write_manifest(discover(source), manifest)
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)
    first = _stable_plane(_vault_file_bytes(vault))
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)
    second = _stable_plane(_vault_file_bytes(vault))
    drifted = _stable_drift(first, second)
    first_summary = _stable_plane_summary(first)
    second_summary = _stable_plane_summary(second)
    ok = not drifted and first_summary == second_summary and bool(first)
    observed = {
        "first": first_summary,
        "second": second_summary,
        "drift": drifted[:8],
    }
    return {
        "case_id": "determinism_pipeline",
        "result": "pass" if ok else "fail",
        "expected": (
            "idempotent re-ingest/indexes/validate: stable planes byte-identical "
            "with equal digest summaries"
        ),
        "observed": json.dumps(observed, sort_keys=True),
    }


def _case_clean_clone_replay(work: Path) -> dict[str, Any]:
    """Two sequential pipelines on disposable vaults with one shared manifest.

    AS-ADV-RELEASE-002 RC hardening: clean-clone replay must match E2E-style
    stable-plane equality without claiming RELEASE CERTIFIED.
    """
    source = work / "src-clone"
    _seed_source(source)
    manifest = work / "shared-manifest.json"
    write_manifest(discover(source), manifest)

    vault_a = work / "vault-a"
    vault_b = work / "vault-b"
    create_scaffold(vault_a)
    create_scaffold(vault_b)

    ingest(manifest, vault_a, authorized_source_root=source)
    build_indexes(vault_a)
    validate(vault_a)

    ingest(manifest, vault_b, authorized_source_root=source)
    build_indexes(vault_b)
    validate(vault_b)

    plane_a = _stable_plane(_vault_file_bytes(vault_a))
    plane_b = _stable_plane(_vault_file_bytes(vault_b))
    drifted = _stable_drift(plane_a, plane_b)
    ok = not drifted and bool(plane_a)
    return {
        "case_id": "clean_clone_replay",
        "result": "pass" if ok else "fail",
        "expected": (
            "two disposable vaults + identical manifest → stable planes byte-identical"
        ),
        "observed": (
            f"keys={len(plane_a)}; drift=[]"
            if ok
            else f"keys_a={len(plane_a)} keys_b={len(plane_b)} drift={drifted[:8]}"
        ),
        "detail": (
            "AS-ADV-RELEASE-002 clean-clone prep; RC hardening only; "
            "RELEASE CERTIFIED remains false"
        ),
    }


def _case_perf_baseline_fixture(work: Path) -> dict[str, Any]:
    source = work / "src-perf"
    vault = work / "vault-perf"
    _seed_source(source)
    create_scaffold(vault)
    timings_ms: dict[str, int] = {}
    steps: list[tuple[str, Any]] = [
        ("discover", lambda: write_manifest(discover(source), work / "perf-manifest.json")),
        ("ingest", lambda: ingest(
            work / "perf-manifest.json",
            vault,
            authorized_source_root=source,
        )),
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


def _case_perf_budget_smoke(work: Path) -> dict[str, Any]:
    """Bound fixture scale with deterministic counters, never wall-clock."""
    source = work / "src-perf-budget"
    vault = work / "vault-perf-budget"
    manifest = work / "perf-budget-manifest.json"
    _seed_source(source)
    source_files = sorted(path for path in source.rglob("*") if path.is_file())
    source_bytes = sum(path.stat().st_size for path in source_files)
    create_scaffold(vault)
    write_manifest(discover(source), manifest)
    ingest(manifest, vault, authorized_source_root=source)
    build_indexes(vault)
    validate(vault)
    stable_summary = _stable_plane_summary(_stable_plane(_vault_file_bytes(vault)))
    signals = {
        "operation_count": 4,
        "source_file_count": len(source_files),
        "source_byte_count": source_bytes,
        "stable_file_count": stable_summary["file_count"],
        "stable_byte_count": stable_summary["byte_count"],
    }
    budgets = {
        "operation_count_max": 4,
        "source_file_count_max": 4,
        "source_byte_count_max": 4_096,
        "stable_file_count_max": 128,
        "stable_byte_count_max": 1_048_576,
    }
    ok = (
        signals["operation_count"] <= budgets["operation_count_max"]
        and signals["source_file_count"] <= budgets["source_file_count_max"]
        and signals["source_byte_count"] <= budgets["source_byte_count_max"]
        and 0 < signals["stable_file_count"] <= budgets["stable_file_count_max"]
        and 0 < signals["stable_byte_count"] <= budgets["stable_byte_count_max"]
    )
    return {
        "case_id": "perf_budget_smoke",
        "result": "pass" if ok else "fail",
        "expected": "fixture stays within deterministic file/byte/operation budgets",
        "observed": json.dumps(
            {"budgets": budgets, "signals": signals}, sort_keys=True
        ),
        "detail": (
            "AS-ADV-RELEASE-003 objective fixture-scale smoke; no wall-clock "
            "gate; RELEASE CERTIFIED remains false"
        ),
    }


_CASE_RUNNERS = {
    "recovery_promote_noop": _case_recovery_promote_noop,
    "recovery_snapshot_roundtrip": _case_recovery_snapshot_roundtrip,
    "migration_recovery_replay": _case_migration_recovery_replay,
    "determinism_pipeline": _case_determinism_pipeline,
    "clean_clone_replay": _case_clean_clone_replay,
    "perf_baseline_fixture": _case_perf_baseline_fixture,
    "perf_budget_smoke": _case_perf_budget_smoke,
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
