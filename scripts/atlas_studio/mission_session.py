"""AS-STUDIO-A2-006 — coherent mission session continuity packet.

MISSION_SESSION = PROJECTION (not authority)
Composes A2-002 journey pointers + A2-004 evidence + A2-005 continuity.
Does not mint intents, execute claims, or import #786 task_context (dependency
state UNAVAILABLE until that module is present on the stack).

Binding: intent_id / repository / lane must agree across records or
MISMATCHED_BINDING. Uncertain mutations stay uncertain. AUTO_RETRY = FORBIDDEN.
PERSISTENCE_FAILED_SIGNAL never invents mutation success and never recommends
replay. Fingerprints are stable across wall-clock for unchanged inputs.
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
    DRY_RUN,
    FAILED_CONFIRMED_NO_MUTATION,
    FAILED_UNCERTAIN,
    MALFORMED as EVIDENCE_MALFORMED,
    PENDING_EXECUTE,
    REFUSED,
    UNAVAILABLE as EVIDENCE_UNAVAILABLE_CLASS,
    build_action_evidence,
)
from atlas_studio.intent_continuity import (
    ALREADY_DECIDED,
    CORRUPT as CONTINUITY_CORRUPT,
    DUPLICATE_SUBMIT_RISK,
    FRESH,
    INTERRUPTED_UNCERTAIN,
    MALFORMED as CONTINUITY_MALFORMED,
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
SESSION_DRY_RUN = "DRY_RUN"
SESSION_FAILED_UNCERTAIN = "FAILED_UNCERTAIN"
SESSION_FAILED_CONFIRMED_NO_MUTATION = "FAILED_CONFIRMED_NO_MUTATION"
SESSION_STALE_INTENT = "STALE_INTENT"
SESSION_MISMATCHED_BINDING = "MISMATCHED_BINDING"
SESSION_CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
SESSION_DECISION_MISSING = "DECISION_MISSING"
SESSION_EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
SESSION_PERSISTENCE_FAILED_SIGNAL = "PERSISTENCE_FAILED_SIGNAL"
SESSION_INTERRUPTED_ATOMIC_WRITE = "INTERRUPTED_ATOMIC_WRITE"
SESSION_CORRUPT_INPUT = "CORRUPT_INPUT"
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
        "persistence_failed_ne_replay": True,
        "fingerprint_stable_across_wall_clock": True,
        "knowledge_ne_permission": True,
        "task_context_dependency_explicit": True,
        "control_plane_observation_ne_invented": True,
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


def _control_plane_observation_dependency() -> dict[str, Any]:
    """No Studio-owned RO observation API for OWNER_CLAIMED in this lane.

    atlas_dag event bus exists, but Studio mission-session does not wrap a
    bounded reconciler here. Timeout/missing/unavailable must remain uncertain.
    """
    return {
        "state": "UNAVAILABLE",
        "api": "NONE_IN_MISSION_SESSION",
        "guidance": [
            "Inspect atlas_dag event bus / OWNER_CLAIMED for the lane before any fresh intent",
            "Timeout or missing observation != proof that no mutation occurred",
            "Do not auto-retry claim-execute",
        ],
        "notes": [
            "CONTROL_PLANE_OBSERVATION_API = UNAVAILABLE in this package",
            "UNCERTAIN stays UNCERTAIN until authoritative observation resolves it",
        ],
    }


def _extract_repo(obj: dict[str, Any] | None) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in ("repository", "target_repo", "expected_repo", "repo"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    evidence = obj.get("evidence")
    if isinstance(evidence, dict):
        for key in ("repository", "repo", "expected_repo"):
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_lane(obj: dict[str, Any] | None) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in ("target_lane", "lane"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    evidence = obj.get("evidence")
    if isinstance(evidence, dict):
        for key in ("target_lane", "lane"):
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _decisions_conflict(
    decision: dict[str, Any] | None, evidence_packet: dict[str, Any] | None
) -> bool:
    """True when separately supplied evidence contradicts the decision file."""
    if not isinstance(decision, dict) or not isinstance(evidence_packet, dict):
        return False
    embedded = evidence_packet.get("decision")
    if not isinstance(embedded, dict):
        return False
    # Same object identity / exact match → ok
    if embedded == decision:
        return False
    for key in ("intent_id", "decision", "mutated", "evaluated_at_utc"):
        left = decision.get(key)
        right = embedded.get(key)
        if left is not None and right is not None and left != right:
            return True
    return False


def _derive_session_state(
    *,
    continuity_state: str,
    outcome_class: str | None,
    persistence_failed_after_mutation: bool,
    interrupted_atomic_write: bool,
    conflicting_evidence: bool,
    has_intent: bool,
    has_decision: bool,
) -> str:
    if persistence_failed_after_mutation:
        return SESSION_PERSISTENCE_FAILED_SIGNAL
    if interrupted_atomic_write:
        return SESSION_INTERRUPTED_ATOMIC_WRITE
    if continuity_state == CONTINUITY_CORRUPT:
        return SESSION_CORRUPT_INPUT
    if continuity_state == MISMATCHED_BINDING:
        return SESSION_MISMATCHED_BINDING
    if conflicting_evidence:
        return SESSION_CONFLICTING_EVIDENCE
    if continuity_state == STALE_INTENT:
        return SESSION_STALE_INTENT
    if continuity_state == CONTINUITY_MALFORMED or outcome_class == EVIDENCE_MALFORMED:
        return SESSION_INCOMPLETE
    if continuity_state == MISSING or not has_intent:
        return SESSION_UNAVAILABLE if not has_intent else SESSION_INCOMPLETE
    if continuity_state == INTERRUPTED_UNCERTAIN or outcome_class == FAILED_UNCERTAIN:
        return SESSION_FAILED_UNCERTAIN
    if outcome_class == FAILED_CONFIRMED_NO_MUTATION:
        return SESSION_FAILED_CONFIRMED_NO_MUTATION
    if outcome_class == DRY_RUN:
        return SESSION_DRY_RUN
    if not has_decision:
        if continuity_state == FRESH:
            return READY_TO_EVALUATE
        return SESSION_DECISION_MISSING
    if outcome_class in {None, EVIDENCE_UNAVAILABLE_CLASS}:
        return SESSION_EVIDENCE_UNAVAILABLE
    # Success / refuse / pending only when continuity agrees the decision belongs here.
    if continuity_state == ALREADY_DECIDED:
        if outcome_class == CONFIRMED_SUCCESS:
            return SESSION_CONFIRMED_SUCCESS
        if outcome_class == REFUSED:
            return SESSION_REFUSED
        if outcome_class == PENDING_EXECUTE:
            return SESSION_PENDING_EXECUTE
        return SESSION_INCOMPLETE
    if continuity_state == DUPLICATE_SUBMIT_RISK:
        if outcome_class == PENDING_EXECUTE:
            return SESSION_PENDING_EXECUTE
        if outcome_class == CONFIRMED_SUCCESS:
            # Prior allow without execute — do not call it confirmed success.
            return SESSION_PENDING_EXECUTE
        return SESSION_INCOMPLETE
    if continuity_state == FRESH and outcome_class == CONFIRMED_SUCCESS:
        # Decision present but continuity still FRESH is inconsistent → incomplete.
        return SESSION_INCOMPLETE
    if outcome_class == REFUSED:
        return SESSION_REFUSED
    if outcome_class == PENDING_EXECUTE:
        return SESSION_PENDING_EXECUTE
    if outcome_class == CONFIRMED_SUCCESS:
        return SESSION_INCOMPLETE
    return SESSION_INCOMPLETE


def _fingerprint_material(packet: dict[str, Any]) -> dict[str, Any]:
    """Stable material: excludes wall-clock and free-text recovery notes."""
    recovery = packet.get("recovery") or {}
    action_ids = sorted(
        {
            str(a.get("id"))
            for a in (recovery.get("actions") or [])
            if isinstance(a, dict) and a.get("id")
        }
    )
    resume = packet.get("resume") or {}
    return {
        "schema": packet.get("schema"),
        "session_state": packet.get("session_state"),
        "binding": packet.get("binding"),
        "lifecycle": packet.get("lifecycle"),
        "dependencies": packet.get("dependencies"),
        "recovery": {
            "auto_retry": recovery.get("auto_retry"),
            "action_ids": action_ids,
        },
        "resume": {
            "intent_id": resume.get("intent_id"),
            "repository": resume.get("repository"),
            "session_state": resume.get("session_state"),
            "commands": resume.get("commands"),
            "do_not": resume.get("do_not"),
        },
        "honesty": packet.get("honesty"),
    }


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
    strict_schema: bool = False,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build ATLAS_STUDIO_MISSION_SESSION_V1. Never mutates; never re-executes."""
    notes = [f"package:{PACKAGE_ID}", "session_ne_authority", "auto_retry_forbidden"]
    if strict_schema:
        notes.append("strict_schema=true")

    interrupted_atomic_write = False
    orphan_tmp_with_final = False
    if decision_file is not None:
        dpath = Path(decision_file)
        tmp_sibling = dpath.with_suffix(dpath.suffix + ".tmp")
        if tmp_sibling.is_file() and not dpath.is_file():
            interrupted_atomic_write = True
            notes.append(f"orphan_tmp:{tmp_sibling}")
        elif tmp_sibling.is_file() and dpath.is_file():
            orphan_tmp_with_final = True
            notes.append(f"tmp_coexists_with_final:{tmp_sibling}")

    continuity = build_intent_continuity(
        intent=intent,
        intent_file=intent_file,
        decision=decision,
        decision_file=decision_file,
        evidence=evidence,
        evidence_file=evidence_file,
        clock=clock,
        strict_schema=strict_schema,
    )
    loaded_intent = continuity.get("intent")
    loaded_decision = continuity.get("prior_decision")
    loaded_evidence_packet = continuity.get("prior_evidence")

    # Point-in-time hashes: prefer byte hashes of files actually parsed.
    input_hashes: dict[str, str] = {}
    byte_hashes = (continuity.get("provenance") or {}).get("input_byte_hashes") or {}
    if isinstance(byte_hashes, dict):
        input_hashes.update({k: str(v) for k, v in byte_hashes.items() if v})
    if isinstance(loaded_intent, dict) and "intent" not in input_hashes:
        input_hashes["intent_canonical"] = _canonical_sha256(loaded_intent)
    if isinstance(loaded_decision, dict) and "decision" not in input_hashes:
        input_hashes["decision_canonical"] = _canonical_sha256(loaded_decision)
    if isinstance(loaded_evidence_packet, dict) and "evidence" not in input_hashes:
        input_hashes["evidence_canonical"] = _canonical_sha256(loaded_evidence_packet)
    notes.append(
        "input_byte_hashes_identify_parsed_bytes;"
        "multi_file_consistency_is_binding_checks_not_a_single_fs_snapshot"
    )

    conflicting_evidence = False
    if loaded_evidence_packet is None and loaded_decision is not None:
        evidence_packet = build_action_evidence(decision=loaded_decision, clock=clock)
        notes.append("evidence_derived_from_decision")
    elif loaded_evidence_packet is not None:
        evidence_packet = loaded_evidence_packet
        notes.append("evidence_injected_or_loaded")
        if loaded_decision is not None and _decisions_conflict(
            loaded_decision, evidence_packet
        ):
            conflicting_evidence = True
            notes.append("EVIDENCE_CONFLICTS_WITH_DECISION")
    else:
        evidence_packet = build_action_evidence(decision=None, clock=clock)
        notes.append("evidence_unavailable")

    outcome_class = evidence_packet.get("outcome_class")
    continuity_state = str(continuity.get("continuity_state"))

    intent_repo = _extract_repo(loaded_intent if isinstance(loaded_intent, dict) else None)
    decision_repo = _extract_repo(
        loaded_decision if isinstance(loaded_decision, dict) else None
    )
    journey_repo = _extract_repo(journey if isinstance(journey, dict) else None)
    intent_lane = _extract_lane(loaded_intent if isinstance(loaded_intent, dict) else None)
    decision_lane = _extract_lane(
        loaded_decision if isinstance(loaded_decision, dict) else None
    )

    expected = expected_repository or journey_repo or intent_repo or decision_repo
    binding_ok = True
    binding_notes: list[str] = []
    present_repos = {
        label: value
        for label, value in (
            ("intent", intent_repo),
            ("decision", decision_repo),
            ("journey", journey_repo),
        )
        if value
    }
    if expected_repository:
        # Fail closed: explicit --repo must be verified against artifacts.
        if not present_repos:
            binding_ok = False
            binding_notes.append("REPO_UNVERIFIED_IN_ARTIFACTS")
        else:
            for label, value in present_repos.items():
                if value != expected_repository:
                    binding_ok = False
                    binding_notes.append(f"REPO_MISMATCH:{label}:{value}!={expected_repository}")
        expected = expected_repository
    else:
        for label, value in present_repos.items():
            if expected and value != expected:
                binding_ok = False
                binding_notes.append(f"REPO_MISMATCH:{label}:{value}!={expected}")

    if intent_lane and decision_lane and intent_lane != decision_lane:
        binding_ok = False
        binding_notes.append(f"LANE_MISMATCH:{intent_lane}!={decision_lane}")

    if not binding_ok and continuity_state != MISMATCHED_BINDING:
        continuity_state = MISMATCHED_BINDING
        notes.extend(binding_notes)

    session_state = _derive_session_state(
        continuity_state=continuity_state,
        outcome_class=str(outcome_class) if outcome_class else None,
        persistence_failed_after_mutation=persistence_failed_after_mutation,
        interrupted_atomic_write=interrupted_atomic_write,
        conflicting_evidence=conflicting_evidence,
        has_intent=isinstance(loaded_intent, dict),
        has_decision=isinstance(loaded_decision, dict),
    )

    recovery_actions = list((continuity.get("recovery") or {}).get("actions") or [])
    evidence_actions = list((evidence_packet.get("recovery") or {}).get("actions") or [])
    seen = {a.get("id") for a in recovery_actions if isinstance(a, dict)}
    for action in evidence_actions:
        if isinstance(action, dict) and action.get("id") not in seen:
            recovery_actions.append(action)
            seen.add(action.get("id"))
    if orphan_tmp_with_final:
        recovery_actions.insert(
            0,
            {
                "id": "tmp_coexists_with_final",
                "summary": (
                    "decision.json.tmp coexists with final decision.json — prefer the final "
                    "file; do not promote tmp; inspect if contents disagree"
                ),
            },
        )
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
                    "inspect control plane; do NOT re-execute / replay claim-execute; "
                    "do NOT assume success"
                ),
            },
        )
    if conflicting_evidence:
        recovery_actions.insert(
            0,
            {
                "id": "conflicting_evidence",
                "summary": (
                    "Evidence packet contradicts decision file (shared intent_id, different "
                    "attempt fields) — do not treat as confirmed success; do not replay"
                ),
            },
        )
    if session_state == SESSION_CORRUPT_INPUT:
        recovery_actions.insert(
            0,
            {
                "id": "corrupt_input",
                "summary": (
                    "Corrupt/truncated JSON among intent/decision/evidence — replace from "
                    "known-good source; do not execute"
                ),
            },
        )

    # Strip any recovery text that could be read as replay permission.
    for action in recovery_actions:
        if not isinstance(action, dict):
            continue
        summary = str(action.get("summary") or "").lower()
        if "re-run claim-execute" in summary or "replay claim-execute" in summary:
            action["summary"] = (
                "Inspect control plane / event bus; mint a fresh intent only after "
                "authoritative observation (AUTO_RETRY=FORBIDDEN)"
            )

    intent_id = (loaded_intent or {}).get("intent_id") if isinstance(loaded_intent, dict) else None
    resume = {
        "intent_id": intent_id,
        "repository": expected,
        "lane": intent_lane or decision_lane,
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
            "replay claim-execute after PERSISTENCE_FAILED_SIGNAL",
            "treat MISMATCHED_BINDING as success",
            "treat PERSISTENCE_FAILED_SIGNAL as confirmed mutation",
            "treat CONFLICTING_EVIDENCE as confirmed success",
            "treat uncertain mutation as nothing-changed",
            "promote decision.json.tmp to authoritative success",
        ],
        "notes": [
            "RESUME_NE_REEXECUTE",
            "another process loads the same files and re-derives this packet",
            "fingerprint excludes generated_at_utc",
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
            "intent_lane": intent_lane,
            "decision_lane": decision_lane,
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
                "conflicting_with_decision_file": conflicting_evidence,
            },
            "journey": {
                "present": journey is not None,
                "mission_status": ((journey or {}).get("mission") or {}).get("mission_status")
                if isinstance(journey, dict)
                else None,
            },
            "persistence_failed_after_mutation": persistence_failed_after_mutation,
            "interrupted_atomic_write": interrupted_atomic_write,
            "orphan_tmp_with_final": orphan_tmp_with_final,
        },
        "dependencies": {
            "task_context": _task_context_dependency(),
            "control_plane_observation": _control_plane_observation_dependency(),
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
                "REPLAY_FORBIDDEN",
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
            "input_content_hashes": input_hashes,
            "session_fingerprint": None,
        },
    }
    packet["provenance"]["session_fingerprint"] = _canonical_sha256(
        _fingerprint_material(packet)
    )
    return packet


