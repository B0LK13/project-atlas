"""AS-CORE-007 / AS-CORE-008 Knowledge Query — read-only consumer of persisted state.

Does not call evaluate_authority / evaluate_conflicts and never writes the vault.
Answers derive solely from state/current-state and state/authoritative-state plus
immutable claims for provenance projection.

AS-CORE-008 adds subject multi-field composition under one shared snapshot load.
Composition ≠ new authority; multi-field success ≠ all fields authoritative.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from project_atlas.domain.authority_semantics import AuthoritativeStateRecord
from project_atlas.domain.claims import Claim, validate_claim_subject
from project_atlas.domain.knowledge_query import (
    AnswerStatus,
    ClaimProjection,
    KnowledgeAnswer,
    KnowledgeMultiFieldAnswer,
    KnowledgeQueryErrorCode,
    QueryKind,
)
from project_atlas.domain.temporal import CurrentStateRecord

QueryKindName = Literal["authoritative", "temporal", "explain"]


class KnowledgeQueryError(Exception):
    """Operational / integrity failure (CLI exit 1)."""

    def __init__(self, code: KnowledgeQueryErrorCode | str, message: str) -> None:
        self.code = KnowledgeQueryErrorCode(code) if not isinstance(
            code, KnowledgeQueryErrorCode
        ) else code
        self.message = message
        super().__init__(f"{self.code.value}: {message}")


def answer_to_json(
    answer: KnowledgeAnswer | KnowledgeMultiFieldAnswer | list[KnowledgeAnswer],
) -> str:
    """Serialize answer(s) deterministically (AS-CORE-007-FR-009 / AS-CORE-008-FR-010)."""
    if isinstance(answer, list):
        payload: Any = [item.model_dump(mode="json") for item in answer]
    else:
        payload = answer.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def query_knowledge(
    vault: Path,
    project_id: str,
    subject: str,
    field: str,
    *,
    kind: QueryKindName = "authoritative",
) -> KnowledgeAnswer:
    """Answer a (project, subject, field) query from persisted vault state."""
    if not project_id or not project_id.strip():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, "project_id is required"
        )
    if not field or not field.strip():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, "field is required"
        )
    try:
        subject = validate_claim_subject(subject)
    except ValueError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, str(exc)
        ) from exc

    try:
        query_kind = QueryKind(kind)
    except ValueError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.UNSUPPORTED_KIND,
            f"unsupported query kind: {kind!r}",
        ) from exc

    root = _resolve_vault(vault)
    snapshot = _load_snapshot(root, project_id)
    return _answer_for_kind(snapshot, subject, field, query_kind)


def query_knowledge_fields(
    vault: Path,
    project_id: str,
    subject: str,
    fields: Sequence[str],
    *,
    kind: QueryKindName = "authoritative",
) -> KnowledgeMultiFieldAnswer:
    """Answer (project, subject, fields[]) under one shared compilation snapshot.

    AS-CORE-008 — library-first multi-field composition over point AS-CORE-007
    semantics. Loads project state once; never invents values or recomputes
    authority/temporal dispositions.
    """
    if not project_id or not project_id.strip():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, "project_id is required"
        )
    if not fields:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT,
            "fields must be a non-empty list (AS-CORE-008-FR-008)",
        )
    normalized_fields: list[str] = []
    for index, field in enumerate(fields):
        if not isinstance(field, str) or not field.strip():
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.INVALID_INPUT,
                f"fields[{index}] must be a non-empty string (AS-CORE-008-FR-008)",
            )
        normalized_fields.append(field.strip())
    if len(normalized_fields) != len(set(normalized_fields)):
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT,
            "duplicate field names are not allowed (AS-CORE-008-FR-007)",
        )
    try:
        subject = validate_claim_subject(subject)
    except ValueError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, str(exc)
        ) from exc

    try:
        query_kind = QueryKind(kind)
    except ValueError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.UNSUPPORTED_KIND,
            f"unsupported query kind: {kind!r}",
        ) from exc

    root = _resolve_vault(vault)
    # Single snapshot load — no silent mixed compilation_id (AS-CORE-008-INV-004).
    snapshot = _load_snapshot(root, project_id)

    # Preserve caller field order (AS-CORE-008-FR-006 / INV-007); never dict/set order.
    results: list[KnowledgeAnswer] = [
        _answer_for_kind(snapshot, subject, field_name, query_kind)
        for field_name in normalized_fields
    ]
    return KnowledgeMultiFieldAnswer(
        project_id=project_id,
        subject=subject,
        kind=query_kind,
        compilation_id=snapshot.compilation_id,
        fields=tuple(normalized_fields),
        results=tuple(results),
        inspected_artifacts=_artifacts(snapshot),
    )


def _answer_for_kind(
    snapshot: _ProjectSnapshot,
    subject: str,
    field: str,
    query_kind: QueryKind,
) -> KnowledgeAnswer:
    """Point-answer builder used by AS-CORE-007 and AS-CORE-008 fan-out."""
    if query_kind is QueryKind.TEMPORAL:
        return _answer_temporal(snapshot, subject, field)
    if query_kind is QueryKind.AUTHORITATIVE:
        return _answer_authoritative(snapshot, subject, field)
    return _answer_explain(snapshot, subject, field)


def list_authoritative(vault: Path, project_id: str) -> list[KnowledgeAnswer]:
    """List authoritative-state records for a project in stable order (FR-010)."""
    if not project_id or not project_id.strip():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.INVALID_INPUT, "project_id is required"
        )
    root = _resolve_vault(vault)
    snapshot = _load_snapshot(root, project_id)
    if snapshot.authoritative_path is None:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING,
            f"missing authoritative-state for project {project_id}",
        )
    answers = [
        _answer_authoritative(snapshot, record.subject, record.field)
        for record in snapshot.authoritative_records
    ]
    return sorted(
        answers,
        key=lambda item: (item.subject or "", item.field or "", item.claim_id or ""),
    )


# ---------------------------------------------------------------------------
# Snapshot loading (read-only)
# ---------------------------------------------------------------------------


class _ProjectSnapshot:
    __slots__ = (
        "authoritative_by_key",
        "authoritative_path",
        "authoritative_records",
        "claims_by_id",
        "claims_path",
        "compilation_id",
        "current_by_key",
        "current_path",
        "project_id",
        "registry_version",
        "vault",
    )

    def __init__(self) -> None:
        self.project_id = ""
        self.vault = Path()
        self.claims_path: Path | None = None
        self.current_path: Path | None = None
        self.authoritative_path: Path | None = None
        self.claims_by_id: dict[str, Claim] = {}
        self.current_by_key: dict[tuple[str, str], CurrentStateRecord] = {}
        self.authoritative_by_key: dict[tuple[str, str], AuthoritativeStateRecord] = {}
        self.authoritative_records: list[AuthoritativeStateRecord] = []
        self.compilation_id: str | None = None
        self.registry_version: int | None = None


def _resolve_vault(vault: Path) -> Path:
    try:
        root = vault.expanduser().resolve()
    except OSError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING, f"cannot resolve vault: {exc}"
        ) from exc
    if not root.is_dir():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING, f"vault is not a directory: {root}"
        )
    return root


def _load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
    except FileNotFoundError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING, f"missing state file: {path}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_RACE, f"unreadable state file {path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_CORRUPT, f"malformed JSON in {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_CORRUPT,
            f"state file root must be an object: {path}",
        )
    return raw


def _load_snapshot(vault: Path, project_id: str) -> _ProjectSnapshot:
    snap = _ProjectSnapshot()
    snap.project_id = project_id
    snap.vault = vault

    claims_path = vault / "state" / "claims" / f"{project_id}.json"
    current_path = vault / "state" / "current-state" / f"{project_id}.json"
    auth_path = vault / "state" / "authoritative-state" / f"{project_id}.json"

    if not claims_path.is_file():
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING,
            f"missing claims state: state/claims/{project_id}.json",
        )
    snap.claims_path = claims_path
    claims_raw = _load_json(claims_path)
    compilation_ids: list[str] = []
    claims_cid = claims_raw.get("compilation_id")
    if isinstance(claims_cid, str) and claims_cid:
        compilation_ids.append(claims_cid)

    try:
        for item in claims_raw.get("claims", []):
            if not isinstance(item, dict):
                raise KnowledgeQueryError(
                    KnowledgeQueryErrorCode.STATE_CORRUPT,
                    f"invalid claim entry in {claims_path}",
                )
            claim = Claim.model_validate(item)
            snap.claims_by_id[claim.claim_id] = claim
    except KnowledgeQueryError:
        raise
    except Exception as exc:  # pydantic / type errors
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_CORRUPT,
            f"invalid claims in {claims_path}: {exc}",
        ) from exc

    if current_path.is_file():
        snap.current_path = current_path
        current_raw = _load_json(current_path)
        cid = current_raw.get("compilation_id")
        if isinstance(cid, str) and cid:
            compilation_ids.append(cid)
        try:
            for item in current_raw.get("current_states", []):
                current_record = CurrentStateRecord.model_validate(item)
                snap.current_by_key[(current_record.subject, current_record.field)] = (
                    current_record
                )
        except Exception as exc:
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.STATE_CORRUPT,
                f"invalid current-state in {current_path}: {exc}",
            ) from exc

    if auth_path.is_file():
        snap.authoritative_path = auth_path
        auth_raw = _load_json(auth_path)
        cid = auth_raw.get("compilation_id")
        if isinstance(cid, str) and cid:
            compilation_ids.append(cid)
        reg = auth_raw.get("authority_registry_version")
        if isinstance(reg, int):
            snap.registry_version = reg
        try:
            for item in auth_raw.get("authoritative_states", []):
                auth_record = AuthoritativeStateRecord.model_validate(item)
                snap.authoritative_by_key[(auth_record.subject, auth_record.field)] = (
                    auth_record
                )
                snap.authoritative_records.append(auth_record)
        except Exception as exc:
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.STATE_CORRUPT,
                f"invalid authoritative-state in {auth_path}: {exc}",
            ) from exc
        snap.authoritative_records.sort(
            key=lambda item: (item.subject, item.field, item.rule_id or "")
        )

    if compilation_ids:
        unique = sorted(set(compilation_ids))
        if len(unique) != 1:
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.COMPILATION_MISMATCH,
                f"compilation_id mismatch across state layers: {unique}",
            )
        snap.compilation_id = unique[0]

    return snap


# ---------------------------------------------------------------------------
# Answer builders
# ---------------------------------------------------------------------------


def _artifacts(snap: _ProjectSnapshot) -> tuple[str, ...]:
    paths: list[str] = []
    if snap.claims_path is not None:
        paths.append(f"state/claims/{snap.project_id}.json")
    if snap.current_path is not None:
        paths.append(f"state/current-state/{snap.project_id}.json")
    if snap.authoritative_path is not None:
        paths.append(f"state/authoritative-state/{snap.project_id}.json")
    return tuple(paths)


def _project_claim(snap: _ProjectSnapshot, claim_id: str | None) -> ClaimProjection | None:
    if claim_id is None:
        return None
    claim = snap.claims_by_id.get(claim_id)
    if claim is None:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.PROVENANCE_MISMATCH,
            f"claim_id {claim_id!r} absent from persisted claims",
        )
    source_id: str | None = None
    resource: str | None = None
    sha256: str | None = None
    source_lineage_id = claim.source_lineage_id
    if claim.provenance:
        first = claim.provenance[0]
        source_id = first.source_id
        resource = first.resource
        sha256 = first.sha256
        if first.source_lineage_id:
            source_lineage_id = first.source_lineage_id
    return ClaimProjection(
        claim_id=claim.claim_id,
        value=claim.value,
        source_id=source_id,
        source_lineage_id=source_lineage_id,
        resource=resource,
        sha256=sha256,
    )


def _temporal_fields(
    snap: _ProjectSnapshot, subject: str, field: str
) -> tuple[CurrentStateRecord | None, AnswerStatus | None]:
    record = snap.current_by_key.get((subject, field))
    if record is None:
        if snap.current_path is None:
            return None, AnswerStatus.TEMPORAL_STATE_MISSING
        return None, AnswerStatus.NOT_FOUND
    return record, None


def _answer_temporal(
    snap: _ProjectSnapshot, subject: str, field: str
) -> KnowledgeAnswer:
    if snap.current_path is None:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING,
            f"missing current-state for project {snap.project_id}",
        )
    record, missing = _temporal_fields(snap, subject, field)
    if record is None:
        status = missing or AnswerStatus.NOT_FOUND
        return KnowledgeAnswer(
            status=status,
            kind=QueryKind.TEMPORAL,
            project_id=snap.project_id,
            subject=subject,
            field=field,
            compilation_id=snap.compilation_id,
            reason_code=status.value,
            inspected_artifacts=_artifacts(snap),
            notes=("No persisted CurrentStateRecord for subject+field.",),
        )
    claim = (
        _project_claim(snap, record.current_claim_id)
        if record.current_claim_id
        else None
    )
    # Temporal answers never set authoritative value (INV-004 / INV-005)
    return KnowledgeAnswer(
        status=AnswerStatus.OK,
        kind=QueryKind.TEMPORAL,
        project_id=snap.project_id,
        subject=subject,
        field=field,
        compilation_id=snap.compilation_id or record.compilation_id,
        temporal_status=record.temporal_status.value,
        temporal_resolution_basis=record.resolution_basis.value,
        temporal_current_claim_id=record.current_claim_id,
        temporal_historical_claim_ids=tuple(sorted(record.historical_claim_ids)),
        temporal_rationale=record.rationale,
        claim=claim,
        inspected_artifacts=_artifacts(snap),
        reason_code=None,
        notes=(
            "Temporal disposition from state/current-state (AS-CORE-005).",
            "Temporal current is not authoritative (AS-CORE-007-INV-004).",
        ),
    )


def _status_for_disposition(disposition: str) -> AnswerStatus:
    if disposition == "authoritative":
        return AnswerStatus.OK
    if disposition == "authority-pending":
        return AnswerStatus.AUTHORITY_PENDING
    if disposition == "authority-conflict":
        return AnswerStatus.AUTHORITY_CONFLICT
    if disposition == "unresolved":
        return AnswerStatus.UNRESOLVED
    # subordinate is not a subject-level winner; treat as structured non-answer
    if disposition == "subordinate":
        return AnswerStatus.UNRESOLVED
    return AnswerStatus.NOT_FOUND


def _answer_authoritative(
    snap: _ProjectSnapshot, subject: str, field: str
) -> KnowledgeAnswer:
    if snap.authoritative_path is None:
        raise KnowledgeQueryError(
            KnowledgeQueryErrorCode.STATE_MISSING,
            f"missing authoritative-state for project {snap.project_id}",
        )

    temporal, temporal_missing = _temporal_fields(snap, subject, field)
    # FR-002: if current-state file exists but record missing while we have auth
    # record, still answer but mark temporal_state_missing in envelope fields.
    auth = snap.authoritative_by_key.get((subject, field))
    if auth is None:
        return KnowledgeAnswer(
            status=AnswerStatus.NOT_FOUND,
            kind=QueryKind.AUTHORITATIVE,
            project_id=snap.project_id,
            subject=subject,
            field=field,
            compilation_id=snap.compilation_id,
            temporal_status=temporal.temporal_status.value if temporal else None,
            temporal_resolution_basis=(
                temporal.resolution_basis.value if temporal else None
            ),
            temporal_current_claim_id=temporal.current_claim_id if temporal else None,
            temporal_historical_claim_ids=(
                tuple(sorted(temporal.historical_claim_ids)) if temporal else ()
            ),
            temporal_rationale=temporal.rationale if temporal else None,
            reason_code=AnswerStatus.NOT_FOUND.value,
            inspected_artifacts=_artifacts(snap),
            notes=(
                "No persisted AuthoritativeStateRecord for subject+field.",
                "No authoritative value invented (AS-CORE-007-INV-005).",
            ),
        )

    disposition = auth.disposition.value
    status = _status_for_disposition(disposition)
    value: str | None = None
    claim_id: str | None = None
    claim_proj: ClaimProjection | None = None

    if disposition == "authoritative":
        if not auth.authoritative_claim_id or auth.authoritative_value is None:
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.PROVENANCE_MISMATCH,
                "authoritative disposition lacks claim_id or value in persisted state",
            )
        claim_proj = _project_claim(snap, auth.authoritative_claim_id)
        assert claim_proj is not None
        if claim_proj.value != auth.authoritative_value:
            raise KnowledgeQueryError(
                KnowledgeQueryErrorCode.VALUE_MISMATCH,
                "persisted authoritative_value does not match claim.value",
            )
        value = auth.authoritative_value
        claim_id = auth.authoritative_claim_id
        status = AnswerStatus.OK
    else:
        # FR-004: never emit value for pending/conflict/unresolved
        value = None
        claim_id = None
        # Still project selected claim if present for inspection? Contract: retain
        # claim ids in competing/subordinate lists; optional claim projection for
        # authoritative_claim_id only when disposition authoritative.
        claim_proj = None

    notes = [
        "Authority disposition from state/authoritative-state (AS-CORE-006).",
        "No authority recomputation performed (AS-CORE-007-INV-002).",
    ]
    if temporal is None:
        notes.append(
            f"Temporal context: {temporal_missing.value if temporal_missing else 'absent'}."
        )
    else:
        notes.append("Temporal context attached separately (AS-CORE-007-INV-004).")

    evidence = tuple(
        sorted(
            (item.model_dump(mode="json") for item in auth.evidence),
            key=lambda d: (
                str(d.get("rule_id", "")),
                str(d.get("claim_id", "")),
                str(d.get("source_id", "")),
            ),
        )
    )

    return KnowledgeAnswer(
        status=status,
        kind=QueryKind.AUTHORITATIVE,
        project_id=snap.project_id,
        subject=subject,
        field=field,
        compilation_id=snap.compilation_id or auth.compilation_id,
        temporal_status=temporal.temporal_status.value if temporal else None,
        temporal_resolution_basis=temporal.resolution_basis.value if temporal else None,
        temporal_current_claim_id=temporal.current_claim_id if temporal else None,
        temporal_historical_claim_ids=(
            tuple(sorted(temporal.historical_claim_ids)) if temporal else ()
        ),
        temporal_rationale=temporal.rationale if temporal else None,
        authority_disposition=disposition,
        authority_domain=auth.authority_domain.value,
        rule_id=auth.rule_id,
        registry_version=auth.registry_version,
        trust_root=auth.trust_root,
        authoritative_role=auth.authoritative_role.value if auth.authoritative_role else None,
        value=value,
        claim_id=claim_id,
        competing_claim_ids=tuple(sorted(auth.competing_claim_ids)),
        subordinate_claim_ids=tuple(sorted(auth.subordinate_claim_ids)),
        temporally_ineligible_claim_ids=tuple(sorted(auth.temporally_ineligible_claim_ids)),
        authority_rationale=auth.rationale,
        claim=claim_proj,
        evidence=evidence,
        inspected_artifacts=_artifacts(snap),
        reason_code=None if status is AnswerStatus.OK else status.value,
        notes=tuple(notes),
    )


def _answer_explain(
    snap: _ProjectSnapshot, subject: str, field: str
) -> KnowledgeAnswer:
    """Combined envelope from persisted rationales only (FR-012)."""
    # Prefer authoritative path; if only temporal exists, return temporal explain.
    if snap.authoritative_path is not None:
        auth_answer = _answer_authoritative(snap, subject, field)
        notes = (
            *auth_answer.notes,
            "Explain mode concatenates persisted rationales only (no inference).",
        )
        if auth_answer.temporal_rationale and auth_answer.authority_rationale:
            notes = (
                *notes,
                "Layers: temporal_rationale + authority_rationale from persisted state.",
            )
        return auth_answer.model_copy(
            update={
                "kind": QueryKind.EXPLAIN,
                "notes": notes,
            }
        )
    if snap.current_path is not None:
        temporal_answer = _answer_temporal(snap, subject, field)
        return temporal_answer.model_copy(
            update={
                "kind": QueryKind.EXPLAIN,
                "notes": (
                    *temporal_answer.notes,
                    "Explain mode: authoritative-state absent; temporal layer only.",
                    "No inferred authoritative value.",
                ),
            }
        )
    raise KnowledgeQueryError(
        KnowledgeQueryErrorCode.STATE_MISSING,
        "neither current-state nor authoritative-state is present for explain",
    )
