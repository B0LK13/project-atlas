"""AS-ORCH-001C Cursor integration bridge.

Cursor is transport/lifecycle only. Atlas remains the source of workflow truth.

  Cursor stop event → thin adapter → this module → 001A validate/classify
  → 001B route → safe followup_message or empty continuation

This module does not dispatch agents, execute TaskDirective, merge, or grant
authority. A single pending route may emit at most one followup_message.
"""

from __future__ import annotations

import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, TextIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from project_atlas.orchestration.models import (
    AgentResultEnvelope,
    OrchestrationRoute,
    RouteKind,
)
from project_atlas.orchestration.router import (
    canonical_payload_digest,
    route_payload,
    source_result_digest,
)
from project_atlas.orchestration.validator import (
    ResultValidationError,
    load_result_bytes,
    parse_envelope,
    read_result_source,
)

PACKAGE_ID: Final[Literal["AS-ORCH-001C"]] = "AS-ORCH-001C"
POLICY_ID: Final[Literal["atlas-orchestration-routing"]] = "atlas-orchestration-routing"
POLICY_VERSION: Final[Literal[1]] = 1
STATE_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "cursor" / "state.json"
HOOK_CONFIG_RELATIVE: Final[Path] = Path(".cursor") / "hooks.json"
HOOK_ENTRY_RELATIVE: Final[Path] = Path(".cursor") / "hooks" / "atlas_stop.py"
COMPLETED_STATUS: Final[str] = "completed"
BRIDGE_MARKER: Final[str] = "[ATLAS_CURSOR_BRIDGE]"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class CursorBridgeError(ValueError):
    """Bridge operational error. Not an authority grant."""

    code: str = "CURSOR_BRIDGE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class PendingHandoffExists(CursorBridgeError):
    """Unacknowledged pending handoff already occupies the single slot."""

    code = "PENDING_HANDOFF_EXISTS"


class BridgeAckError(CursorBridgeError):
    """Acknowledgement rejected. Acknowledgement is not authority."""

    code = "BRIDGE_ACK_REJECTED"


