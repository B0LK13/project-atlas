"""AS-CODER-ALPHA-SOURCE-HEALTH-001 — explainable source failures (D-040/D-044).

Read-only projection over connect-manifest exclusions, secret/injection
quarantine metadata, and compile outcomes. Never echoes secret content.

D-044 honesty:
- UNREADABLE != HEALTHY / UNKNOWN != CLEAR
- ``--project X`` must not import ``unknown-project`` evidence into X
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.inventory_drift import (
    attach_source_drift,
    evaluate_connect_inventory_drift,
)

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
    "PARTIAL_CANDIDATE": (
        "Source produced a partial candidate; some claims withheld pending repair."
    ),
    "PROMOTION_FAILED": "Candidate existed but promotion into Truth failed.",
    "UNCLASSIFIED": "Failure recorded without a known reason code.",
    "ARTIFACT_UNREADABLE": "Artifact exists but could not be parsed as JSON.",
    "ARTIFACT_ABSENT": "Expected health artifact is absent; state not positively inspected.",
}


class SourceHealthError(ValueError):
    """Fail-closed source-health error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise SourceHealthError(str(exc)) from exc


def _read_json(path: Path) -> tuple[str, dict[str, Any] | list[Any] | None]:
    """Return ``(status, payload)`` where status is absent|ok|unreadable."""
    if not path.is_file():
        return "absent", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreadable", None
    if isinstance(raw, (dict, list)):
        return "ok", raw
    return "unreadable", None


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


