"""AS-2.0-API-001 — read-only intelligence projections for LIVE_API.

Library results only. Never writes Layer B. Never replaces ``/v1/conflicts``.
``DERIVED_INTELLIGENCE_IS_AUTHORITY = NO``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.domain import (
    AuthorityLevel,
    ClaimLifecycle,
    ConfidenceState,
    ProvenanceReference,
)
from project_atlas.intelligence import (
    IntelligenceQuery,
    IntelligenceQueryKind,
    aggregate_portfolio_state,
    detect_portfolio_dependencies,
    query_intelligence,
    rank_portfolio_attention,
    synthesize_project_state,
)
from project_atlas.intelligence.boundary import (
    DERIVED_INTELLIGENCE_IS_AUTHORITY,
    TRUTH_BOUNDARY_CONTRADICTION,
    TRUTH_BOUNDARY_QUERY,
    TRUTH_BOUNDARY_RISK,
    TRUTH_BOUNDARY_STATE,
)
from project_atlas.intelligence.derived_state import StateContext
from project_atlas.intelligence.timewin import IntelligenceTimeError, parse_instant
from project_atlas.intelligence.types import AssessableClaim

PACKAGE_ID = "AS-2.0-API-001"


class WebIntelligenceError(ValueError):
    """Fail-closed intelligence API read error."""


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebIntelligenceError("intel-api-project-id-required")
    try:
        return safe_relative_component(token, label="project id")
    except ValueError as exc:
        raise WebIntelligenceError("intel-api-project-id-invalid") from exc


def _optional_as_of(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parse_instant(text, field="as-of")
    except IntelligenceTimeError as exc:
        raise WebIntelligenceError(str(exc)) from exc
    return text


def load_assessable_claims(vault: Path, project_id: str) -> tuple[AssessableClaim, ...]:
    """Read ``state/claims/<project>.json``. Missing file is empty, not invented."""
    token = _safe_project_id(project_id)
    path = vault / "state" / "claims" / f"{token}.json"
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WebIntelligenceError(f"intel-api-claims-unreadable:{token}") from exc
    entries = raw.get("claims") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise WebIntelligenceError(f"intel-api-claims-malformed:{token}")
    found: list[AssessableClaim] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        claim = _claim_from_record(item, token)
        if claim is not None:
            found.append(claim)
    return tuple(found)


def _claim_from_record(item: dict[str, Any], project_id: str) -> AssessableClaim | None:
    claim_id = str(item.get("claim_id") or "").strip()
    subject = str(item.get("subject") or "").strip()
    field = str(item.get("field") or "").strip()
    if not claim_id or not subject or not field:
        return None
    refs: list[ProvenanceReference] = []
    provenance = item.get("provenance")
    if isinstance(provenance, list):
        for ref in provenance:
            if not isinstance(ref, dict):
                continue
            source_id = str(ref.get("source_id") or "").strip()
            resource = str(ref.get("resource") or "").strip()
            if not source_id or not resource:
                continue
            sha = ref.get("sha256")
            try:
                refs.append(
                    ProvenanceReference(
                        source_id=source_id,
                        resource=resource,
                        sha256=sha if isinstance(sha, str) else None,
                    )
                )
            except ValueError:
                continue
    return AssessableClaim(
        claim_id=claim_id,
        project_id=str(item.get("project_id") or project_id),
        subject=subject,
        field=field,
        value=str(item.get("value") or ""),
        provenance=tuple(refs),
        authority=_enum_or_none(AuthorityLevel, item.get("authority")),
        confidence=_enum_or_none(ConfidenceState, item.get("confidence")),
        lifecycle=_enum_or_none(ClaimLifecycle, item.get("lifecycle")),
        claim_type=str(item.get("claim_type") or "") or None,
    )


def _enum_or_none(enum_type: type[Any], raw: object) -> Any:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return enum_type(raw)
    except ValueError:
        return None


def _query(
    project_id: str,
    kind: IntelligenceQueryKind,
    *,
    subject: str | None = None,
    field: str | None = None,
    claim_id: str | None = None,
    as_of_valid_time: str | None = None,
) -> IntelligenceQuery:
    return IntelligenceQuery(
        project_id=project_id,
        kind=kind,
        subject=subject or None,
        field=field or None,
        claim_id=claim_id or None,
        as_of_valid_time=as_of_valid_time,
    )


def read_intelligence_evidence(
    vault: Path,
    project_id: str,
    *,
    subject: str | None = None,
    field: str | None = None,
    claim_id: str | None = None,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    token = _safe_project_id(project_id)
    as_of = _optional_as_of(as_of_valid_time)
    answer = query_intelligence(
        _query(
            token,
            IntelligenceQueryKind.EVIDENCE,
            subject=subject,
            field=field,
            claim_id=claim_id,
            as_of_valid_time=as_of,
        ),
        load_assessable_claims(vault, token),
    )
    return {
        "package_id": PACKAGE_ID,
        "project_id": token,
        "outcome": answer.outcome.value,
        "status": answer.status.value,
        "reason": answer.reason,
        "assessments": [item.model_dump(mode="json") for item in answer.assessments],
        "authority_note": answer.authority_note,
        "derived_intelligence_is_authority": DERIVED_INTELLIGENCE_IS_AUTHORITY,
        "truth_boundary": TRUTH_BOUNDARY_QUERY,
        "canonical_write": False,
    }


def read_intelligence_conflicts(
    vault: Path,
    project_id: str,
    *,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    token = _safe_project_id(project_id)
    as_of = _optional_as_of(as_of_valid_time)
    answer = query_intelligence(
        _query(token, IntelligenceQueryKind.CONFLICTS, as_of_valid_time=as_of),
        load_assessable_claims(vault, token),
    )
    return {
        "package_id": PACKAGE_ID,
        "project_id": token,
        "candidates": [item.model_dump() for item in answer.candidates],
        "authority_note": "candidate-not-resolution",
        "derived_intelligence_is_authority": DERIVED_INTELLIGENCE_IS_AUTHORITY,
        "truth_boundary": TRUTH_BOUNDARY_CONTRADICTION,
        "canonical_write": False,
        "replaces_v1_conflicts": False,
    }


def read_intelligence_explain(
    vault: Path,
    project_id: str,
    *,
    subject: str | None = None,
    field: str | None = None,
    claim_id: str | None = None,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    token = _safe_project_id(project_id)
    as_of = _optional_as_of(as_of_valid_time)
    answer = query_intelligence(
        _query(
            token,
            IntelligenceQueryKind.EXPLAIN,
            subject=subject,
            field=field,
            claim_id=claim_id,
            as_of_valid_time=as_of,
        ),
        load_assessable_claims(vault, token),
    )
    return {
        "package_id": PACKAGE_ID,
        "project_id": token,
        "explanation": answer.explanation,
        "status": answer.status.value,
        "reason": answer.reason,
        "authority_note": answer.authority_note,
        "derived_intelligence_is_authority": DERIVED_INTELLIGENCE_IS_AUTHORITY,
        "truth_boundary": TRUTH_BOUNDARY_QUERY,
        "canonical_write": False,
    }


def read_project_state(
    vault: Path,
    project_id: str,
    *,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    token = _safe_project_id(project_id)
    as_of = _optional_as_of(as_of_valid_time)
    state = synthesize_project_state(
        token,
        load_assessable_claims(vault, token),
        StateContext(as_of_valid_time=as_of),
    )
    payload = state.model_dump(mode="json")
    payload["package_id"] = PACKAGE_ID
    payload["derived_intelligence_is_authority"] = DERIVED_INTELLIGENCE_IS_AUTHORITY
    payload["canonical_write"] = False
    payload["truth_boundary"] = TRUTH_BOUNDARY_STATE
    return payload


def read_project_attention(
    vault: Path,
    project_id: str,
    *,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    token = _safe_project_id(project_id)
    as_of = _optional_as_of(as_of_valid_time)
    answer = query_intelligence(
        _query(token, IntelligenceQueryKind.ATTENTION, as_of_valid_time=as_of),
        load_assessable_claims(vault, token),
    )
    return {
        "package_id": PACKAGE_ID,
        "project_id": token,
        "risks": list(answer.risks),
        "authority_note": "risk-is-not-fact",
        "derived_intelligence_is_authority": DERIVED_INTELLIGENCE_IS_AUTHORITY,
        "truth_boundary": TRUTH_BOUNDARY_RISK,
        "canonical_write": False,
    }


def _known_claim_projects(vault: Path) -> tuple[str, ...]:
    root = vault / "state" / "claims"
    if not root.is_dir():
        return ()
    found: list[str] = []
    for path in sorted(root.glob("*.json")):
        try:
            found.append(safe_relative_component(path.stem, label="project id"))
        except ValueError:
            continue
    return tuple(found)


def read_portfolio_state(
    vault: Path,
    project_ids: tuple[str, ...] = (),
    *,
    as_of_valid_time: str | None = None,
) -> dict[str, Any]:
    as_of = _optional_as_of(as_of_valid_time)
    requested = tuple(_safe_project_id(item) for item in project_ids if item.strip())
    keys = requested or _known_claim_projects(vault)
    projects = {key: load_assessable_claims(vault, key) for key in keys}
    state = aggregate_portfolio_state(projects, as_of_valid_time=as_of)
    deps = detect_portfolio_dependencies(projects)
    attention = rank_portfolio_attention(projects, as_of_valid_time=as_of)
    return {
        "package_id": PACKAGE_ID,
        "state": state.model_dump(mode="json"),
        "dependencies": [item.model_dump(mode="json") for item in deps],
        "attention": [item.model_dump(mode="json") for item in attention],
        "derived_intelligence_is_authority": DERIVED_INTELLIGENCE_IS_AUTHORITY,
        "canonical_write": False,
        "numeric_priority_score": None,
    }
