"""AS-STUDIO-A2-006 — coherent mission session continuity packet.

MISSION_SESSION = PROJECTION (not authority)
Composes A2-002 journey pointers + A2-004 evidence + A2-005 continuity.
Does not mint intents, execute claims, or import #786 task_context (dependency
state UNAVAILABLE until that module is present on the stack).

Binding: intent_id / repository must agree across records or MISMATCHED_BINDING.
Uncertain mutations stay uncertain. AUTO_RETRY = FORBIDDEN.
PERSISTENCE_FAILED_SIGNAL is an operator-supplied flag when mutation may have
occurred but decision file write failed — never invents mutation success.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATTENTION_NE_AUTHORIZATION,
    GRANTS_NO_MUTATION,
    STALE_NE_CURRENT,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
)
from atlas_studio.action_evidence import (
    CONFIRMED_SUCCESS,
    FAILED_UNCERTAIN,
    PENDING_EXECUTE,
    REFUSED,
    UNAVAILABLE as EVIDENCE_UNAVAILABLE_CLASS,
    build_action_evidence,
    classify_decision,
)
from atlas_studio.intent_continuity import (
    ALREADY_DECIDED,
    DUPLICATE_SUBMIT_RISK,
    FRESH,
    INTERRUPTED_UNCERTAIN,
    MISMATCHED_BINDING,
    MISSING,
    STALE_INTENT,
    build_intent_continuity,
)
from atlas_studio.snapshot import utcnow, validator_for

SCHEMA_CONST = "ATLAS_STUDIO_MISSION_SESSION_V1"
SCHEMA_FILE = "atlas_studio_mission_session_v1.schema.json"
PACKAGE_ID = "AS-STUDIO-A2-006"

READY_TO_EVALUATE = "READY_TO_EVALUATE"
SESSION_PENDING_EXECUTE = "PENDING_EXECUTE"
SESSION_CONFIRMED_SUCCESS = "CONFIRMED_SUCCESS"
SESSION_REFUSED = "REFUSED"
SESSION_FAILED_UNCERTAIN = "FAILED_UNCERTAIN"
SESSION_STALE_INTENT = "STALE_INTENT"
SESSION_MISMATCHED_BINDING = "MISMATCHED_BINDING"
SESSION_DECISION_MISSING = "DECISION_MISSING"
SESSION_EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
SESSION_PERSISTENCE_FAILED_SIGNAL = "PERSISTENCE_FAILED_SIGNAL"
SESSION_INTERRUPTED_ATOMIC_WRITE = "INTERRUPTED_ATOMIC_WRITE"
SESSION_INCOMPLETE = "INCOMPLETE"
SESSION_UNAVAILABLE = "UNAVAILABLE"


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "session_ne_authority": True,
        "auto_retry_forbidden": True,
        "monitor_ne_reexecute": True,
        "uncertain_mutation_ne_nothing_changed": True,
        "persistence_failed_ne_confirmed_success": True,
        "knowledge_ne_permission": True,
        "task_context_dependency_explicit": True,
        "formal_iv_tip_ne_later_tip": True,
    }


def validate_mission_session(packet: dict) -> list[str]:
    validator = validator_for(SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _task_context_dependency() -> dict[str, Any]:
    """Consume #786 contract only if module is importable; else explicit UNAVAILABLE."""
    try:
        import atlas_studio.task_context as tc  # type: ignore[import-not-found]

        return {
            "package": "AS-STUDIO-A2-003",
            "state": "AVAILABLE",
            "schema": getattr(tc, "SCHEMA_CONST", "ATLAS_STUDIO_TASK_CONTEXT_V1"),
            "ownership": "PR_786",
            "built_here": False,
            "notes": ["module importable; journey may call separately"],
        }
    except ImportError:
        return {
            "package": "AS-STUDIO-A2-003",
            "state": "UNAVAILABLE",
            "schema": "ATLAS_STUDIO_TASK_CONTEXT_V1",
            "ownership": "PR_786_DRAFT",
            "built_here": False,
            "command": (
                "atlas-studio task-context --lane <lane> --agent <agent> --repo <owner/name>"
            ),
            "notes": [
                "task_context module not on this stack",
                "do not invent lane knowledge; show dependency explicitly",
            ],
        }


