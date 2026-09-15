"""Backlog item -> draft contract, with the gaps named rather than filled.

THE ONE RULE HERE
    Nothing is invented. An owner, an authorization, an acceptance command, a
    budget and a mutation path are all decisions somebody has to make, and a
    plausible default for any of them is worse than an empty field: it looks
    reviewed. Everything this module writes into a draft is either read from
    the declared origination source or supplied explicitly by the caller.

    Prose is not a decision either. A backlog item that says "approved by the
    owner, budget $50, run pytest" contributes none of those -- it is data
    about intent, and it is carried into the draft as text the operator reads,
    never as a field the contract asserts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from project_atlas.orchestration.origination.adapter import EligibleRoadmapItem
from project_atlas.orchestration.taskcontract.models import (
    TaskContract,
    TaskContractError,
    find_placeholders,
)

#: Fields no source can supply, in the order an operator naturally decides
#: them. Each carries the question it answers, because "missing: owner" tells
#: an operator what is absent and not what to do about it.
_OPERATOR_DECISIONS: tuple[tuple[str, str], ...] = (
    ("owner", "Who is accountable for this task's result?"),
    ("repository", "Which repository does the work happen in?"),
    ("base_pin", "Which commit is the work based on (a full 40-char sha)?"),
    ("mutation_paths", "Which paths may the worker change?"),
    ("runtime", "Which adapter runs it, and with which capabilities?"),
    ("requirements", "What must be observably true when this is done?"),
    ("acceptance", "Which checks decide each requirement?"),
    ("limits", "What bounds the attempt: launches, attempts, seconds?"),
    ("budget", "What is the cost ceiling, and what actually enforces it?"),
    ("observable_outcome", "What is true at the end that is not true now?"),
)


@dataclass(frozen=True)
class MissingField:
    """One field the draft could not fill, and what would fill it."""

    field: str
    question: str
    why_not_inferred: str = (
        "no declared source states it, and guessing it would look reviewed"
    )


@dataclass(frozen=True)
class DraftConflict:
    """Two inputs that disagree. Reported, never silently resolved."""

    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftResult:
    """A draft is a partial payload plus an honest account of what is absent."""

    payload: dict[str, Any]
    missing: tuple[MissingField, ...]
    conflicts: tuple[DraftConflict, ...]
    #: Present only when the payload is complete AND parses.
    contract: TaskContract | None = None

    @property
    def complete(self) -> bool:
        return self.contract is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "payload": self.payload,
            "missing": [
                {
                    "field": m.field,
                    "question": m.question,
                    "why_not_inferred": m.why_not_inferred,
                }
                for m in self.missing
            ],
            "conflicts": [
                {"code": c.code, "message": c.message, "detail": c.detail}
                for c in self.conflicts
            ],
            "grants": (
                "NOTHING. A draft is a proposal; a complete contract is still "
                "not execution authority."
            ),
        }


def _source_reference(item: EligibleRoadmapItem, revision: str | None) -> dict[str, Any]:
    return {
        "source_path": item.source_path,
        "item_id": item.item_id,
        "item_digest": item.item_digest,
        "source_revision": revision,
        "title": item.title,
    }


def draft_from_item(
    item: EligibleRoadmapItem,
    *,
    supplied: dict[str, Any] | None = None,
    contract_id: str | None = None,
    source_revision: str | None = None,
) -> DraftResult:
    """Compose a draft from one backlog item plus explicit structured input.

    ``supplied`` is the operator's own JSON. It is layered OVER the
    source-derived values, and every disagreement between the two is reported
    as a conflict rather than resolved by precedence -- silently preferring one
    side is how a contract ends up describing work nobody asked for.
    """
    # Underscore-prefixed keys are comments, the same convention the program
    # template uses (`_mutation_paths`, `_acceptance`). They let an operator
    # explain a decision in the file where the decision lives instead of in a
    # separate note that goes stale.
    given = {k: v for k, v in (supplied or {}).items() if not k.startswith("_")}
    conflicts: list[DraftConflict] = []

    payload: dict[str, Any] = {
        "contract_id": contract_id or f"CONTRACT-{item.item_id}",
        "contract_version": given.get("contract_version", 1),
        "source": _source_reference(item, source_revision),
        "objective": given.get("objective") or item.title,
        "depends_on": tuple(item.depends_on),
    }

    # Scope and exclusions: an explicit sidecar acceptance contract is the only
    # non-operator source allowed to state scope, because it is reviewable
    # repository metadata rather than prose.
    if item.contract_proposed_scope is not None:
        payload["scope"] = tuple(item.contract_proposed_scope)
    if "scope" in given:
        supplied_scope = tuple(given["scope"])
        if (
            item.contract_proposed_scope is not None
            and tuple(item.contract_proposed_scope) != supplied_scope
        ):
            conflicts.append(
                DraftConflict(
                    code="SCOPE_DISAGREES_WITH_SOURCE_CONTRACT",
                    message=(
                        "the declared acceptance contract and the supplied input "
                        "state different scope; one of them is out of date"
                    ),
                    detail={
                        "source_contract": list(item.contract_proposed_scope or ()),
                        "supplied": list(supplied_scope),
                    },
                )
            )
        payload["scope"] = supplied_scope

    if "depends_on" in given:
        supplied_deps = tuple(given["depends_on"])
        if supplied_deps != tuple(item.depends_on):
            conflicts.append(
                DraftConflict(
                    code="DEPENDS_ON_DISAGREES_WITH_SOURCE",
                    message=(
                        "the backlog item and the supplied input list different "
                        "dependencies"
                    ),
                    detail={
                        "source": list(item.depends_on),
                        "supplied": list(supplied_deps),
                    },
                )
            )
        payload["depends_on"] = supplied_deps

    # A blocked item can still be drafted -- preparation is not dispatch -- but
    # the blocker must survive into the contract's own executable_when.
    if item.blockers:
        payload["executable_when"] = tuple(
            given.get("executable_when", ())
        ) or tuple(f"blocker resolved: {b}" for b in item.blockers)

    for key, value in given.items():
        if key not in payload:
            payload[key] = value

    # Placeholder text arriving from either side is reported here, not silently
    # carried into a "complete" contract.
    for field_name in ("objective", "observable_outcome"):
        text = payload.get(field_name)
        if isinstance(text, str):
            markers = find_placeholders(text)
            if markers:
                conflicts.append(
                    DraftConflict(
                        code="UNRESOLVED_PLACEHOLDER",
                        message=f"{field_name} still contains template markers",
                        detail={"field": field_name, "markers": list(markers)},
                    )
                )

    missing = tuple(
        MissingField(field=name, question=question)
        for name, question in _OPERATOR_DECISIONS
        if not payload.get(name)
    )
    if missing:
        return DraftResult(payload=payload, missing=missing, conflicts=tuple(conflicts))

    try:
        contract = TaskContract.model_validate(payload)
    except (ValueError, TaskContractError) as exc:
        conflicts.append(
            DraftConflict(
                code="DRAFT_DOES_NOT_PARSE",
                message=str(exc),
                detail={},
            )
        )
        return DraftResult(payload=payload, missing=(), conflicts=tuple(conflicts))

    return DraftResult(
        payload=payload,
        missing=(),
        conflicts=tuple(conflicts),
        contract=contract,
    )
