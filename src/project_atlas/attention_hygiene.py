"""AS-CODER-ALPHA-ATTENTION-001 — deterministic attention hygiene (D-040).

Classifies unresolved Truth work into actionable buckets without confidence
theatre. Read-only over vault artifacts; never invents winners.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID = "AS-CODER-ALPHA-ATTENTION-001"
GENERATOR_ID = "atlas-coder-alpha-attention-001"
LEVELS = (
    "BLOCKING",
    "ACTION_REQUIRED",
    "NEEDS_HUMAN_REVIEW",
    "SOURCE_FAILURE",
    "CONFLICT",
    "STALE",
    "SUPERSEDED",
    "DUPLICATE",
    "INCOMPLETE",
    "UNKNOWN",
    "INFORMATIONAL",
    "LOW_VALUE_NOISE",
)
# Rollup precedence (lowest index wins). CLEAR is never inferred from absence.
_ROLLUP_ORDER = (
    "BLOCKING",
    "ACTION_REQUIRED",
    "NEEDS_HUMAN_REVIEW",
    "SOURCE_FAILURE",
    "CONFLICT",
    "STALE",
    "SUPERSEDED",
    "DUPLICATE",
    "INCOMPLETE",
    "UNKNOWN",
    "INFORMATIONAL",
    "LOW_VALUE_NOISE",
    "CLEAR",
)


class AttentionHygieneError(ValueError):
    """Fail-closed attention hygiene error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise AttentionHygieneError(str(exc)) from exc


def _read_json(path: Path) -> tuple[str, dict[str, Any] | None]:
    """Return ``(status, payload)`` where status is absent|ok|unreadable."""
    if not path.is_file():
        return "absent", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreadable", None
    if not isinstance(raw, dict):
        return "unreadable", None
    return "ok", raw


def _read_json_any(path: Path) -> tuple[str, dict[str, Any] | list[Any] | None]:
    """Like ``_read_json`` but accepts top-level object or array (secret-findings)."""
    if not path.is_file():
        return "absent", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreadable", None
    if isinstance(raw, (dict, list)):
        return "ok", raw
    return "unreadable", None


def _item(
    *,
    level: str,
    kind: str,
    reason_code: str,
    why: str,
    impact: str,
    action: str,
    evidence: list[str],
    subject_id: str | None = None,
) -> dict[str, Any]:
    return {
        "level": level,
        "kind": kind,
        "reason_code": reason_code,
        "why_seeing_this": why,
        "why_it_matters": impact,
        "what_to_do": action,
        "evidence": evidence,
        "subject_id": subject_id,
        "confidence_theatre": False,
    }


def _pending_level(category: str) -> str:
    cat_l = category.lower()
    if "stale" in cat_l:
        return "STALE"
    if "superseded" in cat_l:
        return "SUPERSEDED"
    if any(
        token in cat_l
        for token in (
            "authority",
            "competing",
            "action-required",
            "blocking",
            "disposition",
        )
    ):
        return "ACTION_REQUIRED"
    return "NEEDS_HUMAN_REVIEW"