def _manifest_project_indexes(
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(source_id→project, path→project)`` from connect-manifest."""
    by_id: dict[str, str] = {}
    by_path: dict[str, str] = {}
    if not isinstance(manifest, dict):
        return by_id, by_path
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return by_id, by_path
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        likely = str(entry.get("likely_project") or "unknown-project")
        source_id = str(entry.get("source_id") or "")
        path = str(entry.get("path") or "").replace("\\", "/")
        if source_id:
            by_id[source_id] = likely
        if path:
            by_path[path] = likely
    return by_id, by_path


def _finding_matches_project(
    finding: dict[str, Any],
    *,
    project_id: str | None,
    source_projects: dict[str, str],
    path_projects: dict[str, str],
) -> bool:
    """Scope quarantine findings to ``project_id`` when requested.

    D-044: ``unknown-project`` / unmapped ownership must NOT be imported into a
    scoped project report. Unknown stays UNSCOPED.
    """
    if project_id is None:
        return True
    source_id = str(finding.get("source_id") or "")
    if source_id and source_id in source_projects:
        return source_projects[source_id] == project_id
    path = str(finding.get("path") or finding.get("source_path") or "").replace("\\", "/")
    if path and path in path_projects:
        return path_projects[path] == project_id
    return False


def _is_noise_row(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "").replace("\\", "/").lower()
    reason = str(row.get("reason_code") or "")
    if ".atlas-vault" in source or source.startswith(".atlas/"):
        return True
    noise_tokens = (
        "node_modules/",
        "__pycache__/",
        ".git/",
        "/dist/",
        "/build/",
        ".venv/",
    )
    excluded = reason in {"default-excluded-directory", "configured-exclusion"}
    return excluded and any(token in source for token in noise_tokens)


def explain_source_health(vault: Path, project_id: str | None = None) -> dict[str, Any]:
    """Explain failed/excluded/quarantined sources (read-only, no secrets)."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise SourceHealthError(f"vault is not a directory: {vault}")
    if project_id is not None:
        project_id = _safe_project_id(project_id)

    rows: list[dict[str, Any]] = []
    inspected: list[str] = []
    artifact_status: dict[str, str] = {}
    unscoped_omitted = 0
    diagnostic = "ok"

    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    durable_path = vault / "sources" / "manifests" / "source-manifest.json"
    inspected.append(manifest_path.relative_to(vault).as_posix())
    inspected.append(durable_path.relative_to(vault).as_posix())
    manifest_status, manifest_raw = _read_json(manifest_path)
    durable_status, durable_raw = _read_json(durable_path)
    artifact_status["connect-manifest"] = manifest_status
    artifact_status["source-manifest"] = durable_status
    if manifest_status == "unreadable":
        diagnostic = "unreadable"
        rows.append(
            _row(
                source="generated/ops/connect-manifest.json",
                status="unreadable",
                pipeline_stage="discover",
                reason_code="ARTIFACT_UNREADABLE",
                evidence=manifest_path.relative_to(vault).as_posix(),
                next_action="Repair connect-manifest JSON or re-run atlas connect",
            )
        )
    manifest = manifest_raw if isinstance(manifest_raw, dict) else None
    # Ownership for quarantine/secret scoping: durable multi-project source-manifest
    # wins over last-writer connect-manifest (D-050 shared-vault isolation).
    ownership: dict[str, Any] | None
    ownership_evidence = manifest_path.relative_to(vault).as_posix()
    # Project-scoped ownership requires durable multi-project inventory.
    # Absent/unreadable durable must fail closed — never trust last-writer
    # connect-manifest alone (shared-vault false CLEAR).
    if durable_status == "ok" and isinstance(durable_raw, dict):
        ownership = durable_raw
        ownership_evidence = durable_path.relative_to(vault).as_posix()
    elif project_id is not None:
        ownership = None
        ownership_evidence = durable_path.relative_to(vault).as_posix()
    else:
        ownership = manifest
    source_projects, path_projects = _manifest_project_indexes(ownership)
    # Enumerate exclusions from durable multi-project inventory when available.
    # connect-manifest is last-writer single-root and drops sibling exclusions (D-050).
    sources = ownership.get("sources") if isinstance(ownership, dict) else None
    if isinstance(sources, list):
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            likely = str(entry.get("likely_project") or "unknown-project")
            if project_id:
                if likely == "unknown-project":
                    unscoped_omitted += 1
                    continue
                if likely != project_id:
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
                    evidence=ownership_evidence,
                    next_action="Adjust includes/excludes or move docs outside excluded trees",
                )
            )

    secrets_path = vault / "generated" / "reports" / "secret-findings.json"
    inspected.append(secrets_path.relative_to(vault).as_posix())
    secrets_status, secrets = _read_json(secrets_path)
    artifact_status["secret-findings"] = secrets_status
    if secrets_status == "unreadable":
        diagnostic = "unreadable"
        rows.append(
            _row(
                source="generated/reports/secret-findings.json",
                status="unreadable",
                pipeline_stage="ingest",
                reason_code="ARTIFACT_UNREADABLE",
                evidence=secrets_path.relative_to(vault).as_posix(),
                next_action="Repair secret-findings JSON (metadata only; never echo secrets)",
            )
        )
    secret_rows = secrets if isinstance(secrets, list) else (
        secrets.get("findings") if isinstance(secrets, dict) else None
    )
    if isinstance(secret_rows, list):
        dict_findings = [row for row in secret_rows if isinstance(row, dict)]
        if (
            project_id is not None
            and dict_findings
            and not source_projects
            and not path_projects
        ):
            # Findings exist but ownership cannot be scoped — never false CLEAR.
            rows.append(
                _row(
                    source="sources/manifests/source-manifest.json",
                    status="unknown",
                    pipeline_stage="ingest",
                    reason_code="SECRET_OWNERSHIP_UNKNOWN",
                    evidence=ownership_evidence,
                    next_action="Re-run atlas connect to restore source-manifest ownership",
                )
            )
        else:
            for finding in dict_findings:
                if not _finding_matches_project(
                    finding,
                    project_id=project_id,
                    source_projects=source_projects,
                    path_projects=path_projects,
                ):
                    if project_id is not None:
                        unscoped_omitted += 1
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
    injection_status, injection = _read_json(injection_path)
    artifact_status["injection-findings"] = injection_status
    if injection_status == "unreadable":
        diagnostic = "unreadable"
        rows.append(
            _row(
                source="generated/reports/injection-findings.json",
                status="unreadable",
                pipeline_stage="ingest",
                reason_code="ARTIFACT_UNREADABLE",
                evidence=injection_path.relative_to(vault).as_posix(),
                next_action="Repair injection-findings JSON and reconnect",
            )
        )
    inj_findings = injection.get("findings") if isinstance(injection, dict) else None
    if isinstance(inj_findings, list):
        for finding in inj_findings:
            if not isinstance(finding, dict):
                continue
            if not _finding_matches_project(
                finding,
                project_id=project_id,
                source_projects=source_projects,
                path_projects=path_projects,
            ):
                if project_id is not None:
                    unscoped_omitted += 1
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
        outcomes_status, outcomes = _read_json(outcomes_path)
        artifact_status["compilation-outcomes"] = outcomes_status
        if outcomes_status == "unreadable":
            diagnostic = "unreadable"
            rows.append(
                _row(
                    source=outcomes_path.relative_to(vault).as_posix(),
                    status="unreadable",
                    pipeline_stage="compile",
                    reason_code="ARTIFACT_UNREADABLE",
                    evidence=outcomes_path.relative_to(vault).as_posix(),
                    next_action="Repair compilation-outcomes JSON or recompile",
                )
            )
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
                        candidate.get("source_path")
                        or candidate.get("path")
                        or candidate.get("source_id")
                        or "UNKNOWN"
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

        promo_path = vault / "quarantine" / "promotion-failures" / "index.json"
        inspected.append(promo_path.relative_to(vault).as_posix())
        promo_status, promo = _read_json(promo_path)
        artifact_status["promotion-failures"] = promo_status
        if promo_status == "unreadable":
            diagnostic = "unreadable"
            rows.append(
                _row(
                    source=promo_path.relative_to(vault).as_posix(),
                    status="unreadable",
                    pipeline_stage="promote",
                    reason_code="ARTIFACT_UNREADABLE",
                    evidence=promo_path.relative_to(vault).as_posix(),
                    next_action="Inspect quarantine/promotion-failures/index.json",
                )
            )
        if isinstance(promo, dict):
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
                    rows.append(
                        _row(
                            source=str(candidate.get("source_path") or "UNKNOWN"),
                            source_id=str(candidate.get("source_id") or "") or None,
                            status="promotion_failed",
                            pipeline_stage="promote",
                            reason_code="PROMOTION_FAILED",
                            evidence=promo_path.relative_to(vault).as_posix(),
                            next_action=(
                                "Resolve promotion fault and re-run atlas connect/ingest; "
                                "canonical state was rolled back"
                            ),
                        )
                    )
    elif manifest_status == "absent" and secrets_status == "absent":
        diagnostic = "unknown"
        rows.append(
            _row(
                source="(none)",
                status="unknown",
                pipeline_stage="inspect",
                reason_code="ARTIFACT_ABSENT",
                evidence="generated/ops/connect-manifest.json",
                next_action="Run atlas connect before interpreting source health",
            )
        )

    rows.sort(key=lambda row: (row["pipeline_stage"], row["status"], row["source"]))
    actionable = [row for row in rows if not _is_noise_row(row)]
    noise = [row for row in rows if _is_noise_row(row)]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    reason_counts: dict[str, int] = {}
    for row in actionable:
        code = str(row.get("reason_code") or "UNCLASSIFIED")
        reason_counts[code] = reason_counts.get(code, 0) + 1
    noise_groups: dict[str, int] = {}
    for row in noise:
        source = str(row.get("source") or "").replace("\\", "/")
        if ".atlas-vault" in source:
            key = ".atlas-vault/**"
        elif "node_modules" in source:
            key = "node_modules/**"
        else:
            key = str(row.get("reason_code") or "excluded")
        noise_groups[key] = noise_groups.get(key, 0) + 1

    # Empty + readable must not look "healthy" when diagnostic is unreadable/unknown.
    if diagnostic == "unreadable":
        health_state = "UNREADABLE"
    elif diagnostic == "unknown":
        health_state = "UNKNOWN"
    elif any(
        row["status"] in {"quarantined", "compile_failed", "promotion_failed", "unreadable"}
        for row in actionable
    ):
        health_state = "ACTION_REQUIRED"
    elif actionable:
        health_state = "INFORMATIONAL"
    else:
        health_state = "CLEAR" if artifact_status.get("connect-manifest") == "ok" else "UNKNOWN"

    if project_id is not None:
        drift = evaluate_connect_inventory_drift(vault, project_id)
        drift_status = str(drift.get("status") or "UNKNOWN")
        reason_code = str(drift.get("reason_code") or "")
        if health_state == "CLEAR" and drift_status == "STALE":
            health_state = "STALE"
        elif health_state == "CLEAR" and reason_code == "SOURCE_ROOT_UNVERIFIED":
            health_state = "UNKNOWN"

    payload = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.source-health.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "diagnostic": diagnostic,
        "health_state": health_state,
        "source_count": len(rows),
        "actionable_count": len(actionable),
        "noise_count": len(noise),
        "unscoped_omitted_count": unscoped_omitted,
        "counts": counts,
        "reason_counts": reason_counts,
        "noise_groups": noise_groups,
        "summary": {
            "health_state": health_state,
            "action_required": len(
                [
                    row
                    for row in actionable
                    if row["status"]
                    in {"quarantined", "compile_failed", "promotion_failed", "unreadable"}
                ]
            ),
            "excluded_informational": len(noise),
        },
        "sources": actionable + noise,
        "actionable": actionable,
        "noise": noise,
        "artifact_status": artifact_status,
        "inspected_artifacts": inspected,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "secrets_echoed": False,
            "lens_is_authority": False,
            "unknown_is_valid": True,
            "unreadable_as_healthy": False,
            "unknown_project_leaked": False,
        },
        "truth_boundary": "SOURCE HEALTH != AUTHORITY / NO SECRET ECHO",
    }
    if project_id is not None:
        return attach_source_drift(payload, vault, project_id)
    return payload