def format_mission_session_tui(packet: dict) -> str:
    binding = packet.get("binding") or {}
    lifecycle = packet.get("lifecycle") or {}
    recovery = packet.get("recovery") or {}
    deps = packet.get("dependencies") or {}
    tc = deps.get("task_context") or {}
    obs = deps.get("control_plane_observation") or {}
    lines = [
        f"atlas-studio mission-session schema={packet.get('schema')}",
        f"session_state={packet.get('session_state')} "
        f"intent_id={binding.get('intent_id')} "
        f"binding_ok={binding.get('binding_ok')}",
        f"continuity={((lifecycle.get('continuity') or {}).get('state'))} "
        f"outcome={((lifecycle.get('evidence') or {}).get('outcome_class'))} "
        f"persistence_failed={lifecycle.get('persistence_failed_after_mutation')}",
        f"task_context={tc.get('state')} observation={obs.get('state')}",
        f"auto_retry={recovery.get('auto_retry')}",
    ]
    for action in (recovery.get("actions") or [])[:6]:
        lines.append(f"  recovery: [{action.get('id')}] {action.get('summary')}")
    lines.append(
        "HONESTY: SESSION!=AUTHORITY / AUTO_RETRY=FORBIDDEN / "
        "PERSISTENCE_FAILED!=SUCCESS / UNCERTAIN!=NOTHING_CHANGED / "
        "FINGERPRINT_STABLE"
    )
    return "\n".join(lines)


def exit_code_for_session(packet: dict) -> int:
    """CLI exit codes for mission-session (inspect-only; never mutation).

    0 — clear terminal inspect outcomes / ready-to-evaluate
    1 — recovery / uncertainty / mismatch / incomplete
    3 — persistence interrupted or failed after possible mutation
    """
    state = packet.get("session_state")
    if state in {
        SESSION_CONFIRMED_SUCCESS,
        SESSION_REFUSED,
        SESSION_DRY_RUN,
        READY_TO_EVALUATE,
        SESSION_FAILED_CONFIRMED_NO_MUTATION,
    }:
        return 0
    if state in {SESSION_PERSISTENCE_FAILED_SIGNAL, SESSION_INTERRUPTED_ATOMIC_WRITE}:
        return 3
    return 1
