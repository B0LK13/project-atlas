"""AS-STUDIO-A2-004 — action evidence + recovery projection.

MONITOR_RESULTS != RE-EXECUTE
EXECUTION_FAILURE != SUCCESS
UNCERTAIN_MUTATION != NOTHING_CHANGED
CAPTURE != AUTHORITY / SPOOL != TRUTH_CORE
AUTO_RETRY = FORBIDDEN
STUDIO_UI != AUTHORITY

Inspects an ATLAS_STUDIO_ACTION_DECISION_V1 packet (or refuses UNAVAILABLE),
classifies the outcome for humans/agents, and emits recovery guidance that
never auto-retries mutations. Optional spool write feeds the governed
knowledge-capture path as non-canonical raw evidence only.
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
from atlas_studio.snapshot import utcnow, validator_for

SCHEMA_CONST = "ATLAS_STUDIO_ACTION_EVIDENCE_V1"
SCHEMA_FILE = "atlas_studio_action_evidence_v1.schema.json"
DECISION_SCHEMA = "ATLAS_STUDIO_ACTION_DECISION_V1"

CONFIRMED_SUCCESS = "CONFIRMED_SUCCESS"
REFUSED = "REFUSED"
FAILED_UNCERTAIN = "FAILED_UNCERTAIN"
FAILED_CONFIRMED_NO_MUTATION = "FAILED_CONFIRMED_NO_MUTATION"
DRY_RUN = "DRY_RUN"
PENDING_EXECUTE = "PENDING_EXECUTE"
MALFORMED = "MALFORMED"
UNAVAILABLE = "UNAVAILABLE"


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "execution_failure_ne_success": True,
        "uncertain_mutation_ne_nothing_changed": True,
        "capture_ne_authority": True,
        "spool_ne_truth_core": True,
        "auto_retry_forbidden": True,
        "monitor_ne_reexecute": True,
    }


def validate_action_evidence(packet: dict) -> list[str]:
    validator = validator_for(SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_decision_file(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"DECISION_FILE_MISSING:{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("DECISION_NOT_OBJECT")
    return data


def classify_decision(decision: dict[str, Any] | None) -> str:
    """Map a decision packet to an outcome class for recovery UX."""
    if decision is None:
        return UNAVAILABLE
    if not isinstance(decision, dict):
        return MALFORMED
    schema = decision.get("schema")
    outcome = decision.get("decision")
    if schema is not None and schema != DECISION_SCHEMA:
        return MALFORMED
    if not outcome or not isinstance(outcome, str):
        return MALFORMED
    if decision.get("dry_run") is True and outcome in {"EXECUTE_ALLOWED", "EXECUTED"}:
        return DRY_RUN
    if outcome == "EXECUTED" and decision.get("mutated") is True:
        return CONFIRMED_SUCCESS
    if outcome.startswith("REFUSED_"):
        return REFUSED
    if outcome == "EXECUTION_FAILED":
        evidence = decision.get("evidence") or {}
        if isinstance(evidence, dict) and evidence.get("mutation_state") == "UNKNOWN":
            return FAILED_UNCERTAIN
        return FAILED_CONFIRMED_NO_MUTATION
    if outcome == "EXECUTE_ALLOWED":
        # Evaluate-only allow: not yet executed; never treat as success.
        return PENDING_EXECUTE
    return MALFORMED


def build_recovery(outcome_class: str, decision: dict[str, Any] | None) -> dict[str, Any]:
    """Recovery actions — never auto-retry mutations."""
    actions: list[dict[str, str]] = []
    notes = ["AUTO_RETRY=FORBIDDEN", "MONITOR_NE_REEXECUTE"]
    intent_id = (decision or {}).get("intent_id")
    action_type = (decision or {}).get("action_type") or "OWNERSHIP_CLAIM"

    if outcome_class == UNAVAILABLE:
        actions.append(
            {
                "id": "supply_decision",
                "summary": "Provide --decision-file with ATLAS_STUDIO_ACTION_DECISION_V1",
            }
        )
    elif outcome_class == MALFORMED:
        actions.append(
            {
                "id": "inspect_packet",
                "summary": "Inspect decision JSON schema/fields; do not treat as success",
            }
        )
    elif outcome_class == CONFIRMED_SUCCESS:
        actions.append(
            {
                "id": "refresh_mission",
                "summary": "Re-run mission-journey / mission-control to observe ownership",
            }
        )
        actions.append(
            {
                "id": "optional_spool",
                "summary": "Optionally spool this evidence into knowledge capture (non-canonical)",
            }
        )
    elif outcome_class == REFUSED:
        reasons = list((decision or {}).get("reasons") or [])
        actions.append(
            {
                "id": "read_refusal",
                "summary": f"Address refusal reasons: {', '.join(map(str, reasons[:5])) or 'see packet'}",
            }
        )
        actions.append(
            {
                "id": "repreview",
                "summary": "Re-run claim-preview/claim-evaluate against live truth (do not force execute)",
            }
        )
    elif outcome_class == DRY_RUN:
        actions.append(
            {
                "id": "wet_path_separate",
                "summary": "Dry-run is not execution; use claim-execute --repo only when authorized",
            }
        )
    elif outcome_class == PENDING_EXECUTE:
        actions.append(
            {
                "id": "execute_requires_authorization",
                "summary": (
                    "EXECUTE_ALLOWED is not EXECUTED; run claim-execute --repo only under "
                    "explicit authorization (Studio never self-authorizes)"
                ),
            }
        )
    elif outcome_class == FAILED_UNCERTAIN:
        notes.append("UNCERTAIN_MUTATION!=NOTHING_CHANGED")
        actions.append(
            {
                "id": "inspect_control_plane",
                "summary": (
                    "Inspect atlas_dag event bus / OWNER_CLAIMED for this lane before any retry"
                ),
            }
        )
        actions.append(
            {
                "id": "do_not_auto_retry",
                "summary": "Do not auto-retry claim-execute; duplicate effects risk",
            }
        )
        actions.append(
            {
                "id": "reconcile_then_decide",
                "summary": "After inspection, either stop or mint a fresh intent if still unowned",
            }
        )
    elif outcome_class == FAILED_CONFIRMED_NO_MUTATION:
        actions.append(
            {
                "id": "fix_executor_then_fresh_intent",
                "summary": "Fix executor/environment, then mint a fresh intent (no replay of same attempt)",
            }
        )

    if intent_id:
        notes.append(f"intent_id={intent_id}")
    notes.append(f"action_type={action_type}")

    return {
        "actions": actions,
        "auto_retry": False,
        "notes": notes,
    }


def write_knowledge_spool(
    *,
    spool_dir: Path | str,
    evidence_packet: dict[str, Any],
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Write non-canonical spool evidence for later governed capture.

    CAPTURE != AUTHORITY. Does not write vault Truth Core / Layer B.
    """
    root = Path(spool_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = clock().replace(":", "").replace("-", "")
    fingerprint = _canonical_sha256(evidence_packet)[:16]
    name = f"studio-action-evidence-{stamp}-{fingerprint}.json"
    path = root / name
    envelope = {
        "schema": "ATLAS_STUDIO_KNOWLEDGE_SPOOL_V0",
        "captured_at_utc": clock(),
        "source": "atlas_studio.action_evidence",
        "authority": False,
        "canonical": False,
        "item_type": "observation",
        "summary": (
            f"Studio action evidence outcome_class="
            f"{evidence_packet.get('outcome_class')} "
            f"decision={(evidence_packet.get('decision') or {}).get('decision')}"
        ),
        "payload": evidence_packet,
        "honesty": {
            "capture_ne_authority": True,
            "spool_ne_truth_core": True,
            "conversation_ne_authority": True,
        },
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return {
        "written": True,
        "path": str(path),
        "canonical": False,
        "authority": False,
        "notes": ["SPOOL!=TRUTH_CORE", "requires later quarantine/normalize/review"],
    }


def build_action_evidence(
    *,
    decision: dict[str, Any] | None = None,
    decision_file: Path | str | None = None,
    spool_dir: Path | str | None = None,
    write_spool: bool = False,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build ATLAS_STUDIO_ACTION_EVIDENCE_V1. Never mutates control plane."""
    notes = ["package:AS-STUDIO-A2-004", "monitor_ne_reexecute"]
    loaded: dict[str, Any] | None = decision
    if loaded is None and decision_file is not None:
        try:
            loaded = load_decision_file(decision_file)
            notes.append(f"loaded:{decision_file}")
        except FileNotFoundError:
            loaded = None
            notes.append("DECISION_FILE_MISSING")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            loaded = None
            notes.append(f"DECISION_LOAD_ERROR:{type(exc).__name__}")

    outcome = classify_decision(loaded)
    recovery = build_recovery(outcome, loaded)

    packet: dict[str, Any] = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "outcome_class": outcome,
        "decision": loaded,
        "recovery": recovery,
        "knowledge_spool": None,
        "honesty": honesty_block(),
        "provenance": {
            "generator": "atlas-studio action-evidence (AS-STUDIO-A2-004)",
            "presentation_only": True,
            "grants_no_mutation": True,
            "notes": notes,
            "evidence_fingerprint": None,
        },
    }

    if write_spool:
        if spool_dir is None:
            packet["knowledge_spool"] = {
                "written": False,
                "error": "SPOOL_DIR_REQUIRED",
                "canonical": False,
                "authority": False,
            }
            notes.append("SPOOL_DIR_REQUIRED")
        else:
            # Fingerprint before spool so spool path is not circular.
            material = {k: v for k, v in packet.items() if k != "provenance"}
            packet["provenance"]["evidence_fingerprint"] = _canonical_sha256(material)
            packet["knowledge_spool"] = write_knowledge_spool(
                spool_dir=spool_dir, evidence_packet=packet, clock=clock
            )
            notes.append("spool_written")

    material = {k: v for k, v in packet.items() if k != "provenance"}
    packet["provenance"]["notes"] = notes
    packet["provenance"]["evidence_fingerprint"] = _canonical_sha256(material)
    return packet


def format_action_evidence_tui(packet: dict) -> str:
    decision = packet.get("decision") or {}
    recovery = packet.get("recovery") or {}
    lines = [
        f"atlas-studio action-evidence schema={packet.get('schema')}",
        f"outcome_class={packet.get('outcome_class')} "
        f"decision={decision.get('decision')} mutated={decision.get('mutated')} "
        f"dry_run={decision.get('dry_run')}",
        f"intent_id={decision.get('intent_id')} action_type={decision.get('action_type')}",
        f"auto_retry={recovery.get('auto_retry')}",
    ]
    for action in recovery.get("actions") or []:
        lines.append(f"  recovery: [{action.get('id')}] {action.get('summary')}")
    spool = packet.get("knowledge_spool")
    if isinstance(spool, dict) and spool.get("written"):
        lines.append(f"  spool: {spool.get('path')} (non-canonical)")
    lines.append(
        "HONESTY: EXECUTION_FAILURE!=SUCCESS / UNCERTAIN_MUTATION!=NOTHING_CHANGED / "
        "AUTO_RETRY=FORBIDDEN / CAPTURE!=AUTHORITY"
    )
    return "\n".join(lines)
