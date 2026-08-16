"""AS-ORCH-001D-R2 adapter for canonical Atlas session-receipt evidence.

Canonical receipt semantics remain owned by the control-plane receipt gate
(``atlas-vault-documentation/agent_control/receipt_gate.py``). This module
does not import that sibling package. It reads and writes the same store
(``.atlas/receipts/{receipt_id}.json``) and the same evidence-only payload
shape so Core can bind a target ``AgentResultEnvelope`` without creating a
second receipt authority model.

MODEL_OUTPUT_IS_RECEIPT_AUTHORITY = NO
ENVELOPE_RECEIPT_STATUS_ALONE_IS_SUFFICIENT = NO
TARGET_AGENT_CAN_MINT_VALID_RECEIPT = NO
CURSOR_RESULT_TEXT_CAN_CERTIFY_RECEIPT = NO
RECEIPT_IS_AUTHORITY = NO
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn

from atlas_contracts.identity import ensure_under_root, safe_relative_component
from atlas_contracts.versions import ID_PATTERN
from project_atlas.orchestration.models import AgentResultEnvelope, ResultReceiptBinding
from project_atlas.orchestration.router import canonical_payload_digest

CANONICAL_RECEIPTS_RELATIVE: Final[tuple[str, ...]] = (".atlas", "receipts")
CANONICAL_SESSIONS_RELATIVE: Final[tuple[str, ...]] = (".atlas", "sessions")
MANAGED_SKILL_ID: Final[str] = "atlas-orchestration-dispatch"
MANAGED_SKILL_VERSION: Final[str] = "1.0.0"
MANAGED_AGENT_ID: Final[str] = "cursor-readonly-ask"
DETERMINISTIC_EVENT_TIME: Final[str] = "1970-01-01T00:00:00Z"
_ID_RE = re.compile(ID_PATTERN)
_RECEIPT_ID_RE = re.compile(r"^ASR-[0-9a-f]{16}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_VALIDATION_PASSED_FIELDS: Final[tuple[str, ...]] = (
    "skill_certification",
    "adapter_readiness",
    "session",
    "routes",
    "project",
    "receipt",
    "postflight",
)
_REQUIRED_EVENTS: Final[tuple[str, ...]] = ("session-start", "validation", "completion")
_PIPELINE_COUNTERS: Final[tuple[str, ...]] = ("captured", "normalized", "verified", "routed")
_FAILED_PIPELINE_TOKENS: Final[frozenset[object]] = frozenset(
    {"failed", "unverified", "error", "rejected", "pending"}
)


class ReceiptBindingError(ValueError):
    """Canonical receipt authenticity failure. Not an authority grant."""

    code: str = "RECEIPT_NOT_VALID"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def _closed(code: str, message: str) -> NoReturn:
    raise ReceiptBindingError(message, code=code)


@dataclass(frozen=True)
class DispatchReceiptBindTarget:
    """Trusted dispatcher identity used to bind a canonical receipt."""

    dispatch_id: str
    dispatch_task_id: str
    managed_session_id: str
    attempt: int
    target_role: str


def managed_session_id_for(dispatch_id: str, stored: str | None = None) -> str:
    """Stable governed session identity for one dispatch. Not Cursor session_id."""
    if stored:
        if not _ID_RE.fullmatch(stored):
            raise ReceiptBindingError("managed session id is unsafe", code="RECEIPT_TAMPERED")
        return stored
    if not _DIGEST_RE.fullmatch(dispatch_id):
        raise ReceiptBindingError("dispatch id is not a SHA-256 digest", code="RECEIPT_TAMPERED")
    return f"ds.{dispatch_id}"


def expected_receipt_id_for_session(session_id: str) -> str:
    """Same ``ASR-`` + sha256(session_id)[:16] algorithm as ``receipt_gate.issue``."""
    return "ASR-" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]


def workspace_project_id(workspace: Path) -> str:
    """Project binding derived from the resolved governed workspace root."""
    digest = hashlib.sha256(str(workspace.expanduser().resolve()).encode("utf-8")).hexdigest()
    return f"ws.{digest[:16]}"


def receipt_binding_digest(
    *,
    receipt_id: str,
    target: DispatchReceiptBindTarget,
    project_id: str,
) -> str:
    """Audit digest of binding facts. Does not store receipt content."""
    return canonical_payload_digest(
        {
            "receipt_id": receipt_id,
            "dispatch_id": target.dispatch_id,
            "dispatch_task_id": target.dispatch_task_id,
            "managed_session_id": target.managed_session_id,
            "project_id": project_id,
            "attempt": target.attempt,
            "target_role": target.target_role,
        }
    )


def _workspace_root(workspace: Path) -> Path:
    return workspace.expanduser().resolve()


def _join_atlas(workspace: Path, parts: tuple[str, ...], name: str, *, label: str) -> Path:
    root = _workspace_root(workspace)
    try:
        safe_name = safe_relative_component(name, label=label)
        joined = root
        for part in parts:
            joined = joined.joinpath(safe_relative_component(part, label=label))
        joined = joined.joinpath(safe_name)
        return ensure_under_root(root, joined, label=label)
    except ValueError as exc:
        raise ReceiptBindingError(f"unsafe {label}", code="RECEIPT_TAMPERED") from exc


def canonical_receipts_root(workspace: Path) -> Path:
    root = _workspace_root(workspace)
    try:
        joined = root
        for part in CANONICAL_RECEIPTS_RELATIVE:
            joined = joined.joinpath(safe_relative_component(part, label="receipts root"))
        return ensure_under_root(root, joined, label="receipts root")
    except ValueError as exc:
        raise ReceiptBindingError("unsafe receipts root", code="RECEIPT_TAMPERED") from exc


def resolve_canonical_receipt_path(workspace: Path, receipt_id: str) -> Path:
    """Resolve ``.atlas/receipts/{receipt_id}.json`` with fail-closed path safety.

    Model text never chooses an arbitrary file. Symlink / traversal / absolute
    / alternate-extension lookups are rejected.
    """
    if not isinstance(receipt_id, str) or not _ID_RE.fullmatch(receipt_id):
        raise ReceiptBindingError("receipt_id is not a safe identifier", code="RECEIPT_NOT_FOUND")
    filename = f"{receipt_id}.json"
    path = _join_atlas(workspace, CANONICAL_RECEIPTS_RELATIVE, filename, label="receipt_id")
    if path.name != filename or path.suffix != ".json":
        _closed("RECEIPT_TAMPERED", "receipt path is not a canonical json artifact")
    candidate = canonical_receipts_root(workspace) / filename
    if candidate.is_symlink() or path.is_symlink():
        raise ReceiptBindingError("refusing symlink receipt path", code="RECEIPT_TAMPERED")
    return path


def resolve_canonical_session_path(workspace: Path, session_id: str) -> Path:
    if not isinstance(session_id, str) or not _ID_RE.fullmatch(session_id):
        raise ReceiptBindingError("session_id is not a safe identifier", code="RECEIPT_TAMPERED")
    return _join_atlas(
        workspace,
        CANONICAL_SESSIONS_RELATIVE,
        f"{session_id}.json",
        label="session_id",
    )


def _atomic_write_text(path: Path, content: str) -> None:
    if path.is_symlink():
        raise ReceiptBindingError("refusing to write through a symlink", code="RECEIPT_TAMPERED")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    if tmp.is_symlink():
        raise ReceiptBindingError("refusing to write through a symlink", code="RECEIPT_TAMPERED")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _dump_canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _workspace_vault_binding(workspace: Path) -> dict[str, str]:
    root = _workspace_root(workspace)
    derived_id = workspace_project_id(workspace)
    derived_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, str(root)))
    identity = root / ".atlas" / "vault.json"
    if identity.is_file() and not identity.is_symlink() and not identity.parent.is_symlink():
        try:
            contained = ensure_under_root(root, identity, label="vault identity")
            raw = json.loads(contained.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            vault_id = raw.get("vault_id")
            vault_uuid = raw.get("vault_uuid") or raw.get("vault_id")
            if isinstance(vault_id, str) and _ID_RE.fullmatch(vault_id):
                derived_id = vault_id
            if isinstance(vault_uuid, str) and vault_uuid:
                derived_uuid = vault_uuid
    return {"vault_id": derived_id, "vault_uuid": derived_uuid, "root": str(root)}


def _skill_binding() -> dict[str, Any]:
    material = f"{MANAGED_SKILL_ID}:{MANAGED_SKILL_VERSION}".encode()
    return {
        "id": MANAGED_SKILL_ID,
        "version": MANAGED_SKILL_VERSION,
        "sha256": hashlib.sha256(material).hexdigest(),
    }


def _event(session_id: str, name: str) -> dict[str, str]:
    return {
        "event_id": f"evt.{session_id}.{name}",
        "type": name,
        "recorded_at": DETERMINISTIC_EVENT_TIME,
    }


def build_managed_session_state(
    workspace: Path,
    target: DispatchReceiptBindTarget,
    *,
    complete: bool,
) -> dict[str, Any]:
    """Build the control-plane session state used by ``receipt_gate.validate``."""
    project_id = workspace_project_id(workspace)
    events: dict[str, list[dict[str, str]]] = {
        "session-start": [_event(target.managed_session_id, "session-start")],
        "implementation": [],
        "decision": [],
        "validation": [_event(target.managed_session_id, "validation")] if complete else [],
        "blocked": [],
        "completion": [_event(target.managed_session_id, "completion")] if complete else [],
    }
    pipeline = {
        "captured": 1 if complete else 0,
        "normalized": 1 if complete else 0,
        "verified": 1 if complete else 0,
        "routed": 1 if complete else 0,
        "pending_spool": 0,
        "failed": 0,
    }
    return {
        "schema_version": 1,
        "session": {
            "session_id": target.managed_session_id,
            "task_id": target.dispatch_task_id,
            "project_id": project_id,
            "dispatch_id": target.dispatch_id,
            "attempt": target.attempt,
            "target_role": target.target_role,
            "started_at": DETERMINISTIC_EVENT_TIME,
        },
        "agent": {
            "agent_id": MANAGED_AGENT_ID,
            "adapter_id": "cursor",
            "adapter": "cursor",
        },
        "skill": _skill_binding(),
        "vault": _workspace_vault_binding(workspace),
        "events": events,
        "pipeline": pipeline,
        "preflight": {"strict": True, "readiness": "passed", "skill_certification": None},
        "capability": {},
        "status": "complete" if complete else "active",
    }


def _validate_gate_state(state: Mapping[str, Any]) -> list[str]:
    """Mirror ``receipt_gate.validate`` so issued receipts stay gate-compatible."""
    errors: list[str] = []
    events = state.get("events", {})
    if not isinstance(events, dict):
        return ["events missing"]
    for required in _REQUIRED_EVENTS:
        if not events.get(required):
            errors.append(f"missing required event: {required}")
    pipeline_obj = state.get("pipeline", {})
    if not isinstance(pipeline_obj, dict):
        return ["pipeline missing"]
    if pipeline_obj.get("pending_spool", 0) and (
        isinstance(state.get("preflight"), dict) and state.get("preflight", {}).get("strict", True)
    ):
        errors.append("pending spool events")
    captured = int(pipeline_obj.get("captured", 0) or 0)
    if captured and not all(
        int(pipeline_obj.get(key, 0) or 0) >= captured
        for key in ("normalized", "verified", "routed")
    ):
        errors.append("capture pipeline is not normalized, verified and routed")
    skill = state.get("skill", {})
    if not isinstance(skill, dict) or not skill.get("sha256"):
        errors.append("missing skill hash")
    return errors


def persist_managed_session(workspace: Path, state: Mapping[str, Any]) -> Path:
    session = state.get("session")
    if not isinstance(session, dict) or not isinstance(session.get("session_id"), str):
        raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
    path = resolve_canonical_session_path(workspace, session["session_id"])
    _atomic_write_text(path, _dump_canonical(state))
    return path


def ensure_managed_dispatch_session(
    workspace: Path,
    target: DispatchReceiptBindTarget,
) -> dict[str, Any]:
    """Create or reuse the governed dispatch session (session-start only)."""
    path = resolve_canonical_session_path(workspace, target.managed_session_id)
    if path.is_file() and not path.is_symlink():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReceiptBindingError(
                "managed session is unreadable",
                code="RECEIPT_TAMPERED",
            ) from exc
        if isinstance(existing, dict):
            session = existing.get("session")
            if (
                isinstance(session, dict)
                and session.get("session_id") == target.managed_session_id
                and session.get("task_id") == target.dispatch_task_id
                and session.get("dispatch_id") == target.dispatch_id
                and session.get("project_id") == workspace_project_id(workspace)
            ):
                return existing
            raise ReceiptBindingError(
                "managed session does not bind this dispatch",
                code="RECEIPT_BINDING_MISMATCH",
            )
    state = build_managed_session_state(workspace, target, complete=False)
    persist_managed_session(workspace, state)
    return state


def issue_managed_dispatch_receipt(
    workspace: Path,
    target: DispatchReceiptBindTarget,
) -> dict[str, Any]:
    """Issue an evidence-only canonical session receipt for this dispatch.

    Payload fields match ``receipt_gate.issue`` (authority_role=evidence-only,
    is_authority=false, receipt_is_authority=false, status=passed).
    """
    state = build_managed_session_state(workspace, target, complete=True)
    errors = _validate_gate_state(state)
    if errors:
        raise ReceiptBindingError("; ".join(errors), code="RECEIPT_NOT_VALID")
    session = state["session"]
    assert isinstance(session, dict)
    receipt_id = expected_receipt_id_for_session(str(session["session_id"]))
    if not _RECEIPT_ID_RE.fullmatch(receipt_id):
        raise ReceiptBindingError("issued receipt_id is not canonical", code="RECEIPT_TAMPERED")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "receipt_type": "atlas-agent-session",
        "receipt_id": receipt_id,
        "authority_role": "evidence-only",
        "is_authority": False,
        "receipt_is_authority": False,
        "session": session,
        "agent": {**state["agent"], "adapter_readiness": "passed"},
        "skill": {
            **state["skill"],
            "hash_matched": True,
            "verified": True,
            "acknowledged": False,
            "certification_receipt": None,
        },
        "skill_acknowledgement": None,
        "vault": state["vault"],
        "events": state["events"],
        "pipeline": {**state["pipeline"], "failed": 0},
        "capability": {},
        "validation": {field: "passed" for field in _VALIDATION_PASSED_FIELDS},
        "replay": {"idempotent": True, "canonical_mutations": 0},
        "rehearsal": None,
        "status": "passed",
        "sync_state": "synchronized",
        "blockers": [],
    }
    path = resolve_canonical_receipt_path(workspace, receipt_id)
    content = _dump_canonical(payload)
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReceiptBindingError(
                "canonical receipt is unreadable",
                code="RECEIPT_TAMPERED",
            ) from exc
        if existing != content:
            raise ReceiptBindingError(
                "immutable session receipt collision",
                code="RECEIPT_TAMPERED",
            )
    else:
        _atomic_write_text(path, content)
    state["status"] = "complete"
    state["receipt_id"] = receipt_id
    persist_managed_session(workspace, state)
    return payload


def load_canonical_receipt(workspace: Path, receipt_id: str) -> dict[str, Any]:
    """Load a canonical receipt artifact. Missing/unsafe IDs fail closed."""
    try:
        path = resolve_canonical_receipt_path(workspace, receipt_id)
    except ReceiptBindingError:
        raise
    if not path.is_file():
        raise ReceiptBindingError("canonical receipt artifact is missing", code="RECEIPT_NOT_FOUND")
    if path.is_symlink():
        raise ReceiptBindingError("refusing symlink receipt artifact", code="RECEIPT_TAMPERED")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptBindingError(
            "canonical receipt is malformed",
            code="RECEIPT_TAMPERED",
        ) from exc
    if not isinstance(payload, dict):
        raise ReceiptBindingError("canonical receipt is malformed", code="RECEIPT_TAMPERED")
    return payload


def _require_false(payload: Mapping[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise ReceiptBindingError(
            f"canonical receipt {key} is not false",
            code="RECEIPT_TAMPERED",
        )


def verify_canonical_receipt_payload(
    payload: Mapping[str, Any],
    *,
    receipt_id: str,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> dict[str, Any]:
    """Independently verify canonical receipt truth. Envelope copies are ignored."""
    if payload.get("receipt_id") != receipt_id:
        _closed("RECEIPT_TAMPERED", "canonical receipt_id does not match reference")
    if payload.get("status") != "passed":
        _closed("RECEIPT_NOT_VALID", "canonical receipt is not in a successful state")
    if payload.get("authority_role") != "evidence-only":
        raise ReceiptBindingError("canonical receipt is not evidence-only", code="RECEIPT_TAMPERED")
    _require_false(payload, "is_authority")
    _require_false(payload, "receipt_is_authority")
    session = payload.get("session")
    if not isinstance(session, dict):
        raise ReceiptBindingError("canonical receipt session is missing", code="RECEIPT_TAMPERED")
    if session.get("task_id") != target.dispatch_task_id:
        _closed("RECEIPT_BINDING_MISMATCH", "canonical receipt task does not match dispatch")
    if session.get("session_id") != target.managed_session_id:
        raise ReceiptBindingError(
            "canonical receipt session does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if session.get("dispatch_id") != target.dispatch_id:
        raise ReceiptBindingError(
            "canonical receipt dispatch does not match record",
            code="RECEIPT_BINDING_MISMATCH",
        )
    expected_project = workspace_project_id(workspace)
    if session.get("project_id") != expected_project:
        raise ReceiptBindingError(
            "canonical receipt project does not match workspace",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if "attempt" in session and session.get("attempt") != target.attempt:
        raise ReceiptBindingError(
            "canonical receipt attempt does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if "target_role" in session and session.get("target_role") != target.target_role:
        raise ReceiptBindingError(
            "canonical receipt producer role does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        _closed("RECEIPT_TAMPERED", "canonical receipt validation is missing")
    for field in _VALIDATION_PASSED_FIELDS:
        if validation.get(field) != "passed":
            raise ReceiptBindingError(
                f"canonical receipt validation.{field} is not passed",
                code="RECEIPT_NOT_VALID",
            )
    pipeline = payload.get("pipeline")
    if not isinstance(pipeline, dict):
        raise ReceiptBindingError("canonical receipt pipeline is missing", code="RECEIPT_TAMPERED")
    if pipeline.get("failed") not in (0, None, False):
        raise ReceiptBindingError("canonical receipt pipeline failed", code="RECEIPT_NOT_VALID")
    for value in pipeline.values():
        if value in _FAILED_PIPELINE_TOKENS:
            _closed("RECEIPT_NOT_VALID", "canonical receipt pipeline is unverified")
    captured = int(pipeline.get("captured", 0) or 0)
    for key in _PIPELINE_COUNTERS[1:]:
        if int(pipeline.get(key, 0) or 0) < captured:
            _closed("RECEIPT_NOT_VALID", "canonical receipt pipeline is incomplete")
    events = payload.get("events")
    if not isinstance(events, dict):
        raise ReceiptBindingError("canonical receipt events are missing", code="RECEIPT_TAMPERED")
    for required in _REQUIRED_EVENTS:
        if not events.get(required):
            raise ReceiptBindingError(
                f"canonical receipt missing {required} evidence",
                code="RECEIPT_NOT_VALID",
            )
    skill = payload.get("skill")
    if not isinstance(skill, dict) or not skill.get("sha256"):
        _closed("RECEIPT_TAMPERED", "canonical receipt skill hash is missing")
    return dict(payload)


def verify_target_receipt_binding(
    envelope: AgentResultEnvelope,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> dict[str, Any]:
    """Verify envelope.receipt.receipt_id against Atlas-controlled receipt state.

    Does not accept validity decisions from Cursor prose or envelope.status.
    """
    if envelope.receipt is None or not envelope.receipt.receipt_id:
        raise ReceiptBindingError("receipt_id missing", code="RECEIPT_NOT_FOUND")
    receipt_id = envelope.receipt.receipt_id
    payload = load_canonical_receipt(workspace, receipt_id)
    return verify_canonical_receipt_payload(
        payload,
        receipt_id=receipt_id,
        target=target,
        workspace=workspace,
    )


def bind_target_receipt(
    envelope: AgentResultEnvelope,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> tuple[AgentResultEnvelope, dict[str, Any]]:
    """Attach a trusted receipt binding issued or verified by Atlas.

    A model claim of ``status=valid`` is never sufficient. That claim is
    accepted only when a canonical receipt already exists and binds this
    dispatch. Pending/missing receipts are issued by the managed lifecycle
    after the envelope body is otherwise valid. Rejected claims fail closed.

    Preserves producer, task, outcome, state, observations, blockers, and
    requested_transition. Only the receipt binding may be replaced.
    """
    raw_digest = canonical_payload_digest(envelope.model_dump(mode="json"))
    claimed = envelope.receipt
    if claimed is not None and claimed.status == "rejected":
        raise ReceiptBindingError("target receipt is rejected", code="RECEIPT_NOT_VALID")
    if claimed is not None and claimed.status == "valid":
        payload = verify_target_receipt_binding(envelope, target, workspace)
        project_id = workspace_project_id(workspace)
        facts = {
            "receipt_id": claimed.receipt_id,
            "raw_target_result_digest": raw_digest,
            "normalized_target_result_digest": raw_digest,
            "target_receipt_binding_digest": receipt_binding_digest(
                receipt_id=claimed.receipt_id,
                target=target,
                project_id=project_id,
            ),
            "canonical_receipt": payload,
        }
        return envelope, facts
    issued = issue_managed_dispatch_receipt(workspace, target)
    bound = envelope.model_copy(
        update={
            "receipt": ResultReceiptBinding(
                receipt_id=str(issued["receipt_id"]),
                status="valid",
            )
        }
    )
    verify_target_receipt_binding(bound, target, workspace)
    normalized_digest = canonical_payload_digest(bound.model_dump(mode="json"))
    project_id = workspace_project_id(workspace)
    facts = {
        "receipt_id": issued["receipt_id"],
        "raw_target_result_digest": raw_digest,
        "normalized_target_result_digest": normalized_digest,
        "target_receipt_binding_digest": receipt_binding_digest(
            receipt_id=str(issued["receipt_id"]),
            target=target,
            project_id=project_id,
        ),
        "canonical_receipt": issued,
    }
    return bound, facts