class BridgeStatus(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    TERMINAL = "terminal"


class CursorStopEvent(BaseModel):
    """Documented stop-hook fields Atlas consumes. Extra metadata is ignored."""

    model_config = ConfigDict(extra="ignore")

    conversation_id: str | None = Field(default=None, max_length=256)
    status: str = Field(min_length=1, max_length=64)
    loop_count: int = Field(default=0, ge=0, le=1_000_000)


class CursorBridgeState(BaseModel):
    """Single-slot ephemeral handoff. Not a queue and not a dispatcher."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001C"] = "AS-ORCH-001C"
    status: BridgeStatus
    source_result_digest: str = Field(min_length=64, max_length=64)
    route_digest: str = Field(min_length=64, max_length=64)
    envelope: AgentResultEnvelope
    route: OrchestrationRoute
    policy_id: Literal["atlas-orchestration-routing"] = "atlas-orchestration-routing"
    policy_version: Literal[1] = 1
    followup_emitted: bool = False

    @field_validator("source_result_digest", "route_digest")
    @classmethod
    def _digest_hex(cls, value: str) -> str:
        if not _DIGEST_RE.fullmatch(value):
            raise ValueError("digest must be a SHA-256 hex digest")
        return value

    @field_validator("route")
    @classmethod
    def _no_privilege(cls, value: OrchestrationRoute) -> OrchestrationRoute:
        if value.execution_authorized is not False:
            raise ValueError("bridge state cannot authorize execution")
        if (
            value.permissions.merge
            or value.permissions.production_mutation
            or value.permissions.authority_grant
        ):
            raise ValueError("bridge state cannot grant privileged permissions")
        return value


class CursorBridgeResponse(BaseModel):
    """Stdout contract for the Cursor stop hook. Empty object means no continuation."""

    model_config = ConfigDict(extra="forbid")

    followup_message: str | None = None

    def to_stdout_dict(self) -> dict[str, str]:
        if self.followup_message is None:
            return {}
        return {"followup_message": self.followup_message}


def route_digest(route: OrchestrationRoute) -> str:
    """Deterministic identity over the canonical validated route. Not authority."""
    return canonical_payload_digest(route.model_dump(mode="json"))


def _privileges_closed(route: OrchestrationRoute) -> bool:
    """Inspect dumped flags. Typed literals are fail-closed; dump is the runtime check."""
    dumped = route.model_dump(mode="json")
    permissions = dumped.get("permissions")
    if not isinstance(permissions, dict):
        return False
    if dumped.get("execution_authorized") is not False:
        return False
    return not any(
        permissions.get(flag) is True
        for flag in ("merge", "production_mutation", "authority_grant")
    )


def resolve_repo_root(root: Path | None) -> Path:
    """Resolve and reject unsafe roots. Hook cwd is not assumed to be the repo."""
    if root is None:
        raise CursorBridgeError("repository root is required")
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CursorBridgeError("repository root is not a directory")
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise CursorBridgeError("refusing filesystem root or home as bridge root")
    return resolved


def bridge_state_path(root: Path) -> Path:
    resolved = resolve_repo_root(root)
    path = (resolved / STATE_RELATIVE).resolve()
    if not path.is_relative_to(resolved):
        raise CursorBridgeError("bridge state path escaped repository root")
    return path


def stage_result(payload: object, *, root: Path) -> CursorBridgeState:
    """Validate, classify, route, and persist the single-slot bridge state."""
    try:
        envelope = parse_envelope(payload)
    except ResultValidationError as exc:
        raise CursorBridgeError(str(exc)) from exc
    routed = route_payload(payload)
    source_digest = source_result_digest(envelope)
    computed = route_digest(routed)
    status = (
        BridgeStatus.TERMINAL if routed.route_kind == RouteKind.TERMINAL else BridgeStatus.PENDING
    )
    new_state = CursorBridgeState(
        status=status,
        source_result_digest=source_digest,
        route_digest=computed,
        envelope=envelope,
        route=routed,
        followup_emitted=False,
    )
    existing = load_state(root)
    if existing is not None and existing.status == BridgeStatus.PENDING:
        if (
            existing.source_result_digest == new_state.source_result_digest
            and existing.route_digest == new_state.route_digest
        ):
            return existing
        raise PendingHandoffExists("PENDING_HANDOFF_EXISTS")
    persist_state(root, new_state)
    return new_state


def acknowledge(route_digest_value: str, *, root: Path) -> CursorBridgeState:
    """Mark a pending handoff acknowledged. Acknowledgement is not authority."""
    if not _DIGEST_RE.fullmatch(route_digest_value):
        raise BridgeAckError("acknowledgement digest is not a SHA-256 hex digest")
    existing = load_state(root)
    if existing is None:
        raise BridgeAckError("no pending Cursor bridge state")
    if existing.route_digest != route_digest_value:
        raise BridgeAckError("acknowledgement digest does not match pending route")
    if existing.status == BridgeStatus.ACKNOWLEDGED:
        return existing
    if existing.status != BridgeStatus.PENDING:
        raise BridgeAckError("bridge state is not pending")
    verified = verify_state(existing)
    if verified is None:
        raise BridgeAckError("pending bridge state failed recomputation")
    updated = verified.model_copy(update={"status": BridgeStatus.ACKNOWLEDGED})
    persist_state(root, updated)
    return updated


def handle_stop_event(payload: object, *, root: Path) -> dict[str, str]:
    """Pure Atlas reaction to a Cursor stop event. Cursor cannot choose the route."""
    try:
        event = CursorStopEvent.model_validate(payload)
    except ValidationError:
        return {}
    if event.status != COMPLETED_STATUS:
        return {}
    if event.loop_count >= 1:
        return {}
    existing = load_state(root)
    if existing is None:
        return {}
    verified = verify_state(existing)
    if verified is None:
        return {}
    if verified.status != BridgeStatus.PENDING:
        return {}
    if verified.followup_emitted:
        return {}
    if verified.route.route_kind == RouteKind.TERMINAL:
        return {}
    message = render_followup(verified)
    if message is None:
        return {}
    persist_state(root, verified.model_copy(update={"followup_emitted": True}))
    return CursorBridgeResponse(followup_message=message).to_stdout_dict()


def render_followup(state: CursorBridgeState) -> str | None:
    """Fixed trusted template. Untrusted envelope text never interpolates."""
    route = state.route
    if not _privileges_closed(route):
        return None
    digest = state.route_digest
    if not _DIGEST_RE.fullmatch(digest):
        return None
    if route.route_kind == RouteKind.OWNER_GATE:
        return (
            f"{BRIDGE_MARKER}\n"
            "\n"
            "Atlas reached an OWNER_REQUIRED gate.\n"
            "\n"
            f"Route digest: {digest}\n"
            "\n"
            "Acknowledge the bridge state and return the structured owner-gate packet.\n"
            "Do not execute or simulate the privileged action.\n"
        )
    if route.route_kind == RouteKind.TASK:
        task_id = state.envelope.task.id
        role = route.target.role.value if route.target.role is not None else None
        task_type = route.task_type.value if route.task_type is not None else None
        if role is None or task_type is None or not _TASK_ID_RE.fullmatch(task_id):
            return None
        return (
            f"{BRIDGE_MARKER}\n"
            "\n"
            "Atlas produced a governed next-task handoff.\n"
            "\n"
            f"Task: {task_id}\n"
            f"Target role: {role}\n"
            f"Task type: {task_type}\n"
            f"Route digest: {digest}\n"
            "\n"
            "Runtime dispatch is not implemented.\n"
            "\n"
            "Do NOT perform the target task.\n"
            "Acknowledge this handoff through Atlas and return the structured "
            "HANDOFF_READY packet only.\n"
        )
    return None


def handoff_packet(state: CursorBridgeState) -> dict[str, object]:
    """Machine-readable packet contract for the current session. Not a prompt."""
    route = state.route
    base: dict[str, object] = {
        "route_digest": state.route_digest,
        "dispatch_performed": False,
        "execution_authorized": False,
    }
    if route.route_kind == RouteKind.OWNER_GATE:
        return {"state": "OWNER_REQUIRED", **base}
    if route.route_kind == RouteKind.TASK:
        role = route.target.role.value if route.target.role is not None else None
        task_type = route.task_type.value if route.task_type is not None else None
        return {
            "state": "HANDOFF_READY",
            "source_task": state.envelope.task.id,
            "target_role": role,
            "task_type": task_type,
            **base,
        }
    return {"state": "TERMINAL", **base}


def verify_state(state: CursorBridgeState) -> CursorBridgeState | None:
    """Recompute 001A/001B from the stored envelope. Reject tampered state."""
    try:
        envelope = parse_envelope(state.envelope.model_dump(mode="json"))
        routed = route_payload(state.envelope.model_dump(mode="json"))
    except (ResultValidationError, ValidationError, ValueError):
        return None
    expected_source = source_result_digest(envelope)
    expected_route = route_digest(routed)
    if state.source_result_digest != expected_source:
        return None
    if state.route_digest != expected_route:
        return None
    if routed.model_dump(mode="json") != state.route.model_dump(mode="json"):
        return None
    if not _privileges_closed(routed) or not _privileges_closed(state.route):
        return None
    identity = state.model_dump(mode="json")
    if identity.get("policy_id") != POLICY_ID or identity.get("policy_version") != POLICY_VERSION:
        return None
    return state.model_copy(update={"envelope": envelope, "route": routed})


def load_state(root: Path) -> CursorBridgeState | None:
    path = bridge_state_path(root)
    if not path.is_file():
        return None
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return CursorBridgeState.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError):
        return None


def persist_state(root: Path, state: CursorBridgeState) -> None:
    path = bridge_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.model_dump(mode="json"), sort_keys=True, indent=2)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, path)


def status_report(root: Path) -> dict[str, object]:
    """Read-only Cursor bridge diagnostics. No secrets."""
    resolved = resolve_repo_root(root)
    existing = load_state(resolved)
    verified = verify_state(existing) if existing is not None else None
    role = None
    task_type = None
    route_kind = None
    if verified is not None:
        route_kind = verified.route.route_kind.value
        role = verified.route.target.role.value if verified.route.target.role else None
        task_type = verified.route.task_type.value if verified.route.task_type else None
    return {
        "package_id": PACKAGE_ID,
        "bridge_configured": (resolved / HOOK_CONFIG_RELATIVE).is_file(),
        "hook_config_found": (resolved / HOOK_CONFIG_RELATIVE).is_file(),
        "hook_entrypoint_found": (resolved / HOOK_ENTRY_RELATIVE).is_file(),
        "state": existing.status.value if existing is not None else "absent",
        "state_valid": verified is not None,
        "source_result_digest": existing.source_result_digest if existing else None,
        "route_digest": existing.route_digest if existing else None,
        "route_kind": route_kind,
        "target_role": role,
        "task_type": task_type,
        "followup_emitted": existing.followup_emitted if existing else False,
        "execution_authorized": False,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "handoff_packet": handoff_packet(verified) if verified is not None else None,
    }


def run_cursor_stage_result(
    *,
    path: Path | None,
    from_stdin: bool,
    stdin: TextIO,
    root: Path,
) -> tuple[dict[str, object], int]:
    try:
        raw = read_result_source(path=path, from_stdin=from_stdin, stdin=stdin)
        payload = load_result_bytes(raw)
        state = stage_result(payload, root=root)
    except PendingHandoffExists as exc:
        return {"ok": False, "error": exc.code, "execution_authorized": False}, 1
    except (ResultValidationError, CursorBridgeError, OSError, ValidationError) as exc:
        return {"ok": False, "error": str(exc), "execution_authorized": False}, 1
    return _public_state(state, ok=True), 0


def run_cursor_ack(*, route_digest_value: str, root: Path) -> tuple[dict[str, object], int]:
    try:
        state = acknowledge(route_digest_value, root=root)
    except (BridgeAckError, CursorBridgeError) as exc:
        code = getattr(exc, "code", "BRIDGE_ACK_REJECTED")
        return {"ok": False, "error": code, "execution_authorized": False}, 1
    return _public_state(state, ok=True), 0


def run_cursor_status(*, root: Path) -> tuple[dict[str, object], int]:
    try:
        return status_report(root), 0
    except CursorBridgeError as exc:
        return {"ok": False, "error": str(exc), "execution_authorized": False}, 1


def _public_state(state: CursorBridgeState, *, ok: bool) -> dict[str, object]:
    role = state.route.target.role.value if state.route.target.role is not None else None
    task_type = state.route.task_type.value if state.route.task_type is not None else None
    return {
        "ok": ok,
        "package_id": PACKAGE_ID,
        "status": state.status.value,
        "source_result_digest": state.source_result_digest,
        "route_digest": state.route_digest,
        "route_kind": state.route.route_kind.value,
        "target_role": role,
        "task_type": task_type,
        "followup_emitted": state.followup_emitted,
        "execution_authorized": False,
        "policy_id": state.policy_id,
        "policy_version": state.policy_version,
        "handoff_packet": handoff_packet(state),
    }
