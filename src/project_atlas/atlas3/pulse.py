"""AT3-015 — Atlas Pulse derived lens.

Answers: what changed / matters / became stale / conflicts / failed /
was decided / should I look at next.

Composes landed Coder Alpha answers + the Atlas 3 ledger.
Does not invent history. UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    GENERATOR_ID,
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    honesty_block,
    load_answer,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.ledger import list_events

PACKAGE_ID: Final[str] = "AT3-015"
PULSE_QUESTIONS: Final[tuple[str, ...]] = (
    "what_changed",
    "what_matters",
    "what_became_stale",
    "what_conflicts",
    "what_failed",
    "what_was_decided",
    "what_should_i_look_at_next",
)


def _unknown(reason: str) -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason": reason, "items": []}


def _from_answer(answer: dict[str, Any] | None, *, missing: str) -> dict[str, Any]:
    if answer is None:
        return _unknown(missing)
    status = str(answer.get("status") or answer.get("disposition") or "derived")
    return {
        "status": status if status else "derived",
        "items": [answer],
        "authority": "derived",
    }


def compile_pulse(vault: Any, project_id: str) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    changed = load_answer(root, f"ans-changed-{pid}")
    unknown = load_answer(root, f"ans-unknown-{pid}")
    state = load_answer(root, f"ans-state-{pid}")
    decisions = load_answer(root, f"ans-decisions-{pid}")
    nxt = load_answer(root, f"ans-next-{pid}")
    attention = load_answer(root, f"ans-attention-{pid}")
    events = list_events(root, pid)
    failures = [item for item in events if item.get("kind") in {"failure", "incident"}]
    decisions_ev = [item for item in events if item.get("kind") == "decision"]
    stale_events = [
        item
        for item in events
        if (item.get("payload") or {}).get("freshness") == "STALE"
    ]

    questions = {
        "what_changed": _from_answer(changed, missing="changed lens not materialized"),
        "what_matters": _from_answer(
            attention or nxt,
            missing="attention/next lens not materialized",
        ),
        "what_became_stale": (
            {"status": "derived", "items": stale_events, "authority": "derived"}
            if stale_events
            else _from_answer(changed, missing="no stale evidence; changed lens absent")
        ),
        "what_conflicts": _from_answer(unknown, missing="unknown/conflict lens not materialized"),
        "what_failed": (
            {"status": "derived", "items": failures, "authority": "derived"}
            if failures
            else _unknown("no failure events in atlas3 ledger")
        ),
        "what_was_decided": (
            {"status": "derived", "items": decisions_ev, "authority": "derived"}
            if decisions_ev
            else _from_answer(decisions, missing="decisions lens not materialized")
        ),
        "what_should_i_look_at_next": _from_answer(
            nxt,
            missing="next lens not materialized",
        ),
    }

    missing = [
        key for key, value in questions.items() if value.get("status") == "UNKNOWN"
    ]
    report = {
        "schema": "atlas3.pulse.v1",
        "schema_version": 1,
        "package": PACKAGE_ID,
        "project_id": pid,
        "state": load_answer(root, f"ans-state-{pid}") is not None,
        "questions": questions,
        "unknown_questions": missing,
        "ledger_event_count": len(events),
        "authority": "derived",
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "generated": {"by": GENERATOR_ID},
        "current_state_lens_present": state is not None,
    }
    write_json_atomic(root / OPS_RELATIVE / "pulse" / f"{pid}.json", report)
    return report
