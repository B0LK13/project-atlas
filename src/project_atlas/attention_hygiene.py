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
    "INFORMATIONAL",
    "LOW_VALUE_NOISE",
)


class AttentionHygieneError(ValueError):
    """Fail-closed attention hygiene error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise AttentionHygieneError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


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
    conflicts = _read_json(conflicts_path)
    for entry in (conflicts or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        ctype = str(entry.get("conflict_type") or "unknown")
        level = "DUPLICATE" if ctype == "duplicate-source" else "CONFLICT"
        if level == "CONFLICT":
            level = "BLOCKING"
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
    pending = _read_json(pending_path)
    pending_count = 0
    for entry in (pending or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "pending")
        if status not in {"pending", "in-review", ""}:
            continue
        pending_count += 1
        category = str(entry.get("category") or entry.get("reason") or "pending-claim")
        level = "NEEDS_HUMAN_REVIEW"
        if "stale" in category.lower():
            level = "STALE"
        elif "superseded" in category.lower():
            level = "SUPERSEDED"
        items.append(
            _item(
                level=level,
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
    outcomes = _read_json(outcomes_path)
    failed = 0
    for candidate in (outcomes or {}).get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        outcome = str(candidate.get("outcome") or "")
        if outcome.upper() not in {"FAILED", "PROMOTION_FAILED"}:
            continue
        failed += 1
        items.append(
            _item(
                level="SOURCE_FAILURE",
                kind="compile_failure",
                reason_code=outcome,
                why="Source candidate failed during knowledge compile",
                impact="Claims from this source are unavailable or withheld",
                action="Open diagnostics and repair or replace the source",
                evidence=[outcomes_path.relative_to(vault).as_posix()],
                subject_id=str(candidate.get("source_id") or candidate.get("candidate_id") or ""),
            )
        )

    # Cap low-value noise: collapse huge pending queues into summary item.
    if pending_count > 20:
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
        # Keep a sample of first 5 pending for actionability.
        sample = 0
        for entry in (pending or {}).get("entries") or []:
            if not isinstance(entry, dict):
                continue
            status = str(entry.get("status") or "pending")
            if status not in {"pending", "in-review", ""}:
                continue
            items.append(
                _item(
                    level="NEEDS_HUMAN_REVIEW",
                    kind="pending_review",
                    reason_code=str(entry.get("category") or "pending-claim"),
                    why=str(entry.get("reason") or "Claim requires human verification"),
                    impact="Sample pending item requiring disposition",
                    action="atlas review decide",
                    evidence=[pending_path.relative_to(vault).as_posix()],
                    subject_id=str(entry.get("review_id") or ""),
                )
            )
            sample += 1
            if sample >= 5:
                break

    order = {name: index for index, name in enumerate(LEVELS)}
    items.sort(key=lambda row: (order.get(str(row["level"]), 99), str(row.get("subject_id"))))
    rollup = str(items[0]["level"]) if items else "CLEAR"

    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.attention.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "rollup": rollup,
        "item_count": len(items),
        "items": items,
        "inspected_artifacts": inspected,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "confidence_theatre": False,
            "lens_is_authority": False,
            "unknown_is_valid": True,
        },
        "truth_boundary": "ATTENTION LENS != AUTHORITY / UI != CANONICAL",
    }
