"""D-146 — fail-closed outer-session return gate.

Shell/CI/certification completion must not imply owner return.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

PACKAGE_ID: Final[str] = "AS-D146-AUTONOMY-RETURN-GATE-001"


class AutonomyReturnState(BaseModel):
    """Counts and frontier flags for outer-session return decisions."""

    model_config = ConfigDict(extra="forbid")

    package_id: str = PACKAGE_ID
    ready_nodes: int = Field(default=0, ge=0)
    running_nodes: int = Field(default=0, ge=0)
    recoverable_failed_nodes: int = Field(default=0, ge=0)
    uncertified_changes: int = Field(default=0, ge=0)
    derivable_successors: int = Field(default=0, ge=0)
    preparable_blocked_work: int = Field(default=0, ge=0)
    genuine_owner_frontier: bool = False
    external_hard_blocker: bool = False
    project_terminal: bool = False


def autonomous_work_exists(state: AutonomyReturnState) -> bool:
    return any(
        [
            state.ready_nodes > 0,
            state.running_nodes > 0,
            state.recoverable_failed_nodes > 0,
            state.uncertified_changes > 0,
            state.derivable_successors > 0,
            state.preparable_blocked_work > 0,
        ]
    )


def may_emit_final_return(state: AutonomyReturnState) -> bool:
    """Return True only when no autonomous work remains and a frontier exists."""
    if autonomous_work_exists(state):
        return False
    return (
        state.genuine_owner_frontier
        or state.external_hard_blocker
        or state.project_terminal
    )


def final_response_precheck(state: AutonomyReturnState) -> dict[str, object]:
    """Machine-enforced precheck before outer agent final response."""
    work = autonomous_work_exists(state)
    allowed = may_emit_final_return(state)
    return {
        "package_id": PACKAGE_ID,
        "autonomous_work_exists": work,
        "may_emit_final_return": allowed,
        "suppress_final_response": work and not allowed,
        "continue_dag": work,
        "merge_authorized": False,
    }