def _derive_session_state(
    *,
    continuity_state: str,
    outcome_class: str | None,
    persistence_failed_after_mutation: bool,
    interrupted_atomic_write: bool,
    has_intent: bool,
    has_decision: bool,
) -> str:
    if persistence_failed_after_mutation:
        return SESSION_PERSISTENCE_FAILED_SIGNAL
    if interrupted_atomic_write:
        return SESSION_INTERRUPTED_ATOMIC_WRITE
    if continuity_state == MISMATCHED_BINDING:
        return SESSION_MISMATCHED_BINDING
    if continuity_state == STALE_INTENT:
        return SESSION_STALE_INTENT
    if continuity_state == INTERRUPTED_UNCERTAIN or outcome_class == FAILED_UNCERTAIN:
        return SESSION_FAILED_UNCERTAIN
    if continuity_state == MISSING or not has_intent:
        return SESSION_UNAVAILABLE if not has_intent else SESSION_INCOMPLETE
    if continuity_state in {ALREADY_DECIDED, DUPLICATE_SUBMIT_RISK} or outcome_class == CONFIRMED_SUCCESS:
        if outcome_class == CONFIRMED_SUCCESS:
            return SESSION_CONFIRMED_SUCCESS
        if outcome_class == REFUSED:
            return SESSION_REFUSED
        if outcome_class == PENDING_EXECUTE:
            return SESSION_PENDING_EXECUTE
        if continuity_state == DUPLICATE_SUBMIT_RISK:
            return SESSION_PENDING_EXECUTE
        return SESSION_CONFIRMED_SUCCESS if outcome_class == CONFIRMED_SUCCESS else SESSION_REFUSED
    if not has_decision:
        if continuity_state == FRESH:
            return READY_TO_EVALUATE
        return SESSION_DECISION_MISSING
    if outcome_class in {None, EVIDENCE_UNAVAILABLE_CLASS}:
        return SESSION_EVIDENCE_UNAVAILABLE
    if outcome_class == REFUSED:
        return SESSION_REFUSED
    if outcome_class == PENDING_EXECUTE:
        return SESSION_PENDING_EXECUTE
    if outcome_class == CONFIRMED_SUCCESS:
        return SESSION_CONFIRMED_SUCCESS
    return SESSION_INCOMPLETE


