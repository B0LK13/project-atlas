"""AS-STUDIO-A2 governance substrate — reusable governed-action loop.

MISSION CONTROL TRUTH → CANDIDATE → PREVIEW → INTENT
→ POLICY+AUTHORITY+FRESHNESS EVALUATION → CONTROL PLANE
→ EXECUTE|REFUSE → EVIDENCE

STUDIO_UI != AUTHORITY
REQUESTED != CLAIMED / EXECUTED
PREVIEW != EXECUTION
STALE_INTENT != CURRENT_PERMISSION
CAPABILITY != SELF_GRANTED_PERMISSION
CONTROL_PLANE_REVALIDATES_AT_EXECUTION
BUTTON != MUTATION

Action-specific packages (OWNERSHIP_CLAIM first) register handlers.
Studio never self-authorizes; handlers must revalidate at evaluate and
again at apply_authorized. Unknown action types fail closed.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from atlas_studio import (
    ATTENTION_NE_AUTHORIZATION,
    STALE_NE_CURRENT,
    STUDIO_UI_NE_AUTHORITY,
)

SCHEMA_INTENT = "ATLAS_STUDIO_ACTION_INTENT_V1"
SCHEMA_PREVIEW = "ATLAS_STUDIO_ACTION_PREVIEW_V1"
SCHEMA_DECISION = "ATLAS_STUDIO_ACTION_DECISION_V1"

# Decision vocabulary (shared across future actions).
EXECUTE_ALLOWED = "EXECUTE_ALLOWED"
EXECUTED = "EXECUTED"
REFUSED_STALE = "REFUSED_STALE"
REFUSED_ALREADY_OWNED = "REFUSED_ALREADY_OWNED"
REFUSED_NOT_RUNNABLE = "REFUSED_NOT_RUNNABLE"
REFUSED_AGENT_INVALID = "REFUSED_AGENT_INVALID"
REFUSED_CAPABILITY = "REFUSED_CAPABILITY"
REFUSED_POLICY = "REFUSED_POLICY"
REFUSED_TARGET_MISMATCH = "REFUSED_TARGET_MISMATCH"
REFUSED_IDEMPOTENT_ALREADY_CLAIMED = "REFUSED_IDEMPOTENT_ALREADY_CLAIMED"
REFUSED_SCHEMA = "REFUSED_SCHEMA"
REFUSED_UNSUPPORTED_ACTION = "REFUSED_UNSUPPORTED_ACTION"
EXECUTION_FAILED = "EXECUTION_FAILED"  # executor raised / returned no decision

FORBIDDEN_AUTHZ_FIELDS = frozenset(
    {
        "authorized",
        "permitted",
        "executable",
        "grants",
        "policy_pass",
        "authorization_granted",
        "authorization_required",
    }
)

REQUESTED_NE_CLAIMED = True
PREVIEW_NE_EXECUTION = True
CAPABILITY_CLAIMS_NE_AUTHORIZATION = True
GRANTS_NO_SELF_AUTHORIZATION = True
CONTROL_PLANE_REVALIDATES_AT_EXECUTION = True
STUDIO_NEVER_SELF_AUTHORIZES = True
STALE_INTENT_NE_CURRENT_PERMISSION = True
DISPATCH_STEAL_AUTO_NOT_STARTED = True
MERGE_HANDOFF_WORKTREE_NOT_STARTED = True
DRY_RUN_NE_EXECUTED = True
EXECUTION_FAILURE_NE_SUCCESS = True


class GovernanceError(RuntimeError):
    """Fail-closed governance substrate failure."""


def honesty_intent() -> dict[str, bool]:
    return {
        "requested_ne_claimed": REQUESTED_NE_CLAIMED,
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "capability_claims_ne_authorization": CAPABILITY_CLAIMS_NE_AUTHORIZATION,
        "grants_no_self_authorization": GRANTS_NO_SELF_AUTHORIZATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
    }


def honesty_preview() -> dict[str, bool]:
    return {
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "available_ne_authorized": True,
        "ranked_ne_eligible_to_execute": True,
    }


def honesty_decision() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "requested_ne_claimed": REQUESTED_NE_CLAIMED,
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "control_plane_revalidates_at_execution": CONTROL_PLANE_REVALIDATES_AT_EXECUTION,
        "studio_never_self_authorizes": STUDIO_NEVER_SELF_AUTHORIZES,
        "stale_intent_ne_current_permission": STALE_INTENT_NE_CURRENT_PERMISSION,
        "dry_run_ne_executed": DRY_RUN_NE_EXECUTED,
        "execution_failure_ne_success": EXECUTION_FAILURE_NE_SUCCESS,
    }


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def reject_authz_fields(payload: dict) -> list[str]:
    bad = sorted(k for k in payload if k in FORBIDDEN_AUTHZ_FIELDS)
    errors = [f"FORBIDDEN_AUTHZ_FIELD:{k}" for k in bad]
    if payload.get("executable") is True:
        errors.append("FORBIDDEN_AUTHZ_FIELD:executable=true")
    return errors


def check_intent_freshness(
    intent: dict[str, Any],
    *,
    now_utc: str,
) -> list[str]:
    """Return refusal reasons if intent exceeds max_age. Empty ⇒ age OK."""
    try:
        requested = parse_utc(str(intent["requested_at_utc"]))
        max_age = int(intent["max_age_seconds"])
        now_dt = parse_utc(now_utc)
    except (KeyError, TypeError, ValueError) as exc:
        return [f"TIMESTAMP_INVALID:{exc}"]
    if now_dt - requested > timedelta(seconds=max_age):
        return ["INTENT_MAX_AGE_EXCEEDED"]
    return []


def build_decision(
    decision: str,
    *,
    action_type: str,
    intent_id: str | None,
    reasons: list[str],
    evidence: dict[str, Any] | None = None,
    mutated: bool = False,
    dry_run: bool = False,
    emit_status: str | None = None,
    event_id: str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_DECISION,
        "decision": decision,
        "action_type": action_type,
        "intent_id": intent_id,
        "mutated": bool(mutated),
        "dry_run": bool(dry_run),
        "emit_status": emit_status,
        "event_id": event_id,
        "reasons": list(reasons),
        "evidence": dict(evidence or {}),
        "honesty": honesty_decision(),
        "evaluated_at_utc": clock(),
    }


class ActionHandler(Protocol):
    """Per-action adapter. Evaluate never mutates; apply_authorized only after ALLOWED."""

    action_type: str

    def evaluate(self, intent: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Return ATLAS_STUDIO_ACTION_DECISION_V1 (EXECUTE_ALLOWED or REFUSED_*)."""

    def apply_authorized(self, intent: dict[str, Any], decision: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Execute authoritative primitive; return EXECUTED or REFUSED_* decision."""


@dataclass
class RegisteredAction:
    action_type: str
    handler: ActionHandler
    status: str = "IMPLEMENTED"  # or NOT_STARTED for declared-but-absent
    notes: str = ""


_REGISTRY: dict[str, RegisteredAction] = {}


def register_action(handler: ActionHandler, *, notes: str = "") -> None:
    """Register an IMPLEMENTED handler. Fail closed on silent takeover.

    - A NOT_STARTED attach point may be promoted to IMPLEMENTED.
    - Re-registering the *same* handler object is idempotent.
    - Replacing an existing IMPLEMENTED handler with a different object
      always raises ``GovernanceError(DUPLICATE_REGISTRATION:...)``.
      There is no ``replace=True`` escape hatch in this package; a future
      audited replace operation would be a separate API if ever required.
    """
    action_type = str(handler.action_type)
    if not action_type:
        raise GovernanceError("handler.action_type required")
    existing = _REGISTRY.get(action_type)
    if existing is not None and existing.status == "IMPLEMENTED":
        if existing.handler is handler:
            return
        raise GovernanceError(f"DUPLICATE_REGISTRATION:{action_type}")
    _REGISTRY[action_type] = RegisteredAction(
        action_type=action_type, handler=handler, status="IMPLEMENTED", notes=notes
    )


def sanitize_executor_error(exc: BaseException) -> dict[str, str]:
    """Evidence-safe executor failure fields (type only; no secret-bearing body)."""
    return {
        "exception_type": type(exc).__name__,
        # Never persist raw exception text — messages may carry tokens/paths.
        "exception_message": f"{type(exc).__name__} (message redacted)",
    }


def declare_not_started(action_type: str, *, notes: str = "") -> None:
    """Document future attach points without enabling execution."""
    if action_type in _REGISTRY and _REGISTRY[action_type].status == "IMPLEMENTED":
        return
    _REGISTRY[action_type] = RegisteredAction(
        action_type=action_type,
        handler=_UnsupportedHandler(action_type),
        status="NOT_STARTED",
        notes=notes,
    )


class _UnsupportedHandler:
    def __init__(self, action_type: str) -> None:
        self.action_type = action_type

    def evaluate(self, intent: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return build_decision(
            REFUSED_UNSUPPORTED_ACTION,
            action_type=self.action_type,
            intent_id=intent.get("intent_id") if isinstance(intent, dict) else None,
            reasons=[f"ACTION_NOT_STARTED:{self.action_type}"],
            evidence={"registry_status": "NOT_STARTED"},
        )

    def apply_authorized(self, intent: dict[str, Any], decision: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.evaluate(intent, **kwargs)


def supported_actions() -> list[dict[str, str]]:
    return [
        {
            "action_type": r.action_type,
            "status": r.status,
            "notes": r.notes,
        }
        for r in sorted(_REGISTRY.values(), key=lambda x: x.action_type)
    ]


def get_handler(action_type: str) -> RegisteredAction | None:
    return _REGISTRY.get(action_type)


def evaluate_governed_intent(intent: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Substrate entry: reject authz fields, route to registered handler.evaluate."""
    if not isinstance(intent, dict):
        return build_decision(
            REFUSED_SCHEMA,
            action_type="UNKNOWN",
            intent_id=None,
            reasons=["INTENT_NOT_OBJECT"],
        )
    authz = reject_authz_fields(intent)
    if authz:
        return build_decision(
            REFUSED_SCHEMA,
            action_type=str(intent.get("action_type") or "UNKNOWN"),
            intent_id=intent.get("intent_id"),
            reasons=authz,
            evidence={"schema_errors": authz},
        )
    action_type = str(intent.get("action_type") or "")
    reg = _REGISTRY.get(action_type)
    if reg is None:
        return build_decision(
            REFUSED_UNSUPPORTED_ACTION,
            action_type=action_type or "UNKNOWN",
            intent_id=intent.get("intent_id"),
            reasons=[f"UNSUPPORTED_ACTION_TYPE:{action_type}"],
        )
    if reg.status != "IMPLEMENTED":
        return reg.handler.evaluate(intent, **kwargs)
    return reg.handler.evaluate(intent, **kwargs)


def execute_governed_intent(
    intent: dict[str, Any],
    *,
    dry_run: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Always evaluate first; apply_authorized only when EXECUTE_ALLOWED and not dry_run.

    dry_run with EXECUTE_ALLOWED returns EXECUTE_ALLOWED + dry_run=True +
    mutated=False (DRY_RUN != EXECUTED: nothing ran, the label must not say
    it did). An executor that raises, or returns something that is not a
    decision packet, yields EXECUTION_FAILED with mutation_state=UNKNOWN —
    never EXECUTED, never a bare exception without evidence.
    """
    decision = evaluate_governed_intent(intent, **kwargs)
    if decision.get("decision") != EXECUTE_ALLOWED:
        return decision
    action_type = str(intent.get("action_type") or decision.get("action_type") or "")
    reg = _REGISTRY.get(action_type)
    if reg is None or reg.status != "IMPLEMENTED":
        return build_decision(
            REFUSED_UNSUPPORTED_ACTION,
            action_type=action_type or "UNKNOWN",
            intent_id=intent.get("intent_id") if isinstance(intent, dict) else None,
            reasons=[f"UNSUPPORTED_ACTION_TYPE:{action_type}"],
        )
    if dry_run:
        return build_decision(
            EXECUTE_ALLOWED,
            action_type=action_type,
            intent_id=intent.get("intent_id"),
            reasons=["DRY_RUN_NO_EMIT"],
            evidence={
                **(decision.get("evidence") or {}),
                "evaluate_decision": EXECUTE_ALLOWED,
                "substrate": "atlas_studio.governance",
            },
            mutated=False,
            dry_run=True,
        )
    try:
        result = reg.handler.apply_authorized(intent, decision, **kwargs)
    except Exception as exc:
        # KeyboardInterrupt / SystemExit are BaseException, not Exception:
        # they must propagate (process-control != executor failure).
        sanitized = sanitize_executor_error(exc)
        try:
            return build_decision(
                EXECUTION_FAILED,
                action_type=action_type,
                intent_id=intent.get("intent_id"),
                reasons=[f"EXECUTOR_EXCEPTION:{sanitized['exception_type']}"],
                evidence={
                    "evaluate_decision": EXECUTE_ALLOWED,
                    **sanitized,
                    "mutation_state": "UNKNOWN",
                    "substrate": "atlas_studio.governance",
                },
                mutated=False,
                dry_run=False,
            )
        except Exception as evidence_exc:
            # Evidence construction failed after executor failure: do not claim
            # success, do not claim evidence was persisted, re-raise with both.
            raise GovernanceError(
                f"EVIDENCE_PERSISTENCE_FAILED_AFTER_EXECUTOR:"
                f"{sanitized['exception_type']}:"
                f"{type(evidence_exc).__name__}"
            ) from exc
    if not isinstance(result, dict) or not result.get("decision"):
        return build_decision(
            EXECUTION_FAILED,
            action_type=action_type,
            intent_id=intent.get("intent_id"),
            reasons=["EXECUTOR_RETURN_INVALID"],
            evidence={
                "evaluate_decision": EXECUTE_ALLOWED,
                "returned_type": type(result).__name__,
                "mutation_state": "UNKNOWN",
                "substrate": "atlas_studio.governance",
            },
            mutated=False,
            dry_run=False,
        )
    return result


def ensure_default_registry() -> None:
    """Idempotent: NOT_STARTED markers already declared at module load.

    Call after importing action handlers so IMPLEMENTED registrations win.
    """
    declare_not_started("CI_DISPATCH", notes="AS-STUDIO-A2-next; not this package")
    declare_not_started("IV_REQUEST", notes="AS-STUDIO-A2-next; not this package")
    declare_not_started("HANDOFF_DELIVER", notes="AS-STUDIO-A2-next; not this package")
    declare_not_started("STEAL_EXECUTE", notes="policy over claim; not auto-started")
    declare_not_started("MERGE", notes="not started")
    declare_not_started("WORKTREE_OPEN", notes="not started")


# Future attach points (overwritten when a handler registers IMPLEMENTED).
declare_not_started("CI_DISPATCH", notes="AS-STUDIO-A2-next; not this package")
declare_not_started("IV_REQUEST", notes="AS-STUDIO-A2-next; not this package")
declare_not_started("HANDOFF_DELIVER", notes="AS-STUDIO-A2-next; not this package")
declare_not_started("STEAL_EXECUTE", notes="policy over claim; not auto-started")
declare_not_started("MERGE", notes="not started")
declare_not_started("WORKTREE_OPEN", notes="not started")
