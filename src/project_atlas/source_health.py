"""AS-CODER-ALPHA-SOURCE-HEALTH-001 — explainable source failures (D-040).

Read-only projection over connect-manifest exclusions, secret/injection
quarantine metadata, and compile outcomes. Never echoes secret content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID = "AS-CODER-ALPHA-SOURCE-HEALTH-001"
GENERATOR_ID = "atlas-coder-alpha-source-health-001"

REASON_HUMAN = {
    "default-excluded-directory": (
        "Path matches a default excluded directory (e.g. fixtures, .git)."
    ),
    "configured-exclusion": "Path matched an explicit exclude glob.",
    "sensitive-metadata-only": (
        "Filename looks credential-bearing; content not hashed/imported."
    ),
    "unsupported-format": "File extension is not a supported text documentation format.",
    "oversized": "File exceeded the configured max size for discovery.",
    "SECRET_QUARANTINE": "Likely secret patterns detected; source quarantined before import.",
    "INJECTION_QUARANTINE": "Prompt-injection cues detected; source quarantined.",
    "FAILED": "Knowledge compile marked this source FAILED.",
    "PROMOTION_FAILED": "Candidate existed but promotion into Truth failed.",
    "UNCLASSIFIED": "Failure recorded without a known reason code.",
}


class SourceHealthError(ValueError):
    """Fail-closed source-health error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise SourceHealthError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, (dict, list)) else None


def _row(
    *,
    source: str,
    status: str,
    pipeline_stage: str,
    reason_code: str,
    evidence: str,
    next_action: str,
    source_id: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "status": status,
        "pipeline_stage": pipeline_stage,
        "reason_code": reason_code,
        "human_explanation": REASON_HUMAN.get(reason_code, REASON_HUMAN["UNCLASSIFIED"]),
        "evidence": evidence,
        "suggested_next_action": next_action,
    }


def explain_source_health(vault: Path, project_id: str | None = None) -> dict[str, Any]:
    """Explain failed/excluded/quarantined sources (read-only, no secrets)."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise SourceHealthError(f"vault is not a directory: {vault}")
    if project_id is not None:
        project_id = _safe_project_id(project_id)

    rows: list[dict[str, Any]] = []
    inspected: list[str] = []

    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    inspected.append(manifest_path.relative_to(vault).as_posix())
    manifest = _read_json(manifest_path)
    sources = manifest.get("sources") if isinstance(manifest, dict) else None
    if isinstance(sources, list):
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            likely = str(entry.get("likely_project") or "unknown-project")
            if project_id and likely not in {project_id, "unknown-project"}:
                continue
            reason = entry.get("exclusion_reason")
            if not reason:
                continue
            rows.append(
                _row(
                    source=str(entry.get("path") or "UNKNOWN"),
                    source_id=str(entry.get("source_id") or "") or None,
                    status="excluded",
                    pipeline_stage="discover",
                    reason_code=str(reason),
                    evidence=manifest_path.relative_to(vault).as_posix(),
                    next_action="Adjust includes/excludes or move docs outside excluded trees",
                )
            )

    secrets_path = vault / "generated" / "reports" / "secret-findings.json"
    inspected.append(secrets_path.relative_to(vault).as_posix())
    secrets = _read_json(secrets_path)
    secret_rows = secrets if isinstance(secrets, list) else (
        secrets.get("findings") if isinstance(secrets, dict) else None
    )
    if isinstance(secret_rows, list):
        for finding in secret_rows:
            if not isinstance(finding, dict):
                continue
            rows.append(
                _row(
                    source=str(finding.get("path") or "UNKNOWN"),
                    source_id=str(finding.get("source_id") or "") or None,
                    status="quarantined",
                    pipeline_stage="ingest",
                    reason_code="SECRET_QUARANTINE",
                    evidence=secrets_path.relative_to(vault).as_posix(),
                    next_action="Remove/redact credentials and re-run atlas connect",
                )
            )

    injection_path = vault / "generated" / "reports" / "injection-findings.json"
    inspected.append(injection_path.relative_to(vault).as_posix())
    injection = _read_json(injection_path)
    inj_findings = injection.get("findings") if isinstance(injection, dict) else None
    if isinstance(inj_findings, list):
        for finding in inj_findings:
            if not isinstance(finding, dict):
                continue
            rows.append(
                _row(
                    source=str(finding.get("path") or "UNKNOWN"),
                    source_id=str(finding.get("source_id") or "") or None,
                    status="quarantined",
                    pipeline_stage="ingest",
                    reason_code="INJECTION_QUARANTINE",
                    evidence=injection_path.relative_to(vault).as_posix(),
                    next_action="Rewrite source to remove instruction-override cues; reconnect",
                )
            )

    if project_id:
        outcomes_path = vault / "state" / "compilation-outcomes" / f"{project_id}.json"
        inspected.append(outcomes_path.relative_to(vault).as_posix())
        outcomes = _read_json(outcomes_path)
        candidates: list[Any] = []
        if isinstance(outcomes, dict):
            raw_candidates = outcomes.get("candidates")
            if isinstance(raw_candidates, list):
                candidates = raw_candidates
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            outcome = str(candidate.get("outcome") or "")
            if outcome.upper() not in {"FAILED", "PROMOTION_FAILED", "PARTIAL_CANDIDATE"}:
                continue
            rows.append(
                _row(
                    source=str(
                        candidate.get("path") or candidate.get("source_id") or "UNKNOWN"
                    ),
                    source_id=str(candidate.get("source_id") or "") or None,
                    status=(
                        "compile_failed" if "FAIL" in outcome.upper() else "compile_partial"
                    ),
                    pipeline_stage="compile",
                    reason_code=outcome or "UNCLASSIFIED",
                    evidence=outcomes_path.relative_to(vault).as_posix(),
                    next_action="Inspect diagnostics and repair source structure/metadata",
                )
            )

    rows.sort(key=lambda row: (row["pipeline_stage"], row["status"], row["source"]))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.source-health.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "source_count": len(rows),
        "counts": counts,
        "sources": rows,
        "inspected_artifacts": inspected,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "secrets_echoed": False,
            "lens_is_authority": False,
            "unknown_is_valid": True,
        },
        "truth_boundary": "SOURCE HEALTH != AUTHORITY / NO SECRET ECHO",
    }
