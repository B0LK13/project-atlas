"""AS-STUDIO-A2-005 — intent continuity / interrupted-session inspect.

STALE_INTENT != PERMISSION
DUPLICATE_SUBMIT_RISK != AUTO_RETRY
INSPECT != EXECUTE
INTERRUPTED != LOST_CONTEXT (evidence preserved when provided)
MONITOR != RE-EXECUTE

Read-only projection over an intent file plus optional prior decision /
action-evidence packets so operators can resume without duplicate effects.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATTENTION_NE_AUTHORIZATION,
    GRANTS_NO_MUTATION,
    STALE_NE_CURRENT,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
)
from atlas_studio.action_evidence import classify_decision
from atlas_studio.snapshot import utcnow, validator_for

SCHEMA_CONST = "ATLAS_STUDIO_INTENT_CONTINUITY_V1"
SCHEMA_FILE = "atlas_studio_intent_continuity_v1.schema.json"
INTENT_SCHEMA = "ATLAS_STUDIO_ACTION_INTENT_V1"

FRESH = "FRESH"
STALE_INTENT = "STALE_INTENT"
ALREADY_DECIDED = "ALREADY_DECIDED"
DUPLICATE_SUBMIT_RISK = "DUPLICATE_SUBMIT_RISK"
INTERRUPTED_UNCERTAIN = "INTERRUPTED_UNCERTAIN"
MISSING = "MISSING"
MALFORMED = "MALFORMED"


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "stale_intent_ne_permission": True,
        "duplicate_submit_ne_auto_retry": True,
        "inspect_ne_execute": True,
        "auto_retry_forbidden": True,
    }


def validate_intent_continuity(packet: dict) -> list[str]:
    validator = validator_for(SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _parse_utc(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_json_object(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"FILE_MISSING:{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("NOT_OBJECT")
    return data


def build_recovery(state: str, *, intent_id: str | None) -> dict[str, Any]:
    actions: list[dict[str, str]] = []
    notes = ["AUTO_RETRY=FORBIDDEN", "INSPECT!=EXECUTE"]
    if intent_id:
        notes.append(f"intent_id={intent_id}")

    if state == MISSING:
        actions.append(
            {
                "id": "mint_or_supply_intent",
                "summary": "Supply --intent-file or mint a fresh claim-intent",
            }
        )
    elif state == MALFORMED:
        actions.append(
            {
                "id": "fix_intent_json",
                "summary": "Repair intent JSON; do not execute malformed packets",
            }
        )
    elif state == FRESH:
        actions.append(
            {
                "id": "evaluate_then_optional_execute",
                "summary": (
                    "Run claim-evaluate; only claim-execute --repo when authorized "
                    "(Studio never self-authorizes)"
                ),
            }
        )
    elif state == STALE_INTENT:
        actions.append(
            {
                "id": "mint_fresh_intent",
                "summary": "Intent exceeded max_age; mint a fresh intent (stale!=permission)",
            }
        )
    elif state == ALREADY_DECIDED:
        actions.append(
            {
                "id": "inspect_action_evidence",
                "summary": "Use action-evidence on the prior decision; do not re-submit",
            }
        )
        actions.append(
            {
                "id": "refresh_mission",
                "summary": "Refresh mission-journey / mission-control for live ownership",
            }
        )
    elif state == DUPLICATE_SUBMIT_RISK:
        actions.append(
            {
                "id": "do_not_reexecute",
                "summary": "Prior decision exists for this intent_id; do not re-run claim-execute",
            }
        )
        actions.append(
            {
                "id": "reconcile_with_evidence",
                "summary": "Reconcile via action-evidence + control-plane inspection first",
            }
        )
    elif state == INTERRUPTED_UNCERTAIN:
        actions.append(
            {
                "id": "inspect_uncertain_mutation",
                "summary": (
                    "Prior EXECUTION_FAILED with UNKNOWN mutation — inspect control plane "
                    "before any fresh intent"
                ),
            }
        )
        actions.append(
            {
                "id": "do_not_auto_retry",
                "summary": "Do not auto-retry; duplicate effects risk",
            }
        )

    return {"actions": actions, "auto_retry": False, "notes": notes}


def classify_continuity(
    *,
    intent: dict[str, Any] | None,
    prior_decision: dict[str, Any] | None,
    prior_evidence: dict[str, Any] | None,
    now: datetime,
) -> str:
    if intent is None:
        return MISSING
    if not isinstance(intent, dict):
        return MALFORMED
    schema = intent.get("schema")
    if schema is not None and schema != INTENT_SCHEMA:
        return MALFORMED
    if not intent.get("intent_id") or not intent.get("action_type"):
        return MALFORMED

    intent_id = intent.get("intent_id")
    decision = prior_decision
    if decision is None and isinstance(prior_evidence, dict):
        decision = prior_evidence.get("decision")

    if isinstance(decision, dict) and decision.get("intent_id") == intent_id:
        outcome = classify_decision(decision)
        if outcome == "FAILED_UNCERTAIN":
            return INTERRUPTED_UNCERTAIN
        if outcome in {"CONFIRMED_SUCCESS", "REFUSED", "DRY_RUN", "PENDING_EXECUTE"}:
            # Any durable decision for this intent means do not re-submit blindly.
            if outcome == "PENDING_EXECUTE":
                return DUPLICATE_SUBMIT_RISK
            return ALREADY_DECIDED
        if outcome == "FAILED_CONFIRMED_NO_MUTATION":
            return ALREADY_DECIDED
        return DUPLICATE_SUBMIT_RISK

    requested = _parse_utc(intent.get("requested_at_utc") or intent.get("created_at_utc"))
    try:
        max_age = int(intent.get("max_age_seconds") or 0)
    except (TypeError, ValueError):
        max_age = 0
    if requested is not None and max_age > 0 and now - requested > timedelta(seconds=max_age):
        return STALE_INTENT
    return FRESH


def build_intent_continuity(
    *,
    intent: dict[str, Any] | None = None,
    intent_file: Path | str | None = None,
    decision: dict[str, Any] | None = None,
    decision_file: Path | str | None = None,
    evidence: dict[str, Any] | None = None,
    evidence_file: Path | str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build ATLAS_STUDIO_INTENT_CONTINUITY_V1. Never mutates."""
    notes = ["package:AS-STUDIO-A2-005", "inspect_ne_execute"]
    loaded_intent = intent
    if loaded_intent is None and intent_file is not None:
        try:
            loaded_intent = load_json_object(intent_file)
            notes.append(f"intent_loaded:{intent_file}")
        except FileNotFoundError:
            loaded_intent = None
            notes.append("INTENT_FILE_MISSING")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            loaded_intent = None
            notes.append(f"INTENT_LOAD_ERROR:{type(exc).__name__}")

    loaded_decision = decision
    if loaded_decision is None and decision_file is not None:
        try:
            loaded_decision = load_json_object(decision_file)
            notes.append(f"decision_loaded:{decision_file}")
        except FileNotFoundError:
            notes.append("DECISION_FILE_MISSING")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            notes.append(f"DECISION_LOAD_ERROR:{type(exc).__name__}")
            loaded_decision = None

    loaded_evidence = evidence
    if loaded_evidence is None and evidence_file is not None:
        try:
            loaded_evidence = load_json_object(evidence_file)
            notes.append(f"evidence_loaded:{evidence_file}")
        except FileNotFoundError:
            notes.append("EVIDENCE_FILE_MISSING")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            notes.append(f"EVIDENCE_LOAD_ERROR:{type(exc).__name__}")
            loaded_evidence = None

    now_s = clock()
    now_dt = _parse_utc(now_s) or datetime.now(tz=timezone.utc)
    state = classify_continuity(
        intent=loaded_intent,
        prior_decision=loaded_decision,
        prior_evidence=loaded_evidence,
        now=now_dt,
    )
    intent_id = (loaded_intent or {}).get("intent_id") if isinstance(loaded_intent, dict) else None
    recovery = build_recovery(state, intent_id=intent_id if isinstance(intent_id, str) else None)

    packet: dict[str, Any] = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": now_s,
        "continuity_state": state,
        "intent": loaded_intent,
        "prior_decision": loaded_decision,
        "prior_evidence": loaded_evidence,
        "recovery": recovery,
        "honesty": honesty_block(),
        "provenance": {
            "generator": "atlas-studio intent-continuity (AS-STUDIO-A2-005)",
            "presentation_only": True,
            "grants_no_mutation": True,
            "notes": notes,
            "continuity_fingerprint": None,
        },
    }
    material = {k: v for k, v in packet.items() if k != "provenance"}
    packet["provenance"]["continuity_fingerprint"] = _canonical_sha256(material)
    return packet


def format_intent_continuity_tui(packet: dict) -> str:
    intent = packet.get("intent") or {}
    recovery = packet.get("recovery") or {}
    lines = [
        f"atlas-studio intent-continuity schema={packet.get('schema')}",
        f"continuity_state={packet.get('continuity_state')} "
        f"intent_id={intent.get('intent_id')} "
        f"action_type={intent.get('action_type')}",
        f"auto_retry={recovery.get('auto_retry')}",
    ]
    for action in recovery.get("actions") or []:
        lines.append(f"  recovery: [{action.get('id')}] {action.get('summary')}")
    lines.append(
        "HONESTY: STALE_INTENT!=PERMISSION / DUPLICATE_SUBMIT!=AUTO_RETRY / "
        "INSPECT!=EXECUTE / AUTO_RETRY=FORBIDDEN"
    )
    return "\n".join(lines)