def build_mission_session(
    *,
    intent: dict[str, Any] | None = None,
    intent_file: Path | str | None = None,
    decision: dict[str, Any] | None = None,
    decision_file: Path | str | None = None,
    evidence: dict[str, Any] | None = None,
    evidence_file: Path | str | None = None,
    journey: dict[str, Any] | None = None,
    persistence_failed_after_mutation: bool = False,
    expected_repository: str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build ATLAS_STUDIO_MISSION_SESSION_V1. Never mutates; never re-executes."""
    notes = [f"package:{PACKAGE_ID}", "session_ne_authority", "auto_retry_forbidden"]

    interrupted_atomic_write = False
    if decision_file is not None:
        dpath = Path(decision_file)
        tmp_sibling = dpath.with_suffix(dpath.suffix + ".tmp")
        if tmp_sibling.is_file() and not dpath.is_file():
            interrupted_atomic_write = True
            notes.append(f"orphan_tmp:{tmp_sibling}")

    continuity = build_intent_continuity(
        intent=intent,
        intent_file=intent_file,
        decision=decision,
        decision_file=decision_file,
        evidence=evidence,
        evidence_file=evidence_file,
        clock=clock,
    )
    loaded_intent = continuity.get("intent")
    loaded_decision = continuity.get("prior_decision")
    loaded_evidence_packet = continuity.get("prior_evidence")

    if loaded_evidence_packet is None and loaded_decision is not None:
        evidence_packet = build_action_evidence(decision=loaded_decision, clock=clock)
        notes.append("evidence_derived_from_decision")
    elif loaded_evidence_packet is not None:
        evidence_packet = loaded_evidence_packet
        notes.append("evidence_injected_or_loaded")
    else:
        evidence_packet = build_action_evidence(decision=None, clock=clock)
        notes.append("evidence_unavailable")

    outcome_class = evidence_packet.get("outcome_class")
    continuity_state = str(continuity.get("continuity_state"))

    # Repository binding across intent / decision / journey
    intent_repo = None
    if isinstance(loaded_intent, dict):
        intent_repo = loaded_intent.get("repository") or loaded_intent.get("target_repo")
    decision_repo = None
    if isinstance(loaded_decision, dict):
        ev = loaded_decision.get("evidence") or {}
        decision_repo = (
            loaded_decision.get("repository")
            or (ev.get("repo") if isinstance(ev, dict) else None)
        )
    journey_repo = (journey or {}).get("repository") if isinstance(journey, dict) else None
    expected = expected_repository or journey_repo or intent_repo
    binding_ok = True
    binding_notes: list[str] = []
    for label, value in (
        ("intent", intent_repo),
        ("decision", decision_repo),
        ("journey", journey_repo),
    ):
        if expected and value and value != expected:
            binding_ok = False
            binding_notes.append(f"REPO_MISMATCH:{label}:{value}!={expected}")
    if not binding_ok and continuity_state != MISMATCHED_BINDING:
        # Elevate to mismatched when repos disagree even if intent_ids match.
        continuity_state = MISMATCHED_BINDING
        notes.extend(binding_notes)

    session_state = _derive_session_state(
        continuity_state=continuity_state,
        outcome_class=str(outcome_class) if outcome_class else None,
        persistence_failed_after_mutation=persistence_failed_after_mutation,
        interrupted_atomic_write=interrupted_atomic_write,
        has_intent=isinstance(loaded_intent, dict),
        has_decision=isinstance(loaded_decision, dict),
    )

    recovery_actions = list((continuity.get("recovery") or {}).get("actions") or [])
    evidence_actions = list((evidence_packet.get("recovery") or {}).get("actions") or [])
    # Prefer continuity actions; append evidence actions with distinct ids.
    seen = {a.get("id") for a in recovery_actions if isinstance(a, dict)}
    for action in evidence_actions:
        if isinstance(action, dict) and action.get("id") not in seen:
            recovery_actions.append(action)
            seen.add(action.get("id"))
    if interrupted_atomic_write:
        recovery_actions.insert(
            0,
            {
                "id": "interrupted_atomic_write",
                "summary": (
                    "Found decision.json.tmp without final decision.json — treat write as "
                    "interrupted; inspect control plane before any retry; do not assume success"
                ),
            },
        )
    if persistence_failed_after_mutation:
        recovery_actions.insert(
            0,
            {
                "id": "persistence_failed_after_possible_mutation",
                "summary": (
                    "Decision file was not persisted after a possible mutation — "
                    "inspect control plane; do NOT re-execute; do NOT assume success"
                ),
            },
        )

    intent_id = (loaded_intent or {}).get("intent_id") if isinstance(loaded_intent, dict) else None
    resume = {
        "intent_id": intent_id,
        "repository": expected,
        "session_state": session_state,
        "commands": {
            "mission_session": (
                "atlas-studio mission-session "
                "--intent-file <intent.json> "
                "[--decision-file <decision.json>] [--json]"
            ),
            "action_evidence": (
                "atlas-studio action-evidence --decision-file <decision.json> [--json]"
            ),
            "intent_continuity": (
                "atlas-studio intent-continuity --intent-file <intent.json> "
                "[--decision-file <decision.json>] [--json]"
            ),
            "mission_journey": "atlas-studio mission-journey [--json]",
        },
        "do_not": [
            "auto-retry claim-execute",
            "treat MISMATCHED_BINDING as success",
            "treat PERSISTENCE_FAILED_SIGNAL as confirmed mutation",
            "treat uncertain mutation as nothing-changed",
        ],
        "notes": [
            "RESUME_NE_REEXECUTE",
            "another process loads the same files and re-derives this packet",
        ],
    }

    packet: dict[str, Any] = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "session_state": session_state,
        "binding": {
            "intent_id": intent_id,
            "expected_repository": expected,
            "intent_repository": intent_repo,
            "decision_repository": decision_repo,
            "journey_repository": journey_repo,
            "binding_ok": binding_ok and continuity_state != MISMATCHED_BINDING,
            "notes": binding_notes,
        },
        "lifecycle": {
            "continuity": {
                "state": continuity.get("continuity_state"),
                "auto_retry": (continuity.get("recovery") or {}).get("auto_retry"),
            },
            "evidence": {
                "outcome_class": outcome_class,
                "decision": (loaded_decision or {}).get("decision")
                if isinstance(loaded_decision, dict)
                else None,
                "mutated": (loaded_decision or {}).get("mutated")
                if isinstance(loaded_decision, dict)
                else None,
            },
            "journey": {
                "present": journey is not None,
                "mission_status": ((journey or {}).get("mission") or {}).get("mission_status")
                if isinstance(journey, dict)
                else None,
            },
            "persistence_failed_after_mutation": persistence_failed_after_mutation,
            "interrupted_atomic_write": interrupted_atomic_write,
        },
        "dependencies": {
            "task_context": _task_context_dependency(),
            "a2_002_mission_journey": "REQUIRED_COMPOSITION",
            "a2_004_action_evidence": "REQUIRED_COMPOSITION",
            "a2_005_intent_continuity": "REQUIRED_COMPOSITION",
        },
        "recovery": {
            "actions": recovery_actions,
            "auto_retry": False,
            "notes": [
                "AUTO_RETRY=FORBIDDEN",
                "SESSION!=AUTHORITY",
                f"continuity_state={continuity.get('continuity_state')}",
                f"outcome_class={outcome_class}",
            ],
        },
        "resume": resume,
        "honesty": honesty_block(),
        "provenance": {
            "generator": "atlas-studio mission-session (AS-STUDIO-A2-006)",
            "presentation_only": True,
            "grants_no_mutation": True,
            "truth_sources": [
                "atlas_studio.intent_continuity.build_intent_continuity",
                "atlas_studio.action_evidence.build_action_evidence",
                "atlas_studio.mission_journey (optional inject)",
            ],
            "notes": notes,
            "session_fingerprint": None,
        },
    }
    material = {k: v for k, v in packet.items() if k != "provenance"}
    packet["provenance"]["session_fingerprint"] = _canonical_sha256(material)
    return packet


def format_mission_session_tui(packet: dict) -> str:
    binding = packet.get("binding") or {}
    lifecycle = packet.get("lifecycle") or {}
    recovery = packet.get("recovery") or {}
    deps = packet.get("dependencies") or {}
    tc = deps.get("task_context") or {}
    lines = [
        f"atlas-studio mission-session schema={packet.get('schema')}",
        f"session_state={packet.get('session_state')} "
        f"intent_id={binding.get('intent_id')} "
        f"binding_ok={binding.get('binding_ok')}",
        f"continuity={((lifecycle.get('continuity') or {}).get('state'))} "
        f"outcome={((lifecycle.get('evidence') or {}).get('outcome_class'))} "
        f"persistence_failed={lifecycle.get('persistence_failed_after_mutation')}",
        f"task_context={tc.get('state')} ownership={tc.get('ownership')}",
        f"auto_retry={recovery.get('auto_retry')}",
    ]
    for action in (recovery.get("actions") or [])[:6]:
        lines.append(f"  recovery: [{action.get('id')}] {action.get('summary')}")
    lines.append(
        "HONESTY: SESSION!=AUTHORITY / AUTO_RETRY=FORBIDDEN / "
        "PERSISTENCE_FAILED!=SUCCESS / UNCERTAIN!=NOTHING_CHANGED"
    )
    return "\n".join(lines)


# Re-export classify_decision for tests that probe outcome mapping.
__all__ = [
    "SCHEMA_CONST",
    "build_mission_session",
    "format_mission_session_tui",
    "honesty_block",
    "validate_mission_session",
    "classify_decision",
]
