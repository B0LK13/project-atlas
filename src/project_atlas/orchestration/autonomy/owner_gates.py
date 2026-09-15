"""Owner gates A-F. Autonomous code cannot grant any gate."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import OwnerGateKind

OWNER_GATES: frozenset[OwnerGateKind] = frozenset(OwnerGateKind)


class OwnerGateError(ValueError):
    code = "OWNER_GATE_REQUIRED"


class OwnerGateDecision:
    __slots__ = ("allowed", "gate", "reason")

    def __init__(self, allowed: bool, gate: OwnerGateKind | None, reason: str) -> None:
        self.allowed = allowed
        self.gate = gate
        self.reason = reason


def evaluate_owner_action(
    action: OwnerGateKind,
    *,
    owner_grant: bool = False,
) -> OwnerGateDecision:
    """Fail closed unless an external owner grant is explicitly supplied.

    This module never invents a grant. Callers must pass owner_grant=True
    only when a prior owner authorization artifact exists. This package
    itself does not create such artifacts.
    """
    if action not in OWNER_GATES:
        raise OwnerGateError("unknown owner gate")
    if owner_grant:
        return OwnerGateDecision(True, action, "OWNER_GRANT_SUPPLIED_EXTERNALLY")
    return OwnerGateDecision(False, action, "OWNER_GRANT_ABSENT")


def require_owner(action: OwnerGateKind, *, owner_grant: bool = False) -> None:
    decision = evaluate_owner_action(action, owner_grant=owner_grant)
    if not decision.allowed:
        raise OwnerGateError(f"{action.value} requires owner authority")


def classify_requested_action(
    *,
    merge_to_protected_main: bool = False,
    waive_acceptance: bool = False,
    mutate_certified_object: bool = False,
    change_security_or_governance_policy: bool = False,
    destructive_ops: bool = False,
    material_external_spend: bool = False,
) -> tuple[OwnerGateKind, ...]:
    gates: list[OwnerGateKind] = []
    if merge_to_protected_main:
        gates.append(OwnerGateKind.A_PROTECTED_MAIN_MERGE)
    if waive_acceptance:
        gates.append(OwnerGateKind.B_ACCEPTANCE_WAIVER)
    if mutate_certified_object:
        gates.append(OwnerGateKind.C_CERTIFIED_OBJECT_MUTATION)
    if change_security_or_governance_policy:
        gates.append(OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY)
    if destructive_ops:
        gates.append(OwnerGateKind.E_DESTRUCTIVE_OPS)
    if material_external_spend:
        gates.append(OwnerGateKind.F_MATERIAL_EXTERNAL_SPEND)
    return tuple(gates)
