"""What changed between two contract versions, in the terms a reviewer cares about.

A field-by-field JSON diff answers "is this different" and buries the answer to
"does my earlier approval still hold". These five axes are separated because
each invalidates something different: a scope change invalidates the review, an
acceptance change invalidates what "done" meant, a context change invalidates
what the worker was told, a binding change invalidates the host-dependent
validation, and an authorization change invalidates who said yes.
"""

from __future__ import annotations

from typing import Any

from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    binding_digest,
    contract_digest,
)

#: Axes whose change means an earlier approval no longer describes this work.
INVALIDATING_AXES: tuple[str, ...] = ("scope", "acceptance", "authorization")


def _seq_diff(before: tuple[str, ...], after: tuple[str, ...]) -> dict[str, list[str]]:
    return {
        "added": [item for item in after if item not in before],
        "removed": [item for item in before if item not in after],
    }


def _acceptance_view(contract: TaskContract) -> dict[str, str]:
    """One line per check: kind plus the argv/path/pattern that decides it."""
    view: dict[str, str] = {}
    for check in contract.acceptance:
        decider = " ".join(check.argv) or check.path or check.pattern or ""
        view[check.check_id] = f"{check.kind.value}: {decider}"
    return view


def _requirement_view(contract: TaskContract) -> dict[str, str]:
    return {
        r.requirement_id: f"[{r.verification.value}] {r.statement} "
        f"<- {', '.join(r.check_ids) or 'no check'}"
        for r in contract.requirements
    }


def _mapping_diff(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": {
            key: {"before": before[key], "after": after[key]}
            for key in sorted(set(before) & set(after))
            if before[key] != after[key]
        },
    }


def diff_contracts(
    before: TaskContract,
    after: TaskContract,
    *,
    binding_before: DeploymentBinding | None = None,
    binding_after: DeploymentBinding | None = None,
) -> dict[str, Any]:
    """Compare two contract versions along the axes that change a decision."""
    axes: dict[str, Any] = {
        "scope": {
            "scope": _seq_diff(before.scope, after.scope),
            "exclusions": _seq_diff(before.exclusions, after.exclusions),
            "mutation_paths": _seq_diff(before.mutation_paths, after.mutation_paths),
            "expected_output_paths": _seq_diff(
                before.expected_output_paths, after.expected_output_paths
            ),
            "objective_changed": before.objective != after.objective,
            "observable_outcome_changed": (
                before.observable_outcome != after.observable_outcome
            ),
        },
        "acceptance": {
            "checks": _mapping_diff(_acceptance_view(before), _acceptance_view(after)),
            "requirements": _mapping_diff(
                _requirement_view(before), _requirement_view(after)
            ),
        },
        "context": _mapping_diff(
            {c.source_id: f"{c.path} :: {c.why}" for c in before.context},
            {c.source_id: f"{c.path} :: {c.why}" for c in after.context},
        ),
        "authorization": {
            "owner": {"before": before.owner, "after": after.owner}
            if before.owner != after.owner
            else None,
            "references": _mapping_diff(
                {r.reference: r.kind for r in before.authorization_references},
                {r.reference: r.kind for r in after.authorization_references},
            ),
        },
        "binding": {
            "before_digest": binding_digest(binding_before) if binding_before else None,
            "after_digest": binding_digest(binding_after) if binding_after else None,
            "changed": (
                (binding_digest(binding_before) if binding_before else None)
                != (binding_digest(binding_after) if binding_after else None)
            ),
        },
        "limits": {
            "before": before.limits.model_dump(mode="json"),
            "after": after.limits.model_dump(mode="json"),
            "changed": before.limits != after.limits,
        },
        "base_pin": {
            "before": before.base_pin,
            "after": after.base_pin,
            "changed": before.base_pin != after.base_pin,
        },
    }

    changed_axes = sorted(axis for axis in axes if _axis_changed(axes[axis]))
    invalidating = [axis for axis in changed_axes if axis in INVALIDATING_AXES]

    return {
        "schema": "atlas.taskcontract.diff/1",
        "contract_id": after.contract_id,
        "before": {
            "version": before.contract_version,
            "digest": contract_digest(before),
        },
        "after": {
            "version": after.contract_version,
            "digest": contract_digest(after),
        },
        "identical": contract_digest(before) == contract_digest(after),
        "changed_axes": changed_axes,
        "axes": axes,
        "prior_approval_still_describes_this_work": not (
            invalidating or axes["binding"]["changed"]
        ),
        "why_not": (
            [f"{axis} changed" for axis in invalidating]
            + (["deployment binding changed"] if axes["binding"]["changed"] else [])
        ),
        "grants": (
            "NOTHING. A diff reports what moved; re-approval is a human act and "
            "an earlier launch approval does not survive an invalidating change."
        ),
    }


def _axis_changed(axis: Any) -> bool:
    """True when anything inside this axis is non-empty / flagged changed."""
    if isinstance(axis, dict):
        return any(_axis_changed(value) for key, value in axis.items()
                   if key not in {"before", "after", "before_digest", "after_digest"})
    if isinstance(axis, list):
        return bool(axis)
    if isinstance(axis, bool):
        return axis
    return axis is not None