def classify_attention(vault: Path, project_id: str) -> dict[str, Any]:
    """Classify unresolved attention for one project (read-only)."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise AttentionHygieneError(f"vault is not a directory: {vault}")
    project_id = _safe_project_id(project_id)
    inspected: list[str] = []
    items: list[dict[str, Any]] = []

    conflicts_path = vault / "review" / "conflicts" / f"{project_id}.json"
    inspected.append(conflicts_path.relative_to(vault).as_posix())
    conflicts_status, conflicts = _read_json(conflicts_path)
    if conflicts_status == "unreadable":
        items.append(
            _item(
                level="INFORMATIONAL",
                kind="artifact_unreadable",
                reason_code="ARTIFACT_UNREADABLE",
                why="review/conflicts artifact exists but could not be parsed",
                impact="Attention may be incomplete; do not treat as CLEAR",
                action="Repair JSON or re-run atlas connect / compile",
                evidence=[conflicts_path.relative_to(vault).as_posix()],
            )
        )
    for entry in (conflicts or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        ctype = str(entry.get("conflict_type") or "unknown")
        level = "DUPLICATE" if ctype == "duplicate-source" else "BLOCKING"
        items.append(
            _item(
                level=level,
                kind="conflict",
                reason_code=ctype,
                why="Unresolved competing claims recorded in review/conflicts",
                impact="Canonical field cannot be trusted until disposition",
                action="Inspect competing claims and run atlas review decide",
                evidence=[conflicts_path.relative_to(vault).as_posix()],
                subject_id=str(entry.get("conflict_id") or entry.get("field") or ""),
            )
        )

    pending_path = vault / "review" / "pending" / f"{project_id}.json"
    inspected.append(pending_path.relative_to(vault).as_posix())
    pending_status, pending = _read_json(pending_path)
    if pending_status == "unreadable":
        items.append(
            _item(
                level="INFORMATIONAL",
                kind="artifact_unreadable",
                reason_code="ARTIFACT_UNREADABLE",
                why="review/pending artifact exists but could not be parsed",
                impact="Attention may be incomplete; do not treat as CLEAR",
                action="Repair JSON or re-run atlas connect / compile",
                evidence=[pending_path.relative_to(vault).as_posix()],
            )
        )
    pending_count = 0
    for entry in (pending or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "pending")
        if status not in {"pending", "in-review", ""}:
            continue
        pending_count += 1
        category = str(entry.get("category") or entry.get("reason") or "pending-claim")
        items.append(
            _item(
                level=_pending_level(category),
                kind="pending_review",
                reason_code=category,
                why=str(entry.get("reason") or "Claim requires human verification"),
                impact="Pending review blocks verified claim promotion",
                action="Inspect evidence then atlas review decide accept|reject",
                evidence=[pending_path.relative_to(vault).as_posix()],
                subject_id=str(entry.get("review_id") or ""),
            )
        )

    outcomes_path = vault / "state" / "compilation-outcomes" / f"{project_id}.json"
    inspected.append(outcomes_path.relative_to(vault).as_posix())
    outcomes_status, outcomes = _read_json(outcomes_path)
    if outcomes_status == "unreadable":
        items.append(
            _item(
                level="INFORMATIONAL",
                kind="artifact_unreadable",
                reason_code="ARTIFACT_UNREADABLE",
                why="compilation-outcomes artifact exists but could not be parsed",
                impact="Source-failure attention may be incomplete",
                action="Repair JSON or re-run knowledge compile",
                evidence=[outcomes_path.relative_to(vault).as_posix()],
            )
        )
    for candidate in (outcomes or {}).get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        outcome = str(candidate.get("outcome") or "")
        if outcome.upper() not in {"FAILED", "PROMOTION_FAILED"}:
            continue
        level = "ACTION_REQUIRED" if outcome.upper() == "PROMOTION_FAILED" else "SOURCE_FAILURE"
        subject = str(
            candidate.get("source_path")
            or candidate.get("source_id")
            or candidate.get("candidate_id")
            or ""
        )
        items.append(
            _item(
                level=level,
                kind="compile_failure",
                reason_code=outcome,
                why="Source candidate failed during knowledge compile",
                impact="Claims from this source are unavailable or withheld",
                action="Open diagnostics and repair or replace the source",
                evidence=[outcomes_path.relative_to(vault).as_posix()],
                subject_id=subject,
            )
        )

    # Real PROMOTION_FAILED is recorded in quarantine after canonical rollback
    # (ingestion._quarantine_promotion_failure) — not left in compilation-outcomes.
    promo_path = vault / "quarantine" / "promotion-failures" / "index.json"
    inspected.append(promo_path.relative_to(vault).as_posix())
    promo_status, promo = _read_json(promo_path)
    if promo_status == "unreadable":
        items.append(
            _item(
                level="INFORMATIONAL",
                kind="artifact_unreadable",
                reason_code="ARTIFACT_UNREADABLE",
                why="promotion-failures quarantine exists but could not be parsed",
                impact="Promotion-failure attention may be incomplete",
                action="Inspect quarantine/promotion-failures/index.json",
                evidence=[promo_path.relative_to(vault).as_posix()],
            )
        )
    elif promo_status == "ok" and isinstance(promo, dict):
        for project_row in promo.get("projects") or []:
            if not isinstance(project_row, dict):
                continue
            if str(project_row.get("project_id") or "") != project_id:
                continue
            for candidate in project_row.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                outcome = str(candidate.get("outcome") or "")
                if outcome.upper() != "PROMOTION_FAILED":
                    continue
                items.append(
                    _item(
                        level="ACTION_REQUIRED",
                        kind="promotion_failure",
                        reason_code="PROMOTION_FAILED",
                        why="Canonical promotion failed and rolled back",
                        impact="Truth Core not updated for this project's candidates",
                        action="Resolve promotion fault and re-run atlas connect/ingest",
                        evidence=[promo_path.relative_to(vault).as_posix()],
                        subject_id=str(candidate.get("source_path") or ""),
                    )
                )

    # SECRET_QUARANTINE must never disappear into a false CLEAR (D-041/D-044).
    # Scoped attention must not import other projects' quarantine rows (D-047 IV /
    # CROSS_PROJECT_LEAK) — reuse source-health ownership indexes.
    from project_atlas.source_health import (
        _finding_matches_project,
        _manifest_project_indexes,
    )

    secrets_path = vault / "generated" / "reports" / "secret-findings.json"
    inspected.append(secrets_path.relative_to(vault).as_posix())
    secrets_status, secrets_payload = _read_json_any(secrets_path)
    if secrets_status == "unreadable":
        items.append(
            _item(
                level="INCOMPLETE",
                kind="artifact_unreadable",
                reason_code="ARTIFACT_UNREADABLE",
                why="secret-findings artifact exists but could not be parsed",
                impact="Quarantine attention may be incomplete; not CLEAR",
                action="Repair secret-findings JSON (metadata only; never echo secrets)",
                evidence=[secrets_path.relative_to(vault).as_posix()],
            )
        )
    elif secrets_status == "ok":
        if isinstance(secrets_payload, list):
            secret_rows = [row for row in secrets_payload if isinstance(row, dict)]
        elif isinstance(secrets_payload, dict):
            raw_findings = secrets_payload.get("findings")
            secret_rows = (
                [row for row in raw_findings if isinstance(row, dict)]
                if isinstance(raw_findings, list)
                else []
            )
        else:
            secret_rows = []
        # Prefer durable vault source-manifest (multi-project) over last-writer
        # connect-manifest so sibling reconnects cannot erase another project's
        # quarantine ownership (D-050 IV / shared-vault false CLEAR).
        durable_path = vault / "sources" / "manifests" / "source-manifest.json"
        connect_path = vault / "generated" / "ops" / "connect-manifest.json"
        inspected.append(durable_path.relative_to(vault).as_posix())
        inspected.append(connect_path.relative_to(vault).as_posix())
        durable_status, durable_payload = _read_json(durable_path)
        connect_status, connect_payload = _read_json(connect_path)
        ownership_payload = (
            durable_payload
            if durable_status == "ok" and isinstance(durable_payload, dict)
            else connect_payload if connect_status == "ok" else None
        )
        source_projects, path_projects = _manifest_project_indexes(ownership_payload)
        scoped_rows = [
            row
            for row in secret_rows
            if _finding_matches_project(
                row,
                project_id=project_id,
                source_projects=source_projects,
                path_projects=path_projects,
            )
        ]
        if secret_rows and not source_projects and not path_projects:
            # Findings exist but ownership cannot be scoped — never false CLEAR.
            items.append(
                _item(
                    level="INCOMPLETE",
                    kind="secret_quarantine_unscoped",
                    reason_code="SECRET_OWNERSHIP_UNKNOWN",
                    why=(
                        f"{len(secret_rows)} secret-quarantine finding(s) present "
                        "but ownership indexes are unavailable"
                    ),
                    impact="Cannot attribute quarantine to this project; not CLEAR",
                    action="Re-run atlas connect to restore source-manifest ownership",
                    evidence=[secrets_path.relative_to(vault).as_posix()],
                )
            )
        elif scoped_rows:
            items.append(
                _item(
                    level="ACTION_REQUIRED",
                    kind="secret_quarantine",
                    reason_code="SECRET_QUARANTINE",
                    why=f"{len(scoped_rows)} secret-quarantine finding(s) recorded",
                    impact="Credential-bearing sources must be repaired before trust",
                    action="Remove/redact credentials and re-run atlas connect",
                    evidence=[secrets_path.relative_to(vault).as_posix()],
                )
            )

    # Cap low-value noise: collapse huge pending queues into summary item.
    # Preserve ACTION_REQUIRED / STALE / SUPERSEDED classifications — never
    # demote competing-authority rows to NEEDS_HUMAN_REVIEW on rollup.
    if pending_count > 20:
        pending_items = [item for item in items if item["kind"] == "pending_review"]
        items = [item for item in items if item["kind"] != "pending_review"]
        items.append(
            _item(
                level="LOW_VALUE_NOISE",
                kind="pending_review_rollup",
                reason_code="pending-queue-volume",
                why=f"{pending_count} pending reviews — volume exceeds actionable default",
                impact="Individual pending rows are noisy; triage needed",
                action="Filter by category or resolve conflicts first",
                evidence=[pending_path.relative_to(vault).as_posix()],
            )
        )
        priority = {
            "ACTION_REQUIRED": 0,
            "STALE": 1,
            "SUPERSEDED": 2,
            "NEEDS_HUMAN_REVIEW": 3,
        }
        pending_items.sort(
            key=lambda row: (
                priority.get(str(row["level"]), 9),
                str(row.get("subject_id") or ""),
            )
        )
        for item in pending_items[:5]:
            item["why_it_matters"] = "Sample pending item requiring disposition"
            items.append(item)

    # Collapse repetitive SOURCE_FAILURE noise while preserving exact counts
    # and inspectability (D-043). Failures are not hidden.
    source_failures = [item for item in items if item.get("level") == "SOURCE_FAILURE"]
    if len(source_failures) > 5:
        items = [item for item in items if item.get("level") != "SOURCE_FAILURE"]
        sample_subjects = [
            str(item.get("subject_id") or "")
            for item in source_failures[:5]
            if item.get("subject_id")
        ]
        items.append(
            _item(
                level="SOURCE_FAILURE",
                kind="compile_failure_rollup",
                reason_code="source-failure-volume",
                why=(
                    f"{len(source_failures)} source compile failures "
                    "(collapsed for triage; exact count preserved)"
                ),
                impact="Many sources unavailable; claims may be incomplete",
                action=(
                    "Run atlas source-health --project "
                    f"{project_id} to inspect reason codes; "
                    "repair highest-authority sources first"
                ),
                evidence=[outcomes_path.relative_to(vault).as_posix()],
                subject_id=";".join(sample_subjects)[:200] or None,
            )
        )
        # Keep a small inspectable sample of individual failures.
        for item in source_failures[:3]:
            items.append(item)

    order = {name: index for index, name in enumerate(LEVELS)}
    items.sort(key=lambda row: (order.get(str(row["level"]), 99), str(row.get("subject_id"))))

    # D-044 / D-041: CLEAR only when relevant review/compile state was positively
    # inspected. Absent or unreadable artifacts must never collapse to CLEAR.
    key_statuses = {
        "conflicts": conflicts_status,
        "pending": pending_status,
        "outcomes": outcomes_status,
    }
    unreadable = [name for name, status in key_statuses.items() if status == "unreadable"]
    absent = [name for name, status in key_statuses.items() if status == "absent"]
    inspected_ok = [name for name, status in key_statuses.items() if status == "ok"]

    if unreadable:
        items.append(
            _item(
                level="INCOMPLETE",
                kind="inspection_incomplete",
                reason_code="ARTIFACT_UNREADABLE",
                why=(
                    "One or more attention artifacts exist but could not be parsed: "
                    + ",".join(unreadable)
                ),
                impact="Attention state is incomplete; do not treat as CLEAR",
                action="Repair JSON encoding/structure or re-run atlas connect",
                evidence=inspected[:3],
            )
        )
    elif not inspected_ok:
        # Empty vault / failed-connect leftover / never compiled for this project.
        items.append(
            _item(
                level="UNKNOWN",
                kind="inspection_unknown",
                reason_code="STATE_UNINSPECTED",
                why=(
                    "No readable review/compile attention artifacts for this project "
                    f"({', '.join(absent) or 'none'})"
                ),
                impact="Atlas has not positively verified a clear attention state",
                action="Run atlas connect (or compile) then re-check atlas attention",
                evidence=inspected[:3],
            )
        )

    rollup_rank = {name: index for index, name in enumerate(_ROLLUP_ORDER)}
    if items:
        rollup = min(
            (str(item.get("level") or "UNKNOWN") for item in items),
            key=lambda level: rollup_rank.get(level, 99),
        )
    else:
        # All key artifacts readable and empty → positively inspected CLEAR.
        rollup = "CLEAR" if len(inspected_ok) == 3 else "UNKNOWN"

    # Default presentation: 3-10 things the user should actually care about.
    # Cap BLOCKING samples so ACTION_REQUIRED / NEEDS_HUMAN_REVIEW remain visible.
    care_about: list[dict[str, Any]] = []
    for level, limit in (
        ("BLOCKING", 5),
        ("ACTION_REQUIRED", 3),
        ("NEEDS_HUMAN_REVIEW", 2),
    ):
        level_items = [item for item in items if item.get("level") == level]
        care_about.extend(level_items[:limit])
    if len(care_about) < 3:
        for item in items:
            if item in care_about:
                continue
            if item.get("level") in {"LOW_VALUE_NOISE"}:
                continue
            care_about.append(item)
            if len(care_about) >= 3:
                break
    care_about = care_about[:10]

    level_counts: dict[str, int] = {}
    for item in items:
        level = str(item.get("level") or "UNKNOWN")
        level_counts[level] = level_counts.get(level, 0) + 1

    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.attention.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "rollup": rollup,
        "item_count": len(items),
        "level_counts": level_counts,
        "source_failure_total": len(source_failures),
        "care_about": care_about,
        "care_about_count": len(care_about),
        "items": items,
        "inspected_artifacts": inspected,
        "generated": {"by": GENERATOR_ID},
        "inspection": {
            "conflicts": conflicts_status,
            "pending": pending_status,
            "outcomes": outcomes_status,
            "positively_inspected": len(inspected_ok) == 3 and not unreadable,
        },
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "confidence_theatre": False,
            "lens_is_authority": False,
            "unknown_is_valid": True,
            "failures_hidden": False,
            "clear_requires_positive_inspection": True,
        },
        "truth_boundary": "ATTENTION LENS != AUTHORITY / UI != CANONICAL",
    }
