"""AS-ORCH-001D governed single-hop agent dispatcher.

HANDOFF → AGENT → RESULT → NEXT_HANDOFF → STOP

One process may be started for one dispatchable task route. The next
HandoffPacket is never auto-dispatched. Privileges remain false.
PROCESS_DISPATCH != PRIVILEGED EXECUTION AUTHORITY.

SINGLE_HOP_AGENT_DISPATCHER = IMPLEMENTED
AUTONOMOUS_LOOP = NOT_IMPLEMENTED
MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED
DISPATCHER_CAN_REROUTE = NO
DISPATCH_RECEIPT_IS_AUTHORITY = NO
CURSOR_STOP_EVENT_REQUIRED_FOR_DISPATCH = NO
MODEL_CAN_SELF_ASSERT_RECEIPT_VALIDITY = NO
ENVELOPE_RECEIPT_STATUS_ALONE_IS_SUFFICIENT = NO
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, NoReturn, TextIO

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from atlas_contracts.versions import ID_PATTERN
from project_atlas.orchestration.agent_transport import (
    DEFAULT_TIMEOUT_SECONDS,
    CursorOutputKind,
    LauncherKind,
    ProcessRunner,
    ProcessRunOutcome,
    ProcessRunRequest,
    ResolvedCursorExecutable,
    SubprocessProcessRunner,
    TransportError,
    build_launch_plan,
    digest_bytes,
    extract_result_payload,
    parse_structured_cursor_output,
    resolve_cursor_transport,
    sanitize_inherited_env,
)
from project_atlas.orchestration.canonical_session_receipt import (
    DispatchReceiptBindTarget,
    ReceiptBindingError,
    bind_target_receipt,
    ensure_managed_dispatch_session,
    managed_session_id_for,
    verify_target_receipt_binding,
)
from project_atlas.orchestration.cursor_bridge import (
    BridgeStatus,
    CursorBridgeError,
    HandoffPacket,
    HandoffState,
    StagedStateTampered,
    acknowledge,
    complete_staged_handoff,
    require_verified_state,
    resolve_repo_root,
    stage_result,
)
from project_atlas.orchestration.models import (
    AgentResultEnvelope,
    ProducerRole,
    RouteKind,
    TargetKind,
    TaskType,
)
from project_atlas.orchestration.router import canonical_payload_digest, source_result_digest
from project_atlas.orchestration.validator import (
    MAX_RESULT_BYTES,
    ResultValidationError,
    load_result_bytes,
    parse_envelope,
    read_result_source,
)

PACKAGE_ID: Final[Literal["AS-ORCH-001D"]] = "AS-ORCH-001D"
MAX_ACTIVE_DISPATCHES: Final[int] = 1
DEFAULT_ATTEMPT: Final[int] = 1
STATE_DIR_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "dispatcher"
ACTIVE_RELATIVE: Final[Path] = STATE_DIR_RELATIVE / "active.json"
RECORDS_RELATIVE: Final[Path] = STATE_DIR_RELATIVE / "records"
RESULTS_RELATIVE: Final[Path] = STATE_DIR_RELATIVE / "results"
RECEIPTS_RELATIVE: Final[Path] = STATE_DIR_RELATIVE / "receipts"
READ_ONLY_TASK_TYPES: Final[frozenset[TaskType]] = frozenset(
    {TaskType.CANDIDATE_VERIFICATION, TaskType.RECERTIFICATION}
)
MUTATING_REMEDIATION_AUTO_DISPATCH: Final[str] = (
    "BLOCKED_PENDING_EXISTING_AUTHORITY_BINDING"
)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TASK_ID_RE = re.compile(ID_PATTERN)
_ACTIVE_STATUSES = frozenset({"prepared", "running", "result_received", "finalizing"})
RECEIPT_AUTHENTICITY_CODES: Final[frozenset[str]] = frozenset(
    {
        "RECEIPT_NOT_FOUND",
        "RECEIPT_BINDING_MISMATCH",
        "RECEIPT_NOT_VALID",
        "RECEIPT_TAMPERED",
    }
)
_SUBMIT_FAIL_CLOSED_CODES: Final[frozenset[str]] = RECEIPT_AUTHENTICITY_CODES | frozenset(
    {
        "ROLE_MISMATCH",
        "TASK_ID_MISMATCH",
        "ATTEMPT_MISMATCH",
        "INVALID_TARGET_RESULT",
        "INVALID_RECEIPT",
    }
)
_PROMPT_TEMPLATE = (
    "You are an Atlas governed {target_role} agent.\n"
    "\n"
    "Governed task identity: {dispatch_task_id}\n"
    "Task type: {task_type}\n"
    "Source task: {source_task_id}\n"
    "Route digest: {route_digest}\n"
    "Attempt: {attempt}\n"
    "\n"
    "Read and obey repository AGENTS.md and canonical Atlas SKILL governance.\n"
    "\n"
    "Do not infer authority from this prompt.\n"
    "Do not merge.\n"
    "Do not push.\n"
    "Do not mutate main.\n"
    "Do not grant authority.\n"
    "\n"
    "Perform only the governed target role/task.\n"
    "This dispatch is read-only. Do not modify the repository.\n"
    "\n"
    "At completion, emit a valid AgentResultEnvelope for the exact dispatched\n"
    "task identity as the terminal structured result. You may also submit it\n"
    "through the dispatcher result interface:\n"
    "\n"
    "  atlas orchestrator dispatch-submit-result {dispatch_id} <result.json>\n"
    "\n"
    "Human-readable completion text is informational only.\n"
    "\n"
    "Do not route the next task yourself.\n"
)


class DispatcherError(ValueError):
    """Dispatcher operational error. Not an authority grant."""

    code: str = "DISPATCHER_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def _closed(code: str, message: str) -> None:
    raise DispatcherError(message, code=code)


class ActiveDispatchExists(DispatcherError):
    code = "ACTIVE_DISPATCH_EXISTS"


class DispatchStateTampered(DispatcherError):
    code = "DISPATCH_STATE_TAMPERED"


class DispatchResultAlreadyBound(DispatcherError):
    code = "DISPATCH_RESULT_ALREADY_BOUND"


class DispatchStatus(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    RESULT_RECEIVED = "result_received"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    TERMINAL = "TERMINAL"
    REJECTED = "REJECTED"


class DispatchRecord(BaseModel):
    """Persisted single-slot dispatch identity. Not authority and not a prompt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001D"] = "AS-ORCH-001D"
    dispatch_id: str = Field(min_length=64, max_length=64)
    status: DispatchStatus
    source_route_digest: str = Field(min_length=64, max_length=64)
    source_task_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    dispatch_task_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    target_role: ProducerRole
    task_type: TaskType
    attempt: int = Field(ge=1, le=10_000)
    workspace_root: str = Field(min_length=1, max_length=4096)
    process_started: bool = False
    process_terminal: bool = False
    process_timeout: bool = False
    process_exit_code: int | None = Field(default=None, ge=-1, le=1_000_000)
    result_received: bool = False
    source_acknowledged: bool = False
    result_staged: bool = False
    stdout_digest: str | None = Field(default=None, min_length=64, max_length=64)
    stderr_digest: str | None = Field(default=None, min_length=64, max_length=64)
    result_text_digest: str | None = Field(default=None, min_length=64, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    failure_code: str | None = Field(default=None, max_length=64)
    managed_session_id: str | None = Field(default=None, max_length=128, pattern=ID_PATTERN)
    target_receipt_id: str | None = Field(default=None, max_length=128, pattern=ID_PATTERN)
    target_receipt_verified: bool = False
    target_receipt_binding_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    raw_target_result_digest: str | None = Field(default=None, min_length=64, max_length=64)
    normalized_target_result_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    execution_authorized: Literal[False] = False

    @field_validator(
        "dispatch_id",
        "source_route_digest",
        "stdout_digest",
        "stderr_digest",
        "result_text_digest",
        "target_receipt_binding_digest",
        "raw_target_result_digest",
        "normalized_target_result_digest",
    )
    @classmethod
    def _digest_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DIGEST_RE.fullmatch(value):
            raise ValueError("field must be a SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def _identity_and_privileges(self) -> DispatchRecord:
        if self.execution_authorized is not False:
            raise ValueError("DispatchRecord cannot authorize execution")
        expected_id = compute_dispatch_id(
            route_digest=self.source_route_digest,
            target_role=self.target_role,
            task_type=self.task_type,
            source_task=self.source_task_id,
        )
        if self.dispatch_id != expected_id:
            raise ValueError("dispatch_id does not match trusted routing identity")
        if self.dispatch_task_id != dispatch_task_id_for(self.dispatch_id):
            raise ValueError("dispatch_task_id does not match dispatch_id")
        return self


class DispatchReceipt(BaseModel):
    """Proof of one hop. Not authority. Not a next-route chooser."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001D"] = "AS-ORCH-001D"
    dispatch_id: str | None = Field(default=None, min_length=64, max_length=64)
    status: DispatchStatus
    source_route_digest: str | None = Field(default=None, min_length=64, max_length=64)
    source_task_id: str | None = Field(default=None, max_length=128)
    dispatch_task_id: str | None = Field(default=None, max_length=128)
    target_role: ProducerRole | None = None
    task_type: TaskType | None = None
    attempt: int | None = Field(default=None, ge=1, le=10_000)
    process_started: bool = False
    process_terminal: bool = False
    process_timeout: bool = False
    process_exit_code: int | None = None
    result_received: bool = False
    source_acknowledged: bool = False
    result_staged: bool = False
    next_handoff_state: HandoffState | None = None
    next_route_digest: str | None = Field(default=None, min_length=64, max_length=64)
    failure_code: str | None = Field(default=None, max_length=64)
    mutating_remediation_auto_dispatch: str | None = Field(default=None, max_length=128)
    target_receipt_id: str | None = Field(default=None, max_length=128, pattern=ID_PATTERN)
    target_receipt_verified: bool = False
    target_receipt_binding_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    raw_target_result_digest: str | None = Field(default=None, min_length=64, max_length=64)
    normalized_target_result_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    execution_authorized: Literal[False] = False
    authority_granted: Literal[False] = False
    dispatch_receipt_is_authority: Literal[False] = False
    next_handoff_autodispatched: Literal[False] = False

    @field_validator(
        "dispatch_id",
        "source_route_digest",
        "next_route_digest",
        "target_receipt_binding_digest",
        "raw_target_result_digest",
        "normalized_target_result_digest",
    )
    @classmethod
    def _digest_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DIGEST_RE.fullmatch(value):
            raise ValueError("digest must be a SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def _no_authority(self) -> DispatchReceipt:
        if (
            self.execution_authorized is not False
            or self.authority_granted is not False
            or self.dispatch_receipt_is_authority is not False
            or self.next_handoff_autodispatched is not False
        ):
            raise ValueError("DispatchReceipt cannot grant authority or auto-dispatch")
        return self

    def to_public_dict(self) -> dict[str, object]:
        return {
            "package_id": self.package_id,
            "dispatch_id": self.dispatch_id,
            "status": self.status.value,
            "source_route_digest": self.source_route_digest,
            "source_task_id": self.source_task_id,
            "dispatch_task_id": self.dispatch_task_id,
            "target_role": self.target_role.value if self.target_role else None,
            "task_type": self.task_type.value if self.task_type else None,
            "attempt": self.attempt,
            "process_started": self.process_started,
            "process_terminal": self.process_terminal,
            "process_timeout": self.process_timeout,
            "process_exit_code": self.process_exit_code,
            "result_received": self.result_received,
            "source_acknowledged": self.source_acknowledged,
            "result_staged": self.result_staged,
            "next_handoff_state": (
                self.next_handoff_state.value if self.next_handoff_state else None
            ),
            "next_route_digest": self.next_route_digest,
            "failure_code": self.failure_code,
            "mutating_remediation_auto_dispatch": self.mutating_remediation_auto_dispatch,
            "target_receipt_verified": self.target_receipt_verified,
            "execution_authorized": False,
            "authority_granted": False,
            "dispatch_receipt_is_authority": False,
            "next_handoff_autodispatched": False,
        }


class DispatcherConfig(BaseModel):
    """Trusted operator configuration. Envelope fields cannot populate this."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1, le=86_400)
    executable: str | None = Field(default=None, max_length=4096)


class DispatchResultBinding(BaseModel):
    """Validated target evidence stored beside the dispatch, not in the 001C slot."""

    model_config = ConfigDict(extra="forbid")

    dispatch_id: str = Field(min_length=64, max_length=64)
    envelope_digest: str = Field(min_length=64, max_length=64)
    envelope: AgentResultEnvelope
    raw_target_result_digest: str | None = Field(default=None, min_length=64, max_length=64)
    normalized_target_result_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )

    @field_validator(
        "dispatch_id",
        "envelope_digest",
        "raw_target_result_digest",
        "normalized_target_result_digest",
    )
    @classmethod
    def _digest_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DIGEST_RE.fullmatch(value):
            raise ValueError("field must be a SHA-256 hex digest")
        return value


def compute_dispatch_id(
    *,
    route_digest: str,
    target_role: ProducerRole | str,
    task_type: TaskType | str,
    source_task: str,
) -> str:
    """Deterministic identity from trusted routing fields only."""
    if not _DIGEST_RE.fullmatch(route_digest):
        _closed("ELIGIBILITY_REJECTED", "route digest is not a SHA-256 hex digest")
    if not _TASK_ID_RE.fullmatch(source_task):
        _closed("ELIGIBILITY_REJECTED", "source task is not a safe identifier")
    role = target_role.value if isinstance(target_role, ProducerRole) else str(target_role)
    typed = task_type.value if isinstance(task_type, TaskType) else str(task_type)
    if role not in {item.value for item in ProducerRole}:
        _closed("ELIGIBILITY_REJECTED", "target role is not a valid ProducerRole")
    if typed not in {item.value for item in TaskType}:
        _closed("ELIGIBILITY_REJECTED", "task type is not a valid TaskType")
    payload = json.dumps(
        {
            "route_digest": route_digest,
            "source_task": source_task,
            "target_role": role,
            "task_type": typed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dispatch_task_id_for(dispatch_id: str) -> str:
    if not _DIGEST_RE.fullmatch(dispatch_id):
        _closed("ELIGIBILITY_REJECTED", "dispatch id is not a SHA-256 hex digest")
    return f"d.{dispatch_id}"


def trusted_dispatch_prompt(
    *,
    dispatch_id: str,
    dispatch_task_id: str,
    source_task_id: str,
    route_digest: str,
    target_role: ProducerRole,
    task_type: TaskType,
    attempt: int,
) -> str:
    """Fixed Atlas-owned template. Untrusted envelope text is never interpolated."""
    if not _DIGEST_RE.fullmatch(dispatch_id) or not _DIGEST_RE.fullmatch(route_digest):
        _closed("PROMPT_REJECTED", "prompt identity fields are not trusted digests")
    if not _TASK_ID_RE.fullmatch(dispatch_task_id) or not _TASK_ID_RE.fullmatch(source_task_id):
        _closed("PROMPT_REJECTED", "prompt task fields are not safe identifiers")
    if attempt < 1 or attempt > 10_000:
        raise DispatcherError("prompt attempt is out of bounds", code="PROMPT_REJECTED")
    return _PROMPT_TEMPLATE.format(
        target_role=target_role.value,
        dispatch_task_id=dispatch_task_id,
        task_type=task_type.value,
        source_task_id=source_task_id,
        route_digest=route_digest,
        attempt=attempt,
        dispatch_id=dispatch_id,
    )


def validate_workspace_root(root: Path) -> Path:
    """Reject unsafe or non-Atlas workspaces. Envelope paths cannot choose cwd."""
    resolved = resolve_repo_root(root)
    if resolved.is_symlink():
        raise DispatcherError("workspace root must not be a symlink", code="WORKSPACE_UNSAFE")
    agents = resolved / "AGENTS.md"
    pyproject = resolved / "pyproject.toml"
    marker = resolved / ".atlas-project.yaml"
    atlas_src = resolved / "src" / "project_atlas"
    if not agents.is_file() and not marker.is_file():
        raise DispatcherError("workspace is not an Atlas repository", code="WORKSPACE_UNSAFE")
    identity_ok = atlas_src.is_dir()
    if pyproject.is_file():
        snippet = pyproject.read_text(encoding="utf-8")[:4096]
        if "project-atlas" in snippet or "project_atlas" in snippet:
            identity_ok = True
    if marker.is_file():
        identity_ok = True
    if not identity_ok:
        raise DispatcherError("workspace identity is not Atlas", code="WORKSPACE_UNSAFE")
    return resolved


def _safe_under(root: Path, relative: Path) -> Path:
    resolved_root = root.expanduser().resolve()
    path = (resolved_root / relative).resolve()
    if not path.is_relative_to(resolved_root):
        _closed("DISPATCH_STATE_TAMPERED", "dispatcher path escaped workspace root")
    return path


def dispatcher_dir(root: Path) -> Path:
    return _safe_under(root, STATE_DIR_RELATIVE)


def record_path(root: Path, dispatch_id: str) -> Path:
    if not _DIGEST_RE.fullmatch(dispatch_id):
        _closed("ELIGIBILITY_REJECTED", "dispatch id is not a SHA-256 hex digest")
    return _safe_under(root, RECORDS_RELATIVE / f"{dispatch_id}.json")


def result_path(root: Path, dispatch_id: str) -> Path:
    if not _DIGEST_RE.fullmatch(dispatch_id):
        _closed("ELIGIBILITY_REJECTED", "dispatch id is not a SHA-256 hex digest")
    return _safe_under(root, RESULTS_RELATIVE / f"{dispatch_id}.json")


def receipt_path(root: Path, dispatch_id: str) -> Path:
    if not _DIGEST_RE.fullmatch(dispatch_id):
        _closed("ELIGIBILITY_REJECTED", "dispatch id is not a SHA-256 hex digest")
    return _safe_under(root, RECEIPTS_RELATIVE / f"{dispatch_id}.json")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def persist_record(root: Path, record: DispatchRecord) -> None:
    _write_json(record_path(root, record.dispatch_id), record.model_dump(mode="json"))


def persist_receipt(root: Path, receipt: DispatchReceipt) -> None:
    if receipt.dispatch_id is None:
        return
    _write_json(receipt_path(root, receipt.dispatch_id), receipt.model_dump(mode="json"))


def persist_active(root: Path, dispatch_id: str, status: DispatchStatus) -> None:
    _write_json(
        _safe_under(root, ACTIVE_RELATIVE),
        {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "dispatch_id": dispatch_id,
            "status": status.value,
        },
    )


def clear_active(root: Path, dispatch_id: str) -> None:
    path = _safe_under(root, ACTIVE_RELATIVE)
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(payload, dict) and payload.get("dispatch_id") == dispatch_id:
        path.unlink()


def load_active(root: Path) -> dict[str, str] | None:
    path = _safe_under(root, ACTIVE_RELATIVE)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    dispatch_id = payload.get("dispatch_id")
    status = payload.get("status")
    if not isinstance(dispatch_id, str) or not isinstance(status, str):
        return None
    return {"dispatch_id": dispatch_id, "status": status}


def load_record(root: Path, dispatch_id: str) -> DispatchRecord | None:
    path = record_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = DispatchRecord.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise DispatchStateTampered("persisted dispatch record failed validation") from exc
    expected = compute_dispatch_id(
        route_digest=record.source_route_digest,
        target_role=record.target_role,
        task_type=record.task_type,
        source_task=record.source_task_id,
    )
    if record.dispatch_id != expected or record.dispatch_id != dispatch_id:
        raise DispatchStateTampered("persisted dispatch identity was tampered")
    stored_root = Path(record.workspace_root).expanduser().resolve()
    if stored_root != root.expanduser().resolve():
        raise DispatchStateTampered("persisted workspace root does not match")
    return record


def load_receipt(root: Path, dispatch_id: str) -> DispatchReceipt | None:
    path = receipt_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        return DispatchReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError, ValueError):
        return None


def load_result_binding(root: Path, dispatch_id: str) -> DispatchResultBinding | None:
    path = result_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        binding = DispatchResultBinding.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise DispatchStateTampered("persisted dispatch result failed validation") from exc
    if binding.dispatch_id != dispatch_id:
        raise DispatchStateTampered("persisted result dispatch id was tampered")
    expected = canonical_payload_digest(binding.envelope.model_dump(mode="json"))
    if binding.envelope_digest != expected:
        raise DispatchStateTampered("persisted result digest was tampered")
    return binding


def _non_executing_receipt(
    *,
    status: DispatchStatus,
    packet: HandoffPacket,
    failure_code: str | None = None,
    mutating: str | None = None,
) -> DispatchReceipt:
    return DispatchReceipt(
        status=status,
        source_route_digest=packet.route_digest,
        source_task_id=packet.source_task,
        process_started=False,
        process_terminal=False,
        result_received=False,
        source_acknowledged=False,
        result_staged=False,
        failure_code=failure_code,
        mutating_remediation_auto_dispatch=mutating,
    )


def _receipt_from_record(
    record: DispatchRecord,
    *,
    next_packet: HandoffPacket | None = None,
) -> DispatchReceipt:
    return DispatchReceipt(
        dispatch_id=record.dispatch_id,
        status=record.status,
        source_route_digest=record.source_route_digest,
        source_task_id=record.source_task_id,
        dispatch_task_id=record.dispatch_task_id,
        target_role=record.target_role,
        task_type=record.task_type,
        attempt=record.attempt,
        process_started=record.process_started,
        process_terminal=record.process_terminal,
        process_timeout=record.process_timeout,
        process_exit_code=record.process_exit_code,
        result_received=record.result_received,
        source_acknowledged=record.source_acknowledged,
        result_staged=record.result_staged,
        next_handoff_state=next_packet.state if next_packet is not None else None,
        next_route_digest=next_packet.route_digest if next_packet is not None else None,
        failure_code=record.failure_code,
        mutating_remediation_auto_dispatch=(
            MUTATING_REMEDIATION_AUTO_DISPATCH
            if record.failure_code == "CAPABILITY_REQUIRED"
            else None
        ),
        target_receipt_id=record.target_receipt_id,
        target_receipt_verified=record.target_receipt_verified,
        target_receipt_binding_digest=record.target_receipt_binding_digest,
        raw_target_result_digest=record.raw_target_result_digest,
        normalized_target_result_digest=record.normalized_target_result_digest,
    )


def _bind_target_for(record: DispatchRecord) -> DispatchReceiptBindTarget:
    return DispatchReceiptBindTarget(
        dispatch_id=record.dispatch_id,
        dispatch_task_id=record.dispatch_task_id,
        managed_session_id=managed_session_id_for(
            record.dispatch_id, record.managed_session_id
        ),
        attempt=record.attempt,
        target_role=record.target_role.value,
    )


def _raise_receipt_error(exc: ReceiptBindingError) -> NoReturn:
    raise DispatcherError(str(exc), code=exc.code) from exc


def _reverify_bound_envelope(
    envelope: AgentResultEnvelope, record: DispatchRecord, workspace: Path
) -> None:
    try:
        verify_target_receipt_binding(envelope, _bind_target_for(record), workspace)
    except ReceiptBindingError as exc:
        _raise_receipt_error(exc)


def evaluate_dispatch_eligibility(packet: HandoffPacket, root: Path) -> None:
    """Recompute live Atlas route. Dispatcher cannot reroute."""
    if packet.state == HandoffState.OWNER_REQUIRED:
        raise DispatcherError("owner gate is not executable", code="OWNER_REQUIRED")
    if packet.state == HandoffState.TERMINAL:
        raise DispatcherError("terminal handoff is not executable", code="TERMINAL")
    if packet.state != HandoffState.HANDOFF_READY:
        raise DispatcherError("handoff is not HANDOFF_READY", code="ELIGIBILITY_REJECTED")
    verified = require_verified_state(root)
    route = verified.route
    if verified.route_digest != packet.route_digest:
        _closed("STALE_ROUTE_DIGEST", "live route digest does not match handoff")
    if route.route_kind != RouteKind.TASK or route.dispatchable is not True:
        _closed("ROUTE_NOT_DISPATCHABLE", "live route is not a dispatchable task")
    if route.owner_gate is not False or route.execution_authorized is not False:
        raise DispatcherError("live route failed privilege invariants", code="ELIGIBILITY_REJECTED")
    dumped = route.model_dump(mode="json")
    permissions = dumped.get("permissions")
    if not isinstance(permissions, dict) or any(
        permissions.get(flag) is True
        for flag in ("merge", "production_mutation", "authority_grant")
    ):
        _closed("ELIGIBILITY_REJECTED", "live route grants privileged permissions")
    if route.target.kind != TargetKind.AGENT or route.target.role is None:
        _closed("ELIGIBILITY_REJECTED", "live route target is not an agent role")
    if packet.target_role != route.target.role or packet.task_type != route.task_type:
        _closed("ELIGIBILITY_REJECTED", "handoff target does not match live route")
    if packet.source_task != verified.envelope.task.id:
        _closed("ELIGIBILITY_REJECTED", "handoff source task does not match live envelope")


def _reject_unrelated_active(root: Path, dispatch_id: str) -> None:
    active = load_active(root)
    if active is None:
        return
    if active["dispatch_id"] == dispatch_id:
        return
    if active["status"] in _ACTIVE_STATUSES:
        raise ActiveDispatchExists("ACTIVE_DISPATCH_EXISTS")


def submit_target_result(
    dispatch_id: str,
    payload: object,
    *,
    root: Path,
) -> DispatchResultBinding:
    """Store validated target evidence after canonical receipt authenticity.

    Paths B (CLI submit-result) and C (terminal JSON) share this function.
    Envelope ``receipt.status`` is never sufficient. Does not stage 001C.
    """
    workspace = validate_workspace_root(root)
    record = load_record(workspace, dispatch_id)
    if record is None:
        raise DispatcherError("no dispatch record for result submission", code="UNKNOWN_DISPATCH")
    try:
        envelope = parse_envelope(payload)
    except ResultValidationError as exc:
        raise DispatcherError(str(exc), code="INVALID_TARGET_RESULT") from exc
    if envelope.producer.role != record.target_role:
        raise DispatcherError("producer role does not match dispatch target", code="ROLE_MISMATCH")
    if envelope.task.id != record.dispatch_task_id:
        raise DispatcherError("task id does not match dispatch task", code="TASK_ID_MISMATCH")
    if envelope.task.attempt != record.attempt:
        raise DispatcherError("task attempt does not match dispatch", code="ATTEMPT_MISMATCH")
    raw_digest = canonical_payload_digest(envelope.model_dump(mode="json"))
    result_file = result_path(workspace, dispatch_id)
    existing = load_result_binding(workspace, dispatch_id) if result_file.is_file() else None
    if existing is not None:
        same_raw = existing.raw_target_result_digest == raw_digest
        if same_raw or existing.envelope_digest == raw_digest:
            _reverify_bound_envelope(existing.envelope, record, workspace)
            return existing
        raise DispatchResultAlreadyBound("DISPATCH_RESULT_ALREADY_BOUND")
    try:
        bound, facts = bind_target_receipt(envelope, _bind_target_for(record), workspace)
    except ReceiptBindingError as exc:
        _raise_receipt_error(exc)
    envelope_digest = canonical_payload_digest(bound.model_dump(mode="json"))
    binding = DispatchResultBinding(
        dispatch_id=dispatch_id,
        envelope_digest=envelope_digest,
        envelope=bound,
        raw_target_result_digest=str(facts["raw_target_result_digest"]),
        normalized_target_result_digest=str(facts["normalized_target_result_digest"]),
    )
    _write_json(result_file, binding.model_dump(mode="json"))
    updated = record.model_copy(
        update={
            "result_received": True,
            "status": DispatchStatus.RESULT_RECEIVED,
            "target_receipt_id": str(facts["receipt_id"]),
            "target_receipt_verified": True,
            "target_receipt_binding_digest": str(facts["target_receipt_binding_digest"]),
            "raw_target_result_digest": str(facts["raw_target_result_digest"]),
            "normalized_target_result_digest": str(facts["normalized_target_result_digest"]),
        }
    )
    if record.status in {
        DispatchStatus.PREPARED,
        DispatchStatus.RUNNING,
        DispatchStatus.RESULT_RECEIVED,
    }:
        persist_record(workspace, updated)
        persist_active(workspace, dispatch_id, updated.status)
    return binding


def _fail_record(
    root: Path, record: DispatchRecord, code: str, **updates: object
) -> DispatchReceipt:
    failed = record.model_copy(
        update={
            "status": DispatchStatus.FAILED,
            "failure_code": code,
            **updates,
        }
    )
    persist_record(root, failed)
    persist_active(root, failed.dispatch_id, failed.status)
    clear_active(root, failed.dispatch_id)
    receipt = _receipt_from_record(failed)
    persist_receipt(root, receipt)
    return receipt


def finalize_dispatch(root: Path, record: DispatchRecord) -> DispatchReceipt:
    """Ack source, stage target evidence, explicit-complete. Never starts a process."""
    workspace = validate_workspace_root(root)
    verified_record = load_record(workspace, record.dispatch_id)
    if verified_record is None:
        raise DispatchStateTampered("dispatch record missing during finalization")
    if verified_record.status == DispatchStatus.COMPLETED:
        existing = load_receipt(workspace, verified_record.dispatch_id)
        if existing is not None:
            return existing
    binding = load_result_binding(workspace, verified_record.dispatch_id)
    if binding is None:
        return _fail_record(workspace, verified_record, "RESULT_NOT_SUBMITTED")
    try:
        verify_target_receipt_binding(
            binding.envelope, _bind_target_for(verified_record), workspace
        )
    except ReceiptBindingError as exc:
        return _fail_record(workspace, verified_record, exc.code, result_received=True)
    bound_receipt_id = (
        binding.envelope.receipt.receipt_id if binding.envelope.receipt is not None else None
    )
    verified_record = verified_record.model_copy(
        update={
            "target_receipt_verified": True,
            "target_receipt_id": bound_receipt_id or verified_record.target_receipt_id,
            "normalized_target_result_digest": (
                verified_record.normalized_target_result_digest or binding.envelope_digest
            ),
        }
    )
    if not verified_record.process_terminal or verified_record.process_exit_code != 0:
        return _fail_record(
            workspace,
            verified_record,
            "PROCESS_FAILED_WITH_RESULT" if binding is not None else "PROCESS_FAILED",
            result_received=True,
        )
    if verified_record.process_timeout:
        return _fail_record(workspace, verified_record, "PROCESS_TIMEOUT", result_received=True)
    live = require_verified_state(workspace)
    target_digest = source_result_digest(binding.envelope)
    live_source = source_result_digest(live.envelope)
    already_staged = live_source == target_digest
    if already_staged:
        verified_record = verified_record.model_copy(
            update={"source_acknowledged": True, "result_staged": True}
        )
    elif live.route_digest != verified_record.source_route_digest:
        raise DispatcherError("source route changed before finalization", code="STALE_ROUTE_DIGEST")
    elif live.status == BridgeStatus.ACKNOWLEDGED:
        verified_record = verified_record.model_copy(update={"source_acknowledged": True})
    elif live.status != BridgeStatus.PENDING and not verified_record.source_acknowledged:
        raise DispatcherError(
            "source handoff is not pending for acknowledgement",
            code="STALE_ROUTE_DIGEST",
        )
    working = verified_record.model_copy(
        update={"status": DispatchStatus.FINALIZING, "result_received": True}
    )
    persist_record(workspace, working)
    persist_active(workspace, working.dispatch_id, working.status)
    if not working.source_acknowledged:
        acknowledge(working.source_route_digest, root=workspace)
        working = working.model_copy(update={"source_acknowledged": True})
        persist_record(workspace, working)
    if not working.result_staged:
        stage_result(binding.envelope.model_dump(mode="json"), root=workspace)
        working = working.model_copy(update={"result_staged": True})
        persist_record(workspace, working)
    next_packet = complete_staged_handoff(root=workspace)
    completed = working.model_copy(update={"status": DispatchStatus.COMPLETED})
    persist_record(workspace, completed)
    receipt = _receipt_from_record(completed, next_packet=next_packet)
    persist_receipt(workspace, receipt)
    clear_active(workspace, completed.dispatch_id)
    return receipt


def recover_dispatch(dispatch_id: str, *, root: Path) -> DispatchReceipt:
    """Finish finalization after result_received. Never starts a target process."""
    workspace = validate_workspace_root(root)
    existing_receipt = load_receipt(workspace, dispatch_id)
    record = load_record(workspace, dispatch_id)
    if record is None:
        if existing_receipt is not None:
            return existing_receipt
        raise DispatcherError("no dispatch record to recover", code="UNKNOWN_DISPATCH")
    if record.status == DispatchStatus.COMPLETED:
        return existing_receipt or _receipt_from_record(record)
    if record.status == DispatchStatus.FAILED:
        return existing_receipt or _receipt_from_record(record)
    if record.status in {DispatchStatus.RESULT_RECEIVED, DispatchStatus.FINALIZING}:
        return finalize_dispatch(workspace, record)
    raise DispatcherError(
        "recovery does not start a target process",
        code="CRASH_RECOVERY_DOES_NOT_RESPAWN",
    )


def run_dispatch_once(
    *,
    root: Path,
    runner: ProcessRunner | None = None,
    config: DispatcherConfig | None = None,
) -> DispatchReceipt:
    """Single hop: complete → maybe start one process → finalize → stop."""
    workspace = validate_workspace_root(root)
    trusted = config or DispatcherConfig()
    packet = complete_staged_handoff(root=workspace)
    if packet.state == HandoffState.OWNER_REQUIRED:
        return _non_executing_receipt(status=DispatchStatus.OWNER_REQUIRED, packet=packet)
    if packet.state == HandoffState.TERMINAL:
        return _non_executing_receipt(status=DispatchStatus.TERMINAL, packet=packet)
    try:
        evaluate_dispatch_eligibility(packet, workspace)
    except DispatcherError as exc:
        if exc.code in {"OWNER_REQUIRED", "TERMINAL"}:
            return _non_executing_receipt(status=DispatchStatus(exc.code), packet=packet)
        return _non_executing_receipt(
            status=DispatchStatus.REJECTED,
            packet=packet,
            failure_code=exc.code,
        )
    if packet.target_role is None or packet.task_type is None or packet.source_task is None:
        return _non_executing_receipt(
            status=DispatchStatus.REJECTED,
            packet=packet,
            failure_code="ELIGIBILITY_REJECTED",
        )
    if packet.task_type not in READ_ONLY_TASK_TYPES:
        return _non_executing_receipt(
            status=DispatchStatus.REJECTED,
            packet=packet,
            failure_code="CAPABILITY_REQUIRED",
            mutating=MUTATING_REMEDIATION_AUTO_DISPATCH,
        )
    dispatch_id = compute_dispatch_id(
        route_digest=packet.route_digest,
        target_role=packet.target_role,
        task_type=packet.task_type,
        source_task=packet.source_task,
    )
    existing = None
    try:
        existing = load_record(workspace, dispatch_id)
    except DispatchStateTampered:
        raise
    if existing is not None:
        if existing.status == DispatchStatus.COMPLETED:
            receipt = load_receipt(workspace, dispatch_id)
            return receipt or _receipt_from_record(existing)
        if existing.status == DispatchStatus.FAILED:
            receipt = load_receipt(workspace, dispatch_id)
            return receipt or _receipt_from_record(existing)
        if existing.status in {DispatchStatus.RESULT_RECEIVED, DispatchStatus.FINALIZING}:
            return finalize_dispatch(workspace, existing)
        if existing.status in {DispatchStatus.PREPARED, DispatchStatus.RUNNING}:
            raise DispatcherError(
                "dispatch is already prepared or running",
                code="DISPATCH_ALREADY_ACTIVE",
            )
    _reject_unrelated_active(workspace, dispatch_id)
    record = DispatchRecord(
        dispatch_id=dispatch_id,
        status=DispatchStatus.PREPARED,
        source_route_digest=packet.route_digest,
        source_task_id=packet.source_task,
        dispatch_task_id=dispatch_task_id_for(dispatch_id),
        target_role=packet.target_role,
        task_type=packet.task_type,
        attempt=DEFAULT_ATTEMPT,
        workspace_root=str(workspace),
        managed_session_id=managed_session_id_for(dispatch_id),
    )
    persist_record(workspace, record)
    persist_active(workspace, dispatch_id, record.status)
    try:
        ensure_managed_dispatch_session(workspace, _bind_target_for(record))
    except ReceiptBindingError as exc:
        return _fail_record(workspace, record, exc.code)
    prompt = trusted_dispatch_prompt(
        dispatch_id=dispatch_id,
        dispatch_task_id=record.dispatch_task_id,
        source_task_id=record.source_task_id,
        route_digest=record.source_route_digest,
        target_role=record.target_role,
        task_type=record.task_type,
        attempt=record.attempt,
    )
    try:
        transport = (
            ResolvedCursorExecutable(
                logical_name="agent",
                path="agent",
                launcher_kind=LauncherKind.DIRECT,
            )
            if runner is not None and trusted.executable is None
            else resolve_cursor_transport(trusted.executable)
        )
        plan = build_launch_plan(
            transport,
            prompt,
            cwd=workspace,
            timeout_seconds=trusted.timeout_seconds,
        )
        if plan.uses_force is not False or "--force" in plan.argv or "--yolo" in plan.argv:
            raise TransportError("read-only dispatch forbids --force", code="FORCE_FORBIDDEN")
    except TransportError as exc:
        return _fail_record(workspace, record, exc.code)
    process_runner = runner if runner is not None else SubprocessProcessRunner()
    running = record.model_copy(update={"status": DispatchStatus.RUNNING, "process_started": True})
    persist_record(workspace, running)
    persist_active(workspace, dispatch_id, running.status)
    request = ProcessRunRequest(
        argv=plan.argv,
        cwd=Path(plan.cwd),
        timeout_seconds=plan.timeout_seconds,
        env=sanitize_inherited_env(),
        stdin=plan.stdin_payload.encode("utf-8"),
    )
    outcome = process_runner.run(request)
    return _complete_after_process(workspace, running, outcome)


def _complete_after_process(
    root: Path,
    record: DispatchRecord,
    outcome: ProcessRunOutcome,
) -> DispatchReceipt:
    parsed = parse_structured_cursor_output(outcome.stdout)
    updates: dict[str, object] = {
        "process_started": True,
        "process_terminal": True,
        "process_timeout": outcome.timed_out,
        "process_exit_code": outcome.exit_code,
        "stdout_digest": digest_bytes(outcome.stdout),
        "stderr_digest": digest_bytes(outcome.stderr),
        "result_text_digest": parsed.result_text_digest,
        "session_id": parsed.session_id,
        "request_id": parsed.request_id,
        "duration_ms": outcome.duration_ms,
    }
    latest = load_record(root, record.dispatch_id) or record
    working = latest.model_copy(update=updates)
    persist_record(root, working)
    if outcome.timed_out:
        return _fail_record(root, working, "PROCESS_TIMEOUT", **updates)
    if parsed.kind is CursorOutputKind.MISSING:
        return _fail_record(root, working, "MISSING_CURSOR_OUTPUT", **updates)
    if parsed.kind is CursorOutputKind.MALFORMED:
        return _fail_record(root, working, "MALFORMED_CURSOR_OUTPUT", **updates)
    if parsed.kind is CursorOutputKind.CURSOR_ERROR or parsed.is_error:
        return _fail_record(root, working, "CURSOR_ERROR_RESULT", **updates)
    if outcome.exit_code != 0:
        binding = None
        try:
            binding = load_result_binding(root, working.dispatch_id)
        except DispatchStateTampered:
            binding = None
        code = "PROCESS_FAILED_WITH_RESULT" if binding is not None else "PROCESS_FAILED"
        return _fail_record(root, working, code, result_received=binding is not None, **updates)
    binding = None
    try:
        binding = load_result_binding(root, working.dispatch_id)
    except DispatchStateTampered as exc:
        return _fail_record(root, working, exc.code, **updates)
    if binding is None:
        candidate = extract_result_payload(outcome.stdout)
        if candidate is not None:
            try:
                submit_target_result(working.dispatch_id, candidate, root=root)
                binding = load_result_binding(root, working.dispatch_id)
            except DispatcherError as exc:
                if exc.code in _SUBMIT_FAIL_CLOSED_CODES:
                    return _fail_record(root, working, exc.code, **updates)
                binding = None
    if binding is None:
        return _fail_record(root, working, "RESULT_NOT_SUBMITTED", **updates)
    latest = load_record(root, working.dispatch_id) or working
    received = latest.model_copy(
        update={
            **updates,
            "status": DispatchStatus.RESULT_RECEIVED,
            "result_received": True,
        }
    )
    persist_record(root, received)
    persist_active(root, received.dispatch_id, received.status)
    return finalize_dispatch(root, received)


def status_report(root: Path) -> dict[str, object]:
    """Read-only dispatcher facts. No secrets, prompts, or model prose."""
    workspace = validate_workspace_root(root)
    active = load_active(workspace)
    dispatch_id = active["dispatch_id"] if active is not None else None
    record = None
    if dispatch_id is not None:
        try:
            record = load_record(workspace, dispatch_id)
        except DispatcherError:
            record = None
    receipt = load_receipt(workspace, dispatch_id) if dispatch_id is not None else None
    if record is None and receipt is None:
        latest = _latest_receipt(workspace)
        receipt = latest
        dispatch_id = latest.dispatch_id if latest is not None else None
        if dispatch_id is not None:
            try:
                record = load_record(workspace, dispatch_id)
            except DispatcherError:
                record = None
    return {
        "package_id": PACKAGE_ID,
        "active_dispatch_id": active["dispatch_id"] if active is not None else dispatch_id,
        "status": (
            record.status.value
            if record is not None
            else receipt.status.value
            if receipt is not None
            else "absent"
        ),
        "source_route_digest": record.source_route_digest if record else (
            receipt.source_route_digest if receipt else None
        ),
        "source_task": record.source_task_id if record else (
            receipt.source_task_id if receipt else None
        ),
        "dispatch_task": record.dispatch_task_id if record else (
            receipt.dispatch_task_id if receipt else None
        ),
        "target_role": record.target_role.value if record else (
            receipt.target_role.value if receipt and receipt.target_role else None
        ),
        "task_type": record.task_type.value if record else (
            receipt.task_type.value if receipt and receipt.task_type else None
        ),
        "attempt": record.attempt if record else (receipt.attempt if receipt else None),
        "process_started": record.process_started if record else (
            receipt.process_started if receipt else False
        ),
        "process_terminal": record.process_terminal if record else (
            receipt.process_terminal if receipt else False
        ),
        "result_received": record.result_received if record else (
            receipt.result_received if receipt else False
        ),
        "target_receipt_verified": (
            record.target_receipt_verified
            if record is not None
            else receipt.target_receipt_verified
            if receipt is not None
            else False
        ),
        "next_handoff_state": (
            receipt.next_handoff_state.value
            if receipt and receipt.next_handoff_state
            else None
        ),
        "failure_code": record.failure_code if record else (
            receipt.failure_code if receipt else None
        ),
        "execution_authorized": False,
        "cursor_stop_event_required": False,
        "max_active_dispatches": MAX_ACTIVE_DISPATCHES,
        "next_handoff_autodispatched": False,
    }


def _latest_receipt(root: Path) -> DispatchReceipt | None:
    directory = _safe_under(root, RECEIPTS_RELATIVE)
    if not directory.is_dir():
        return None
    latest: DispatchReceipt | None = None
    for path in sorted(directory.glob("*.json")):
        try:
            candidate = DispatchReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError, ValueError):
            continue
        latest = candidate
    return latest


def _public_error(code: str) -> dict[str, object]:
    return {
        "ok": False,
        "package_id": PACKAGE_ID,
        "error": code,
        "execution_authorized": False,
        "next_handoff_autodispatched": False,
    }


def run_cli_dispatch_once(
    *,
    root: Path,
    runner: ProcessRunner | None = None,
    config: DispatcherConfig | None = None,
) -> tuple[dict[str, object], int]:
    try:
        receipt = run_dispatch_once(root=root, runner=runner, config=config)
    except ActiveDispatchExists as exc:
        return _public_error(exc.code), 1
    except (DispatchStateTampered, StagedStateTampered) as exc:
        return _public_error(getattr(exc, "code", "DISPATCH_STATE_TAMPERED")), 1
    except (DispatcherError, CursorBridgeError, TransportError) as exc:
        return _public_error(getattr(exc, "code", "DISPATCHER_ERROR")), 1
    payload = receipt.to_public_dict()
    payload["ok"] = receipt.status not in {
        DispatchStatus.FAILED,
        DispatchStatus.REJECTED,
    }
    exit_code = 0 if payload["ok"] else 1
    return payload, exit_code


def run_cli_dispatch_status(*, root: Path) -> tuple[dict[str, object], int]:
    try:
        return status_report(root), 0
    except (DispatcherError, CursorBridgeError) as exc:
        return _public_error(getattr(exc, "code", "DISPATCHER_ERROR")), 1


def run_cli_submit_result(
    *,
    dispatch_id: str,
    path: Path | None,
    from_stdin: bool,
    stdin: TextIO,
    root: Path,
) -> tuple[dict[str, object], int]:
    try:
        raw = read_result_source(path=path, from_stdin=from_stdin, stdin=stdin)
        if len(raw) > MAX_RESULT_BYTES:
            raise ResultValidationError("result envelope exceeds size limit")
        payload = load_result_bytes(raw)
        binding = submit_target_result(dispatch_id, payload, root=root)
    except DispatchResultAlreadyBound as exc:
        return _public_error(exc.code), 1
    except (ResultValidationError, DispatcherError, CursorBridgeError, OSError) as exc:
        code = getattr(exc, "code", None) or (
            "RESULT_TOO_LARGE" if "size limit" in str(exc) else "INVALID_TARGET_RESULT"
        )
        return _public_error(str(code)), 1
    return {
        "ok": True,
        "package_id": PACKAGE_ID,
        "dispatch_id": binding.dispatch_id,
        "envelope_digest": binding.envelope_digest,
        "result_received": True,
        "staged": False,
        "execution_authorized": False,
    }, 0


def run_cli_recover(*, dispatch_id: str, root: Path) -> tuple[dict[str, object], int]:
    try:
        receipt = recover_dispatch(dispatch_id, root=root)
    except (DispatchStateTampered, StagedStateTampered) as exc:
        return _public_error(getattr(exc, "code", "DISPATCH_STATE_TAMPERED")), 1
    except (DispatcherError, CursorBridgeError) as exc:
        return _public_error(getattr(exc, "code", "DISPATCHER_ERROR")), 1
    payload = receipt.to_public_dict()
    payload["ok"] = receipt.status == DispatchStatus.COMPLETED
    return payload, 0 if payload["ok"] else 1
