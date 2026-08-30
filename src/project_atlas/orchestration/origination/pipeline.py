"""End-to-end origination pipeline: NORMAL PROJECT SOURCES -> proposal ->
policy-evaluated outcome. Pure, deterministic, no LLM call.

``originate_all()`` is the top-level entry point both Process A
(first-time origination) and Process C (successor discovery) use.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from project_atlas.orchestration.origination.adapter import (
    ADAPTER_VERSION,
    EligibleRoadmapItem,
    eligible_roadmap_items,
    extract_corroborating_facts,
)
from project_atlas.orchestration.origination.facts import SourceFact, SourceFactKind
from project_atlas.orchestration.origination.identity import origination_identity, work_id_for
from project_atlas.orchestration.origination.policy import PolicyResult, evaluate
from project_atlas.orchestration.origination.proposal import (
    AuthorityClass,
    EvidenceCompleteness,
    OriginationProposal,
    Provenance,
)
from project_atlas.orchestration.origination.risk import classify

_MAX_EXCERPT = 400


class OriginationOutcome(BaseModel):
    """One originated proposal plus its policy evaluation. What
    ``originate_all()`` returns per eligible roadmap item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal: OriginationProposal
    policy: PolicyResult


def originate_all(project_root: Path, project_id: str) -> tuple[OriginationOutcome, ...]:
    """Scan ``project_root`` for specification-backed work and return one
    ``OriginationOutcome`` per eligible roadmap item found, policy-evaluated.

    Returns an empty tuple when nothing is eligible -- the correct,
    honest ``NO_ELIGIBLE_WORK`` outcome, not an error.
    """
    return tuple(
        _build_outcome(project_root, project_id, item)
        for item in eligible_roadmap_items(project_root)
    )


def originate_new_only(
    project_root: Path, project_id: str, projection_store: Path
) -> tuple[OriginationOutcome, ...]:
    """``originate_all()``, filtered to outcomes whose
    ``origination_identity`` is not already durably resolved
    (``TERMINAL``) in ``projection_store``.

    This is what a real successor-discovery scan (Process C) should call,
    not ``originate_all()`` directly: a project's own roadmap record can
    lag reality (e.g. a completed item whose status field was never
    updated -- see ADR-033's O1 mutation-surface note: the roadmap file
    itself is deliberately not in a leased node's authorized scope, so
    "implement the feature" and "declare the roadmap item done" can be
    separate authorities). Without this filter, a stale roadmap record
    would make every successor scan "re-discover" already-completed work
    -- this is exactly the case ``NO_DUPLICATE_ORIGINATION`` /
    ``RESTART_REPLAY`` must hold under, not just the simpler case where
    nothing on disk changed at all.
    """
    from project_atlas.orchestration.origination.projection import load_projection

    try:
        projection = load_projection(projection_store)
    except Exception:
        # No durable record at all yet (or an unreadable store) -- every
        # candidate is "new" from this scan's point of view; fail open
        # toward re-deriving rather than silently hiding real work behind
        # a store this scan cannot trust anyway.
        resolved_identities: frozenset[str] = frozenset()
    else:
        resolved_identities = frozenset(
            row.origination_identity for row in projection.records if row.state == "TERMINAL"
        )
    return tuple(
        outcome
        for outcome in originate_all(project_root, project_id)
        if outcome.proposal.origination_identity not in resolved_identities
    )


def _build_outcome(
    project_root: Path, project_id: str, item: EligibleRoadmapItem
) -> OriginationOutcome:
    excerpt = f"id={item.item_id} title={item.title} evidence=[{','.join(item.evidence)}]"
    authoritative_fact = SourceFact(
        kind=SourceFactKind.AUTHORITATIVE_ROADMAP_ITEM,
        project_id=project_id,
        location="docs/ROADMAP.md",
        content_digest=item.roadmap_digest,
        excerpt=excerpt[:_MAX_EXCERPT],
        subject_id=item.item_id,
        subject_digest=item.item_digest,
    )
    acceptance_facts = extract_corroborating_facts(project_root, project_id, item.evidence)

    source_evidence = (authoritative_fact, *acceptance_facts)
    source_locations = tuple(dict.fromkeys(fact.location for fact in source_evidence))

    success_criteria = (
        f"Implement {item.item_id} exactly per its declared evidence",
        *(f"Evidence available: {path}" for path in item.evidence),
    )
    proposed_scope = _proposed_scope(item.evidence)

    risk = classify(
        proposed_scope=proposed_scope,
        success_criteria=success_criteria,
    )

    evidence_completeness = (
        EvidenceCompleteness.COMPLETE if acceptance_facts else EvidenceCompleteness.INTENT_ONLY
    )

    origination_id = origination_identity(project_id, authoritative_fact)
    work_id = work_id_for(project_id, item.item_id)

    if item.depends_on:
        why_now = (
            f"{item.item_id!r} depends on {list(item.depends_on)}; the governed DAG "
            "must observe each corresponding package as CERTIFIED or CLOSED first."
        )
    elif item.blockers:
        why_now = f"{item.item_id!r} declares unresolved blockers and cannot execute yet."
    else:
        why_now = f"{item.item_id!r} has no declared dependency and is the currently-eligible item."

    proposal = OriginationProposal(
        work_id=work_id,
        project_id=project_id,
        title=item.title,
        intent=(
            f"Implement roadmap item {item.item_id!r} ({item.title!r}) "
            "per its declared evidence."
        ),
        why_this_work=(
            f"docs/ROADMAP.md declares {item.item_id!r} as status={item.status} "
            f"lifecycle={item.lifecycle} -- the project's own authoritative next-work record."
        ),
        why_now=why_now,
        source_evidence=source_evidence,
        source_locations=source_locations,
        authoritative_source=authoritative_fact,
        acceptance_evidence=acceptance_facts,
        success_criteria=success_criteria,
        dependencies=tuple(work_id_for(project_id, dep) for dep in item.depends_on),
        blockers=item.blockers,
        contradictions=(),
        proposed_scope=proposed_scope,
        risk_class=risk.risk_class,
        authority_class=AuthorityClass.AUTHORITATIVE,
        evidence_completeness=evidence_completeness,
        provenance=Provenance(
            adapter_version=ADAPTER_VERSION,
            consulted_digests=tuple(dict.fromkeys(fact.content_digest for fact in source_evidence)),
        ),
        origination_identity=origination_id,
    )
    policy = evaluate(proposal)
    return OriginationOutcome(proposal=proposal, policy=policy)


def _proposed_scope(evidence_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Conservative default mutation surface: the evidence paths
    themselves plus a top-level ``src/`` allowance whenever a test-file
    evidence path implies source code needs to change. Generic -- derived
    from the evidence paths' own structure, never from project-specific
    knowledge."""
    scope: set[str] = set(evidence_paths)
    for path in evidence_paths:
        if path.startswith("tests/"):
            scope.add("src/")
    return tuple(sorted(scope))
