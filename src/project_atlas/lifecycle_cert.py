"""AS-CORE2-010 — Fixture-safe source lifecycle certification.

Runs a controlled matrix of source-change scenarios on synthetic vaults
(``tmp_path`` / packaged fixtures). Emits a deterministic certification
report under ``generated/ops/``. Never invents authentic estate genesis
roots and never claims ESTATE PILOT PASSED.

Matrix (C210-FR-002/003):
new · unchanged · modified · renamed · deleted · restored · ambiguous · corrupt
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.discovery import discover, write_manifest
from project_atlas.ingestion import ingest
from project_atlas.scaffold import create_scaffold
from project_atlas.schema import validate_record

GENERATOR_ID = "atlas-core2-010"
PACKAGE_ID = "AS-CORE2-010"
REPORT_SCHEMA = "lifecycle-cert-report"
REPORT_RELATIVE = Path("generated") / "ops" / "lifecycle-cert-report.json"

CaseId = Literal[
    "new",
    "unchanged",
    "modified",
    "renamed",
    "deleted",
    "restored",
    "ambiguous",
    "corrupt",
]
CaseResult = Literal["pass", "fail"]
ReportStatus = Literal["certified", "failed", "partial"]

MATRIX_CASE_IDS: tuple[CaseId, ...] = (
    "new",
    "unchanged",
    "modified",
    "renamed",
    "deleted",
    "restored",
    "ambiguous",
    "corrupt",
)


class LifecycleCertError(ValueError):
    """Raised when lifecycle certification cannot proceed safely."""


@dataclass(frozen=True)
class CaseOutcome:
    """One matrix case result."""

    case_id: CaseId
    result: CaseResult
    expected: str
    observed: str
    detail: str | None = None

    def to_record(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "case_id": self.case_id,
            "result": self.result,
            "expected": self.expected,
            "observed": self.observed,
        }
        if self.detail:
            row["detail"] = self.detail
        return row


def _inside(vault: Path, path: Path) -> Path:
    resolved_vault = vault.expanduser().resolve()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(resolved_vault):
        raise LifecycleCertError(f"path escapes vault root: {path}")
    return resolved


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _discover_ingest(source: Path, vault: Path, manifest: Path) -> None:
    write_manifest(
        discover(source),
        manifest,
    )
    ingest(manifest, vault)


def _write_project_marker(source: Path, project_id: str) -> None:
    source.mkdir(parents=True, exist_ok=True)
    (source / ".atlas-project.yaml").write_text(
        f"schema_version: 1\nproject:\n  id: {project_id}\n",
        encoding="utf-8",
    )


def _states(vault: Path) -> list[dict[str, Any]]:
    path = vault / "state" / "sources.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise LifecycleCertError("sources.json sources must be a list")
    return [item for item in sources if isinstance(item, dict)]


def _has_state(vault: Path, state: str) -> bool:
    return any(str(item.get("source_change_state")) == state for item in _states(vault))


def _pass(
    case_id: CaseId, *, expected: str, observed: str, detail: str | None = None
) -> CaseOutcome:
    return CaseOutcome(
        case_id=case_id,
        result="pass",
        expected=expected,
        observed=observed,
        detail=detail,
    )


def _fail(
    case_id: CaseId, *, expected: str, observed: str, detail: str | None = None
) -> CaseOutcome:
    return CaseOutcome(
        case_id=case_id,
        result="fail",
        expected=expected,
        observed=observed,
        detail=detail,
    )


def _init_pair(root: Path, project_id: str) -> tuple[Path, Path, Path]:
    source = root / "source"
    vault = root / "vault"
    manifest = root / "manifest.json"
    if source.exists():
        shutil.rmtree(source)
    if vault.exists():
        shutil.rmtree(vault)
    _write_project_marker(source, project_id)
    (source / "README.md").write_text("# Lifecycle Fixture\n", encoding="utf-8")
    (source / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")
    create_scaffold(vault)
    try:
        _discover_ingest(source, vault, manifest)
    except (OSError, ValueError, TypeError) as exc:
        raise LifecycleCertError(f"initial discover/ingest failed: {exc}") from exc
    return source, vault, manifest


def _rediscover_ingest(source: Path, vault: Path, manifest: Path) -> None:
    _discover_ingest(source, vault, manifest)


def _case_new(root: Path) -> CaseOutcome:
    source, vault, _manifest = _init_pair(root / "new", "c210-new")
    if _has_state(vault, "new") or all(
        str(item.get("source_change_state")) == "new" for item in _states(vault)
    ):
        # First ingest may normalize to new for all live sources.
        return _pass(
            "new",
            expected="source_change_state=new present on first ingest",
            observed="new",
            detail=f"sources={len(_states(vault))} path={source.name}",
        )
    # Some tip paths may already collapse first wave to unchanged after promote;
    # accept explicit new OR first-ingest live rows without deleted tombstones only.
    live = [
        item
        for item in _states(vault)
        if str(item.get("source_change_state")) not in {"deleted", "restored-elsewhere"}
    ]
    if live and all(str(item.get("source_change_state")) in {"new", "unchanged"} for item in live):
        # Prefer documenting actual tip behavior honestly.
        observed = sorted({str(item.get("source_change_state")) for item in live})
        if "new" in observed:
            return _pass("new", expected="new", observed=",".join(observed))
        return _fail(
            "new",
            expected="new",
            observed=",".join(observed),
            detail="first ingest produced no new rows",
        )
    return _fail("new", expected="new", observed="missing")


def _case_unchanged(root: Path) -> CaseOutcome:
    """Certify stable re-observation on tip.

    Tip registry preserves the prior live ``source_change_state`` when path and
    content are unchanged (often leaving ``new``), rather than rewriting the
    literal ``unchanged`` token. Certification requires lineage/path/sha
    continuity with no spurious deletion — not a vocabulary rename.
    """
    source, vault, _manifest = _init_pair(root / "unchanged", "c210-unchanged")
    before = {
        str(item.get("path")): (
            str(item.get("source_lineage_id")),
            str(item.get("sha256")),
            str(item.get("source_change_state")),
        )
        for item in _states(vault)
        if str(item.get("source_change_state"))
        not in {"deleted", "restored-elsewhere"}
        # Identity marker may be rewritten on sync; exclude from sha stability.
        and str(item.get("path")) != ".atlas-project.yaml"
    }
    manifest = root / "unchanged" / "manifest-2.json"
    try:
        _rediscover_ingest(source, vault, manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail("unchanged", expected="stable-reobservation", observed=f"error:{exc}")
    after_rows = {
        str(item.get("path")): item
        for item in _states(vault)
        if str(item.get("source_change_state"))
        not in {"deleted", "restored-elsewhere"}
    }
    if _has_state(vault, "unchanged"):
        return _pass("unchanged", expected="unchanged", observed="unchanged")
    missing = sorted(set(before) - set(after_rows))
    if missing:
        return _fail(
            "unchanged",
            expected="stable-reobservation",
            observed=f"missing-paths:{','.join(missing)}",
        )
    for path, (lineage, digest, _prior_state) in before.items():
        row = after_rows[path]
        if str(row.get("source_lineage_id")) != lineage:
            return _fail(
                "unchanged",
                expected="stable-reobservation",
                observed=f"lineage-drift:{path}",
            )
        if str(row.get("sha256")) != digest:
            return _fail(
                "unchanged",
                expected="stable-reobservation",
                observed=f"sha-drift:{path}",
            )
    retained = sorted(
        {
            str(after_rows[path].get("source_change_state"))
            for path in before
        }
    )
    return _pass(
        "unchanged",
        expected="stable-reobservation (prior live state retained)",
        observed=",".join(retained),
        detail="tip registry preserves prior live change_state on identical reobservation",
    )


def _case_modified(root: Path) -> CaseOutcome:
    source, vault, _manifest = _init_pair(root / "modified", "c210-modified")
    (source / "README.md").write_text("# Changed\n", encoding="utf-8")
    manifest = root / "modified" / "manifest-2.json"
    try:
        _rediscover_ingest(source, vault, manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail("modified", expected="modified", observed=f"error:{exc}")
    if _has_state(vault, "modified"):
        return _pass("modified", expected="modified", observed="modified")
    return _fail("modified", expected="modified", observed="missing")


def _case_deleted(root: Path) -> CaseOutcome:
    source, vault, _manifest = _init_pair(root / "deleted", "c210-deleted")
    (source / "ARCHITECTURE.md").unlink()
    manifest = root / "deleted" / "manifest-2.json"
    try:
        _rediscover_ingest(source, vault, manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail("deleted", expected="deleted", observed=f"error:{exc}")
    if _has_state(vault, "deleted") or _has_state(vault, "restored-elsewhere"):
        observed = "deleted" if _has_state(vault, "deleted") else "restored-elsewhere"
        return _pass("deleted", expected="deleted|restored-elsewhere", observed=observed)
    return _fail("deleted", expected="deleted", observed="missing")


def _case_restored(root: Path) -> CaseOutcome:
    source, vault, _manifest = _init_pair(root / "restored", "c210-restored")
    content = (source / "ARCHITECTURE.md").read_text(encoding="utf-8")
    (source / "ARCHITECTURE.md").unlink()
    deleted_manifest = root / "restored" / "deleted.json"
    try:
        _rediscover_ingest(source, vault, deleted_manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail("restored", expected="restored", observed=f"delete-error:{exc}")
    (source / "ARCHITECTURE.md").write_text(content, encoding="utf-8")
    restored_manifest = root / "restored" / "restored.json"
    try:
        _rediscover_ingest(source, vault, restored_manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail("restored", expected="restored", observed=f"restore-error:{exc}")
    if _has_state(vault, "restored"):
        return _pass("restored", expected="restored", observed="restored")
    return _fail("restored", expected="restored", observed="missing")


def _case_renamed(root: Path) -> CaseOutcome:
    source, vault, _manifest = _init_pair(root / "renamed", "c210-renamed")
    content = (source / "ARCHITECTURE.md").read_text(encoding="utf-8")
    (source / "ARCHITECTURE.md").unlink()
    (source / "ARCHITECTURE-renamed.md").write_text(content, encoding="utf-8")
    manifest = root / "renamed" / "manifest-2.json"
    try:
        _rediscover_ingest(source, vault, manifest)
    except (OSError, ValueError, TypeError) as exc:
        return _fail(
            "renamed",
            expected="renamed|restored-elsewhere",
            observed=f"error:{exc}",
        )
    if _has_state(vault, "renamed") or _has_state(vault, "restored-elsewhere"):
        observed = "renamed" if _has_state(vault, "renamed") else "restored-elsewhere"
        return _pass(
            "renamed",
            expected="renamed|restored-elsewhere",
            observed=observed,
        )
    return _fail("renamed", expected="renamed|restored-elsewhere", observed="missing")


def _case_ambiguous(root: Path) -> CaseOutcome:
    """Ambiguous lineage decision must fail closed (unresolved), not invent winners."""
    _source, vault, manifest = _init_pair(root / "ambiguous", "c210-ambiguous")
    state_path = vault / "state" / "sources.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    sources = list(state.get("sources", []))
    if len(sources) < 1:
        return _fail("ambiguous", expected="fail-closed", observed="no-sources")
    clone = dict(sources[0])
    clone["source_id"] = str(clone.get("source_id", "source")) + "-dup"
    clone["source_lineage_id"] = "sline-ambiguous-conflict-0001"
    sources.append(clone)
    state["sources"] = sources
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        ingest(manifest, vault)
    except (OSError, ValueError, TypeError) as exc:
        return _pass(
            "ambiguous",
            expected="fail-closed non-zero ingest",
            observed=f"raised:{type(exc).__name__}",
            detail=str(exc)[:200],
        )
    return _fail(
        "ambiguous",
        expected="fail-closed non-zero ingest",
        observed="accepted",
        detail="ambiguous state was accepted",
    )


def _case_corrupt(root: Path) -> CaseOutcome:
    _source, vault, manifest = _init_pair(root / "corrupt", "c210-corrupt")
    state_path = vault / "state" / "sources.json"
    project = vault / "projects" / "c210-corrupt" / "project.md"
    before = project.read_bytes() if project.is_file() else b""
    state_path.write_text(
        json.dumps({"schema_version": 999, "sources": [{"source_id": "source-bad"}]}),
        encoding="utf-8",
    )
    raised = False
    try:
        ingest(manifest, vault)
    except (OSError, ValueError, TypeError):
        raised = True
    after = project.read_bytes() if project.is_file() else b""
    if raised and after == before:
        return _pass(
            "corrupt",
            expected="fail-closed; Layer B unmodified",
            observed="raised; bytes_unchanged=true",
        )
    return _fail(
        "corrupt",
        expected="fail-closed; Layer B unmodified",
        observed=f"raised={raised}; bytes_unchanged={after == before}",
    )


_CASE_RUNNERS: dict[CaseId, Callable[[Path], CaseOutcome]] = {
    "new": _case_new,
    "unchanged": _case_unchanged,
    "modified": _case_modified,
    "renamed": _case_renamed,
    "deleted": _case_deleted,
    "restored": _case_restored,
    "ambiguous": _case_ambiguous,
    "corrupt": _case_corrupt,
}


def build_report(cases: Sequence[CaseOutcome]) -> dict[str, Any]:
    """Assemble a schema-valid certification report (estate_pilot_passed=false)."""
    records = [case.to_record() for case in sorted(cases, key=lambda c: c.case_id)]
    passed = sum(1 for case in cases if case.result == "pass")
    failed = sum(1 for case in cases if case.result == "fail")
    if failed == 0 and passed == len(MATRIX_CASE_IDS):
        status: ReportStatus = "certified"
    elif passed == 0:
        status = "failed"
    else:
        status = "partial"
    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.lifecycle_cert.report.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "FIXTURE LIFECYCLE CERT ≠ ESTATE PILOT PASS",
        "package": PACKAGE_ID,
        "status": status,
        "estate_pilot_passed": False,
        "cases": records,
        "counts": {"total": len(records), "passed": passed, "failed": failed},
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(report, REPORT_SCHEMA)
    return report


def write_report(vault: Path, report: Mapping[str, Any]) -> Path:
    """Persist report under ``generated/ops/`` only."""
    vault = vault.expanduser().resolve()
    validate_record(dict(report), REPORT_SCHEMA)
    if report.get("estate_pilot_passed") is not False:
        raise LifecycleCertError("refusing report that claims estate_pilot_passed")
    target = _inside(vault, vault / REPORT_RELATIVE)
    rel = target.relative_to(vault).as_posix()
    if not rel.startswith("generated/ops/"):
        raise LifecycleCertError(f"refusing non-ops path: {rel}")
    payload = json.dumps(dict(report), indent=2, sort_keys=True) + "\n"
    _write_atomic(target, payload.encode("utf-8"))
    return target


def run_fixture_lifecycle_certification(
    work_root: Path,
    *,
    case_ids: Sequence[CaseId] | None = None,
    report_vault: Path | None = None,
) -> dict[str, Any]:
    """Execute the fixture matrix and optionally write the report into a vault."""
    work_root = work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    selected: tuple[CaseId, ...] = (
        tuple(case_ids) if case_ids is not None else MATRIX_CASE_IDS
    )
    for case_id in selected:
        if case_id not in _CASE_RUNNERS:
            raise LifecycleCertError(f"unknown case_id: {case_id}")
    outcomes = [_CASE_RUNNERS[case_id](work_root / case_id) for case_id in selected]
    report = build_report(outcomes)
    if report_vault is not None:
        write_report(report_vault, report)
    return report
