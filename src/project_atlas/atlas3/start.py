"""AT3-030 — Atlas Start bounded context briefing.

Requires an explicit token/context budget. No arbitrary RAG dump.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    GENERATOR_ID,
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    load_answer,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.pulse import compile_pulse

PACKAGE_ID: Final[str] = "AT3-030"
START_SECTIONS: Final[tuple[str, ...]] = (
    "project_identity",
    "current_verified_truth",
    "recent_material_changes",
    "relevant_decisions",
    "open_conflicts",
    "open_unknowns",
    "stale_context",
    "current_task",
    "owner_constraints",
    "recent_failures",
    "next_relevant_actions",
)


def _clip(text: str, budget: int) -> tuple[str, int]:
    if budget <= 0:
        return ("", 0)
    if len(text) <= budget:
        return (text, budget - len(text))
    return (text[: budget - 1] + "…", 0)


def _section(status: str, text: str, *, remaining: int) -> tuple[dict[str, Any], int]:
    clipped, left = _clip(text, remaining)
    return (
        {
            "status": status if clipped else "UNKNOWN",
            "text": clipped or "UNKNOWN",
            "authority": "derived",
        },
        left,
    )


def compile_start(
    vault: Any,
    project_id: str,
    *,
    token_budget: int,
    current_task: str | None = None,
) -> dict[str, Any]:
    if token_budget <= 0:
        raise Atlas3Error(
            "TOKEN_BUDGET_REQUIRED",
            "atlas start requires an explicit positive --budget / token_budget",
        )
    root = require_vault(vault)
    pid = require_project(root, project_id)
    pulse = compile_pulse(root, pid)
    remaining = token_budget
    sections: dict[str, Any] = {}

    identity_text = f"project_id={pid}"
    sections["project_identity"], remaining = _section("derived", identity_text, remaining=remaining)

    state = load_answer(root, f"ans-state-{pid}")
    truth_text = "UNKNOWN — state lens not materialized"
    truth_status = "UNKNOWN"
    if state is not None:
        truth_text = str(state.get("summary") or state.get("title") or "state lens present")
        truth_status = "derived"
    sections["current_verified_truth"], remaining = _section(
        truth_status, truth_text, remaining=remaining
    )

    mapping = (
        ("recent_material_changes", "what_changed"),
        ("relevant_decisions", "what_was_decided"),
        ("open_conflicts", "what_conflicts"),
        ("open_unknowns", "what_conflicts"),
        ("stale_context", "what_became_stale"),
        ("recent_failures", "what_failed"),
        ("next_relevant_actions", "what_should_i_look_at_next"),
    )
    questions = pulse.get("questions") or {}
    for section_key, pulse_key in mapping:
        block = questions.get(pulse_key) or {}
        status = str(block.get("status") or "UNKNOWN")
        items = block.get("items") or []
        if items:
            text = f"{status}: {len(items)} evidence item(s)"
        else:
            text = str(block.get("reason") or "UNKNOWN")
            status = "UNKNOWN"
        sections[section_key], remaining = _section(status, text, remaining=remaining)

    if current_task and current_task.strip():
        sections["current_task"], remaining = _section(
            "derived", current_task.strip(), remaining=remaining
        )
    else:
        sections["current_task"], remaining = _section(
            "UNKNOWN",
            "UNKNOWN — current task was not supplied",
            remaining=remaining,
        )

    constraints = load_answer(root, f"ans-decisions-{pid}")
    if constraints is None:
        sections["owner_constraints"], remaining = _section(
            "UNKNOWN",
            "UNKNOWN — owner constraints not materialized",
            remaining=remaining,
        )
    else:
        sections["owner_constraints"], remaining = _section(
            "derived",
            "decisions lens present; not automatically owner constraints",
            remaining=remaining,
        )

    briefing = {
        "schema": "atlas3.start.v1",
        "schema_version": 1,
        "package": PACKAGE_ID,
        "project_id": pid,
        "token_budget": token_budget,
        "tokens_remaining": remaining,
        "rag_dump": False,
        "sections": sections,
        "section_order": list(START_SECTIONS),
        "authority": "derived",
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "generated": {"by": GENERATOR_ID},
    }
    write_json_atomic(root / OPS_RELATIVE / "start" / f"{pid}.json", briefing)
    return briefing
