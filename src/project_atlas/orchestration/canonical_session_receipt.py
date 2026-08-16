"""AS-ORCH-001D adapter: dispatch ↔ canonical managed-session lifecycle.

Cursor CLI dispatch binds ``agent_type=cli`` / ``generic-cli-v1``.
Readiness is owned by canonical preflight. No readiness override.

Lifecycle truth is owned by the control plane:

    preflight / bootstrap.start
        → event_client.document(session-start | validation | completion)
        → postflight.run → receipt_gate.validate → receipt_gate.issue

This module maps dispatch identity onto that path and verifies binding facts.
It does not construct session-start/validation/completion events, does not
assign pipeline counters, and does not issue receipts.

MODEL_OUTPUT_IS_RECEIPT_AUTHORITY = NO
ENVELOPE_RECEIPT_STATUS_ALONE_IS_SUFFICIENT = NO
TARGET_AGENT_CAN_MINT_VALID_RECEIPT = NO
TARGET_RECEIPT_CANNOT_SKIP_POSTFLIGHT = YES
DISPATCHER_CAN_SELF_ASSERT_LIFECYCLE_VALIDITY = NO
CANONICAL_RECEIPT_IS_AUTHORITY = NO
FAKE_EVENT_TIMESTAMP = NONE
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn

import yaml

from atlas_contracts.identity import ensure_under_root, safe_relative_component
from atlas_contracts.versions import ID_PATTERN
from project_atlas.agent_control import receipt_gate, session
from project_atlas.agent_control.postflight import run as canonical_postflight_run
from project_atlas.agent_control.runtime import (
    ControlPlaneError,
    bootstrap_start,
    document_event,
    documentation_skill_root,
    prepare_event_pipeline,
    run_preflight,
)
from project_atlas.orchestration.models import AgentResultEnvelope, ResultReceiptBinding
from project_atlas.orchestration.router import canonical_payload_digest

CANONICAL_RECEIPTS_RELATIVE: Final[tuple[str, ...]] = (".atlas", "receipts")
CANONICAL_SESSIONS_RELATIVE: Final[tuple[str, ...]] = (".atlas", "sessions")
MANAGED_AGENT_TRANSPORT: Final[str] = "CURSOR_CLI"
MANAGED_AGENT_ID: Final[str] = "cursor-agent-cli"
MANAGED_AGENT_TYPE: Final[str] = "cli"
CANONICAL_ADAPTER_ID: Final[str] = "generic-cli-v1"
MANAGED_WORK_PACKAGE: Final[str] = "as-orch-001d"
_ID_RE = re.compile(ID_PATTERN)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class ReceiptBindingError(ValueError):
    """Canonical receipt authenticity failure. Not an authority grant."""

    code: str = "RECEIPT_NOT_VALID"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def _closed(code: str, message: str) -> NoReturn:
    raise ReceiptBindingError(message, code=code)


def _from_control_plane(exc: Exception) -> ReceiptBindingError:
    code = getattr(exc, "code", None)
    if isinstance(exc, ControlPlaneError) and isinstance(code, str):
        return ReceiptBindingError(str(exc), code=code)
    text = str(exc).lower()
    if any(
        token in text
        for token in (
            "normalization failed",
            "routing failed",
            "invalid-raw-event",
            "likely secret",
        )
    ):
        return ReceiptBindingError(str(exc), code="PIPELINE_FAILED")
    if "capture failed" in text:
        return ReceiptBindingError(str(exc), code="VALIDATION_EVENT_FAILED")
    if isinstance(exc, ValueError):
        return ReceiptBindingError(str(exc), code="PREFLIGHT_FAILED")
    return ReceiptBindingError(str(exc), code="CONTROL_PLANE_UNAVAILABLE")


@dataclass(frozen=True)
class DispatchReceiptBindTarget:
    """Trusted dispatcher identity used to bind a canonical receipt."""

    dispatch_id: str
    dispatch_task_id: str
    managed_session_id: str
    attempt: int
    target_role: str


def require_managed_session_id(stored: str | None) -> str:
    """Return the real control-plane session id. Does not invent one."""
    if not stored:
        raise ReceiptBindingError(
            "managed session has not been started",
            code="SESSION_NOT_STARTED",
        )
    if not _ID_RE.fullmatch(stored):
        raise ReceiptBindingError("managed session id is unsafe", code="RECEIPT_TAMPERED")
    return stored


def expected_receipt_id_for_session(session_id: str) -> str:
    """Lookup helper matching ``receipt_gate.issue`` receipt_id algorithm."""
    return "ASR-" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]


def workspace_project_id(workspace: Path) -> str:
    """Project id declared in ``.atlas/project.yaml``. Not a derived digest."""
    path = workspace.expanduser().resolve() / ".atlas" / "project.yaml"
    if not path.is_file() or path.is_symlink():
        raise ReceiptBindingError(
            "project Atlas configuration is missing",
            code="PREFLIGHT_FAILED",
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ReceiptBindingError(
            "project Atlas configuration is unreadable",
            code="PREFLIGHT_FAILED",
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("project"), dict):
        raise ReceiptBindingError("invalid .atlas/project.yaml", code="PREFLIGHT_FAILED")
    project_id = data["project"].get("id")
    if not isinstance(project_id, str) or not project_id:
        raise ReceiptBindingError("project id is missing", code="PREFLIGHT_FAILED")
    return project_id


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
    """Resolve ``.atlas/receipts/{receipt_id}.json`` with fail-closed path safety."""
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


def load_canonical_receipt(workspace: Path, receipt_id: str) -> dict[str, Any]:
    """Load a canonical receipt artifact. Missing/unsafe IDs fail closed."""
    path = resolve_canonical_receipt_path(workspace, receipt_id)
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


def load_managed_session(workspace: Path, session_id: str) -> dict[str, Any]:
    try:
        return session.load(_workspace_root(workspace), session_id)
    except ValueError as exc:
        raise ReceiptBindingError(str(exc), code="SESSION_NOT_STARTED") from exc


def _require_false(payload: Mapping[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise ReceiptBindingError(
            f"canonical receipt {key} is not false",
            code="RECEIPT_TAMPERED",
        )


def _session_binding_matches(
    session_obj: Mapping[str, Any],
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> None:
    if session_obj.get("task_id") != target.dispatch_task_id:
        _closed("RECEIPT_BINDING_MISMATCH", "canonical session task does not match dispatch")
    if session_obj.get("session_id") != target.managed_session_id:
        raise ReceiptBindingError(
            "canonical session id does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if session_obj.get("dispatch_id") != target.dispatch_id:
        raise ReceiptBindingError(
            "canonical session dispatch does not match record",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if session_obj.get("project_id") != workspace_project_id(workspace):
        raise ReceiptBindingError(
            "canonical session project does not match workspace",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if "attempt" in session_obj and session_obj.get("attempt") != target.attempt:
        raise ReceiptBindingError(
            "canonical session attempt does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )
    if "target_role" in session_obj and session_obj.get("target_role") != target.target_role:
        raise ReceiptBindingError(
            "canonical session producer role does not match dispatch",
            code="RECEIPT_BINDING_MISMATCH",
        )


def _bind_dispatch_metadata(
    state: dict[str, Any],
    *,
    dispatch_id: str,
    dispatch_task_id: str,
    attempt: int,
    target_role: str,
) -> dict[str, Any]:
    current = state.get("session")
    if not isinstance(current, dict):
        raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
    updated = dict(current)
    updated["task_id"] = dispatch_task_id
    updated["dispatch_id"] = dispatch_id
    updated["attempt"] = attempt
    updated["target_role"] = target_role
    state["session"] = updated
    return state


def start_managed_dispatch_session(
    workspace: Path,
    *,
    dispatch_id: str,
    dispatch_task_id: str,
    attempt: int,
    target_role: str,
) -> dict[str, Any]:
    """Start a real managed session through canonical preflight + bootstrap."""
    if not _DIGEST_RE.fullmatch(dispatch_id):
        raise ReceiptBindingError("dispatch id is not a SHA-256 digest", code="RECEIPT_TAMPERED")
    root = _workspace_root(workspace)
    try:
        prepare_event_pipeline()
        skill_root = documentation_skill_root()
        preflight = run_preflight(
            project_root=root,
            vault_root=root,
            agent_type=MANAGED_AGENT_TYPE,
            agent_value=MANAGED_AGENT_ID,
            skill_root=skill_root,
        )
        if preflight.get("ok") is not True:
            raise ReceiptBindingError("canonical preflight did not pass", code="PREFLIGHT_FAILED")
        state, _environment = bootstrap_start(
            project_root=root,
            vault_root=root,
            agent_type=MANAGED_AGENT_TYPE,
            agent_value=MANAGED_AGENT_ID,
            task_id=MANAGED_WORK_PACKAGE,
            skill_root=skill_root,
        )
    except ReceiptBindingError:
        raise
    except Exception as exc:
        raise _from_control_plane(exc) from exc
    events = state.get("events", {})
    if not isinstance(events, dict) or not events.get("session-start"):
        raise ReceiptBindingError(
            "session-start was not recorded by the control plane",
            code="SESSION_START_FAILED",
        )
    bound = _bind_dispatch_metadata(
        state,
        dispatch_id=dispatch_id,
        dispatch_task_id=dispatch_task_id,
        attempt=attempt,
        target_role=target_role,
    )
    session.save(root, bound)
    return session.load(root, str(bound["session"]["session_id"]))


def ensure_managed_dispatch_session(
    workspace: Path,
    *,
    dispatch_id: str,
    dispatch_task_id: str,
    attempt: int,
    target_role: str,
    stored_session_id: str | None = None,
) -> dict[str, Any]:
    """Reuse a real session or start one. Never fabricates lifecycle events."""
    if stored_session_id:
        state = load_managed_session(workspace, stored_session_id)
        session_obj = state.get("session")
        if not isinstance(session_obj, dict):
            raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
        target = DispatchReceiptBindTarget(
            dispatch_id=dispatch_id,
            dispatch_task_id=dispatch_task_id,
            managed_session_id=stored_session_id,
            attempt=attempt,
            target_role=target_role,
        )
        _session_binding_matches(session_obj, target, workspace)
        return state
    return start_managed_dispatch_session(
        workspace,
        dispatch_id=dispatch_id,
        dispatch_task_id=dispatch_task_id,
        attempt=attempt,
        target_role=target_role,
    )


def record_validation_event(
    workspace: Path,
    target: DispatchReceiptBindTarget,
    *,
    notes: list[str],
) -> dict[str, Any]:
    """Record a validation event only after raw target-result validation."""
    state = load_managed_session(workspace, target.managed_session_id)
    session_obj = state.get("session")
    if not isinstance(session_obj, dict):
        raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
    _session_binding_matches(session_obj, target, workspace)
    try:
        prepare_event_pipeline()
        return document_event(
            vault_root=_workspace_root(workspace),
            session_id=target.managed_session_id,
            event_type="validation",
            summary="Dispatched target result passed schema and dispatch binding validation",
            work_package=MANAGED_WORK_PACKAGE,
            validation=notes,
        )
    except ReceiptBindingError:
        raise
    except Exception as exc:
        raise _from_control_plane(exc) from exc


def record_completion_event(
    workspace: Path,
    target: DispatchReceiptBindTarget,
) -> dict[str, Any]:
    """Record completion only after process + validation + pipeline success."""
    state = load_managed_session(workspace, target.managed_session_id)
    session_obj = state.get("session")
    if not isinstance(session_obj, dict):
        raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
    _session_binding_matches(session_obj, target, workspace)
    events = state.get("events", {})
    if not isinstance(events, dict) or not events.get("validation"):
        raise ReceiptBindingError(
            "completion requires a recorded validation event",
            code="LIFECYCLE_INCOMPLETE",
        )
    if events.get("completion"):
        return {"event_id": events["completion"][-1], "reused": True}
    try:
        prepare_event_pipeline()
        return document_event(
            vault_root=_workspace_root(workspace),
            session_id=target.managed_session_id,
            event_type="completion",
            summary="Dispatched target process completed after validated raw evidence",
            work_package=MANAGED_WORK_PACKAGE,
        )
    except ReceiptBindingError:
        raise
    except Exception as exc:
        raise _from_control_plane(exc) from exc


def run_managed_postflight(
    workspace: Path,
    target: DispatchReceiptBindTarget,
) -> dict[str, Any]:
    """Call the canonical postflight (validate + issue). Does not write receipts."""
    state = load_managed_session(workspace, target.managed_session_id)
    session_obj = state.get("session")
    if not isinstance(session_obj, dict):
        raise ReceiptBindingError("managed session is malformed", code="RECEIPT_TAMPERED")
    _session_binding_matches(session_obj, target, workspace)
    try:
        result = canonical_postflight_run(_workspace_root(workspace), target.managed_session_id)
    except ValueError as exc:
        raise ReceiptBindingError(str(exc), code="POSTFLIGHT_FAILED") from exc
    if not result.get("ok"):
        errors = result.get("errors") or ["canonical postflight rejected the session"]
        if isinstance(errors, list):
            joined = "; ".join(str(item) for item in errors)
        else:
            joined = str(errors)
        raise ReceiptBindingError(joined, code="POSTFLIGHT_FAILED")
    receipt = result.get("receipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("receipt_id"), str):
        raise ReceiptBindingError(
            "canonical postflight did not issue a receipt",
            code="POSTFLIGHT_FAILED",
        )
    return receipt


def lifecycle_is_complete(workspace: Path, target: DispatchReceiptBindTarget) -> bool:
    """Inspect real session + issued receipt. Does not synthesize missing facts."""
    try:
        state = load_managed_session(workspace, target.managed_session_id)
    except ReceiptBindingError:
        return False
    if receipt_gate.validate(state):
        return False
    receipt_id = state.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        return False
    try:
        payload = load_canonical_receipt(workspace, receipt_id)
        verify_canonical_receipt_payload(
            payload,
            receipt_id=receipt_id,
            target=target,
            workspace=workspace,
        )
    except ReceiptBindingError:
        return False
    return True


def verify_canonical_receipt_payload(
    payload: Mapping[str, Any],
    *,
    receipt_id: str,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> dict[str, Any]:
    """Verify issued-receipt binding. Gate rules stay in ``receipt_gate.validate``."""
    if payload.get("receipt_id") != receipt_id:
        _closed("RECEIPT_TAMPERED", "canonical receipt_id does not match reference")
    if payload.get("status") != "passed":
        _closed("RECEIPT_NOT_VALID", "canonical receipt is not in a successful state")
    if payload.get("authority_role") != "evidence-only":
        raise ReceiptBindingError("canonical receipt is not evidence-only", code="RECEIPT_TAMPERED")
    _require_false(payload, "is_authority")
    _require_false(payload, "receipt_is_authority")
    session_obj = payload.get("session")
    if not isinstance(session_obj, dict):
        raise ReceiptBindingError("canonical receipt session is missing", code="RECEIPT_TAMPERED")
    _session_binding_matches(session_obj, target, workspace)
    state = load_managed_session(workspace, target.managed_session_id)
    errors = receipt_gate.validate(state)
    if errors:
        raise ReceiptBindingError("; ".join(errors), code="RECEIPT_NOT_VALID")
    if state.get("receipt_id") != receipt_id:
        raise ReceiptBindingError(
            "session receipt_id does not match artifact",
            code="RECEIPT_BINDING_MISMATCH",
        )
    return dict(payload)


def verify_target_receipt_binding(
    envelope: AgentResultEnvelope,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> dict[str, Any]:
    """Verify envelope.receipt.receipt_id against Atlas-issued receipt state."""
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


def normalize_envelope_receipt(
    envelope: AgentResultEnvelope,
    target: DispatchReceiptBindTarget,
    workspace: Path,
    issued: Mapping[str, Any],
) -> tuple[AgentResultEnvelope, dict[str, Any]]:
    """Replace only the receipt binding after canonical postflight."""
    raw_digest = canonical_payload_digest(envelope.model_dump(mode="json"))
    receipt_id = str(issued["receipt_id"])
    bound = envelope.model_copy(
        update={
            "receipt": ResultReceiptBinding(
                receipt_id=receipt_id,
                status="valid",
            )
        }
    )
    verify_target_receipt_binding(bound, target, workspace)
    normalized_digest = canonical_payload_digest(bound.model_dump(mode="json"))
    project_id = workspace_project_id(workspace)
    facts = {
        "receipt_id": receipt_id,
        "raw_target_result_digest": raw_digest,
        "normalized_target_result_digest": normalized_digest,
        "target_receipt_binding_digest": receipt_binding_digest(
            receipt_id=receipt_id,
            target=target,
            project_id=project_id,
        ),
        "canonical_receipt": dict(issued),
    }
    return bound, facts


def accept_raw_target_result(
    envelope: AgentResultEnvelope,
    target: DispatchReceiptBindTarget,
    workspace: Path,
) -> tuple[AgentResultEnvelope, dict[str, Any]]:
    """Treat the model receipt as provisional. Do not issue or skip postflight.

    Policy B: ``status=valid`` is non-authoritative input. Canonical postflight
    later replaces only the receipt binding.
    """
    if envelope.receipt is not None and envelope.receipt.status == "rejected":
        raise ReceiptBindingError("target receipt is rejected", code="RECEIPT_NOT_VALID")
    raw_digest = canonical_payload_digest(envelope.model_dump(mode="json"))
    already = load_managed_session(workspace, target.managed_session_id)
    events = already.get("events", {})
    if not isinstance(events, dict) or not events.get("validation"):
        record_validation_event(
            workspace,
            target,
            notes=[
                "schema",
                "producer-role",
                "dispatch-task-id",
                "attempt",
                "dispatch-binding",
            ],
        )
    facts = {
        "receipt_id": None,
        "raw_target_result_digest": raw_digest,
        "normalized_target_result_digest": None,
        "target_receipt_binding_digest": None,
        "canonical_receipt": None,
    }
    return envelope, facts
