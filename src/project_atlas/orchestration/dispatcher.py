"""AS-ORCH-001D governed single-hop agent dispatcher (fresh current-main).

HANDOFF → AGENT → RESULT → NEXT_HANDOFF → STOP

One process may be started for one dispatchable task route. The next
HandoffPacket is never auto-dispatched. Privileges remain false.
PROCESS_DISPATCH != PRIVILEGED EXECUTION AUTHORITY.

SINGLE_HOP_AGENT_DISPATCHER = IMPLEMENTED
AUTONOMOUS_LOOP = NOT_IMPLEMENTED
MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED
DISPATCH_RECEIPT_IS_AUTHORITY = NO
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, TextIO

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
    ProcessRunner,
    ProcessRunOutcome,
    ProcessRunRequest,
    SubprocessProcessRunner,
    TransportError,
    build_launch_plan,
    digest_bytes,
    parse_structured_cursor_output,
    resolve_cursor_transport,
    sanitize_inherited_env,
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
from project_atlas.orchestration.validator import ResultValidationError, parse_envelope

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
    "\n"
    "At completion, produce a valid AgentResultEnvelope for the exact dispatched\n"
    "task identity and submit it through the dispatcher result interface:\n"
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
    execution_authorized: Literal[False] = False

    @field_validator(
        "dispatch_id",
        "source_route_digest",
        "stdout_digest",
        "stderr_digest",
        "result_text_digest",
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
    execution_authorized: Literal[False] = False
    authority_granted: Literal[False] = False
    dispatch_receipt_is_authority: Literal[False] = False
    next_handoff_autodispatched: Literal[False] = False

    @field_validator("dispatch_id", "source_route_digest", "next_route_digest")
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

    @field_validator("dispatch_id", "envelope_digest")
    @classmethod
    def _digest_hex(cls, value: str) -> str:
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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def persist_record(root: Path, record: DispatchRecord) -> None:
    _write_json(record_path(root, record.dispatch_id), record.model_dump(mode="json"))


def persist_receipt(root: Path, receipt: DispatchReceipt) -> None:
    if receipt.dispatch_id is None:
        return
    _write_json(receipt_path(root, receipt.dispatch_id), receipt.model_dump(mode="json"))


def persist_active(root: Path, dispatch_id: str, status: DispatchStatus) -> None:
    _write_json(
        _safe_under(root, ACTIVE_RELATIVE),
        {"dispatch_id": dispatch_id, "status": status.value},
    )


def clear_active(root: Path, dispatch_id: str) -> None:
    path = _safe_under(root, ACTIVE_RELATIVE)
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return
    if payload.get("dispatch_id") == dispatch_id:
        path.unlink(missing_ok=True)


def load_active(root: Path) -> dict[str, str] | None:
    path = _safe_under(root, ACTIVE_RELATIVE)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchStateTampered("active dispatch slot is unreadable") from exc
    dispatch_id = payload.get("dispatch_id")
    status = payload.get("status")
    if not isinstance(dispatch_id, str) or not isinstance(status, str):
        raise DispatchStateTampered("active dispatch slot is malformed")
    return {"dispatch_id": dispatch_id, "status": status}


def load_record(root: Path, dispatch_id: str) -> DispatchRecord | None:
    path = record_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DispatchRecord.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DispatchStateTampered("dispatch record is unreadable or invalid") from exc


def load_receipt(root: Path, dispatch_id: str) -> DispatchReceipt | None:
    path = receipt_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        return DispatchReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DispatchStateTampered("dispatch receipt is unreadable or invalid") from exc


def load_result_binding(root: Path, dispatch_id: str) -> DispatchResultBinding | None:
    path = result_path(root, dispatch_id)
    if not path.is_file():
        return None
    try:
        return DispatchResultBinding.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DispatchStateTampered("dispatch result binding is unreadable") from exc


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
    )


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
    """Store validated target evidence. Does not stage the 001C slot."""
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
    if not envelope.receipt_is_valid_evidence():
        raise DispatcherError("target result receipt is not valid evidence", code="INVALID_RECEIPT")
    envelope_digest = canonical_payload_digest(envelope.model_dump(mode="json"))
    result_file = result_path(workspace, dispatch_id)
    if result_file.is_file():
        existing = load_result_binding(workspace, dispatch_id)
        if existing is not None:
            if existing.envelope_digest == envelope_digest:
                return existing
            raise DispatchResultAlreadyBound("DISPATCH_RESULT_ALREADY_BOUND")
    binding = DispatchResultBinding(
        dispatch_id=dispatch_id,
        envelope_digest=envelope_digest,
        envelope=envelope,
    )
    _write_json(result_file, binding.model_dump(mode="json"))
    updated = record.model_copy(
        update={"result_received": True, "status": DispatchStatus.RESULT_RECEIVED}
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
    existing = load_record(workspace, dispatch_id)
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
    )
    persist_record(workspace, record)
    persist_active(workspace, dispatch_id, record.status)
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
        if runner is not None and trusted.executable is None:
            executable = resolve_cursor_transport(
                "agent",
                which=lambda _name: "agent",
                exists=lambda _path: True,
                os_name="posix",
            )
        else:
            executable = resolve_cursor_transport(trusted.executable)
        plan = build_launch_plan(executable, prompt, cwd=workspace)
    except TransportError as exc:
        return _fail_record(workspace, record, exc.code)
    process_runner = runner if runner is not None else SubprocessProcessRunner()
    running = record.model_copy(update={"status": DispatchStatus.RUNNING, "process_started": True})
    persist_record(workspace, running)
    persist_active(workspace, dispatch_id, running.status)
    request = ProcessRunRequest(
        argv=tuple(plan.argv),
        cwd=workspace,
        timeout_seconds=trusted.timeout_seconds,
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
        "process_terminal": True,
        "process_timeout": outcome.timed_out,
        "process_exit_code": outcome.exit_code,
        "stdout_digest": digest_bytes(outcome.stdout),
        "stderr_digest": digest_bytes(outcome.stderr),
        "duration_ms": outcome.duration_ms,
        "result_text_digest": parsed.result_text_digest,
        "session_id": parsed.session_id,
        "request_id": parsed.request_id,
    }
    if outcome.timed_out:
        return _fail_record(root, record, "PROCESS_TIMEOUT", **updates)
    if outcome.exit_code != 0 or parsed.kind in {
        CursorOutputKind.MISSING,
        CursorOutputKind.MALFORMED,
        CursorOutputKind.CURSOR_ERROR,
    }:
        code = "PROCESS_FAILED" if outcome.exit_code != 0 else "CURSOR_OUTPUT_UNUSABLE"
        return _fail_record(root, record, code, **updates)
    terminal = record.model_copy(update={**updates, "status": DispatchStatus.RUNNING})
    persist_record(root, terminal)
    binding = load_result_binding(root, terminal.dispatch_id)
    if binding is None:
        return _fail_record(
            root,
            terminal,
            "RESULT_NOT_SUBMITTED",
            **updates,
        )
    received = terminal.model_copy(
        update={"result_received": True, "status": DispatchStatus.RESULT_RECEIVED}
    )
    persist_record(root, received)
    persist_active(root, received.dispatch_id, received.status)
    return finalize_dispatch(root, received)


def status_report(root: Path) -> dict[str, object]:
    workspace = validate_workspace_root(root)
    active = None
    try:
        active = load_active(workspace)
    except DispatchStateTampered:
        active = {"error": "DISPATCH_STATE_TAMPERED"}
    latest = _latest_receipt(workspace)
    return {
        "package_id": PACKAGE_ID,
        "max_active_dispatches": MAX_ACTIVE_DISPATCHES,
        "active": active,
        "latest_receipt": latest.to_public_dict() if latest is not None else None,
        "execution_authorized": False,
        "next_handoff_autodispatched": False,
        "dispatch_receipt_is_authority": False,
    }


def _latest_receipt(root: Path) -> DispatchReceipt | None:
    directory = _safe_under(root, RECEIPTS_RELATIVE)
    if not directory.is_dir():
        return None
    newest: DispatchReceipt | None = None
    newest_mtime = -1.0
    for path in directory.glob("*.json"):
        try:
            receipt = DispatchReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError):
            continue
        mtime = path.stat().st_mtime
        if mtime >= newest_mtime:
            newest = receipt
            newest_mtime = mtime
    return newest


def _public_error(code: str) -> dict[str, object]:
    return {
        "package_id": PACKAGE_ID,
        "status": "FAILED",
        "failure_code": code,
        "process_started": False,
        "execution_authorized": False,
        "dispatch_receipt_is_authority": False,
        "next_handoff_autodispatched": False,
    }


def run_cli_dispatch_once(
    *,
    root: Path,
    runner: ProcessRunner | None = None,
) -> tuple[dict[str, object], int]:
    try:
        receipt = run_dispatch_once(root=root, runner=runner)
    except (DispatcherError, CursorBridgeError, StagedStateTampered) as exc:
        code = getattr(exc, "code", "DISPATCHER_ERROR")
        return _public_error(str(code)), 1
    payload = receipt.to_public_dict()
    exit_code = 0 if receipt.status == DispatchStatus.COMPLETED else 1
    if receipt.status in {DispatchStatus.OWNER_REQUIRED, DispatchStatus.TERMINAL}:
        exit_code = 0
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
    from project_atlas.orchestration.validator import load_result_bytes, read_result_source

    try:
        source = read_result_source(path=path, from_stdin=from_stdin, stdin=stdin)
        payload = load_result_bytes(source)
        binding = submit_target_result(dispatch_id, payload, root=root)
    except (DispatcherError, ResultValidationError, json.JSONDecodeError, OSError) as exc:
        code = getattr(exc, "code", "INVALID_TARGET_RESULT")
        return _public_error(str(code)), 1
    return {
        "package_id": PACKAGE_ID,
        "dispatch_id": binding.dispatch_id,
        "envelope_digest": binding.envelope_digest,
        "result_received": True,
        "execution_authorized": False,
    }, 0


def run_cli_recover(*, dispatch_id: str, root: Path) -> tuple[dict[str, object], int]:
    try:
        receipt = recover_dispatch(dispatch_id, root=root)
    except DispatcherError as exc:
        return _public_error(exc.code), 1
    return receipt.to_public_dict(), 0 if receipt.status == DispatchStatus.COMPLETED else 1
