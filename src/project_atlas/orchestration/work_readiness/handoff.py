"""Idempotent handoff preparation. PROPOSAL != CLAIM."""

from __future__ import annotations

from typing import Any

from project_atlas.orchestration.work_readiness.models import (
    HandoffProposal,
    SelectionBucket,
    WorkItemProjection,
    WorkQueueReport,
    stable_handoff_id,
)


def prepare_handoff(
    report: WorkQueueReport,
    task_id: str,
    *,
    proposed_agent_or_capabilities: str,
    execution_limits: dict[str, Any] | None = None,
) -> HandoffProposal:
    """Build an idempotent proposal. Does not reserve work or grant authority."""
    item = _require_item(report, task_id)
    if item.bucket is not SelectionBucket.OFFERABLE_TO_DISPATCHER:
        # Still emit a packet so operators can inspect, but mark expired semantics
        # when used as a transfer — callers must re-check via refresh_handoff.
        pass

    hid = stable_handoff_id(
        task_id=item.task_id,
        contract_digest=item.contract_digest,
        source_revisions=report.source_revisions,
        mutation_paths=item.mutation_paths,
    )
    dep_evidence = tuple(
        f"{d.dependency_id}:{d.status.value}:{d.evidence or ''}" for d in item.dependencies
    )
    ownership = []
    if item.active_claim_id:
        ownership.append(f"claim={item.active_claim_id} agent={item.active_claim_agent}")
    else:
        ownership.append("no active claim observed for this task_id")
    freshness = tuple(
        f"{s.source_id}:rev={s.revision}:reachable={s.reachable}:stale={s.stale}"
        for s in item.sources
    )
    acceptance = (item.acceptance_ref,) if item.acceptance_ref else ()
    return HandoffProposal(
        handoff_id=hid,
        task_id=item.task_id,
        contract_id=item.contract_id,
        contract_digest=item.contract_digest,
        source_revisions=dict(report.source_revisions),
        proposed_agent_or_capabilities=proposed_agent_or_capabilities,
        dependency_evidence=dep_evidence,
        ownership_evidence=tuple(ownership),
        mutation_paths=item.mutation_paths,
        execution_limits=dict(execution_limits or {}),
        acceptance_refs=acceptance,
        freshness_conditions=freshness,
        observed_at=report.observed_at,
        expired=False,
        expire_reason=None,
    )


def refresh_handoff(
    previous: HandoffProposal,
    report: WorkQueueReport,
) -> HandoffProposal:
    """Re-check contract/ownership/deps/binding immediately before transfer use.

    A stale proposal is rejected recognizably. This does **not** replace the
    authority check before dispatch.
    """
    item = next((i for i in report.items if i.task_id == previous.task_id), None)
    if item is None:
        return previous.model_copy(
            update={
                "expired": True,
                "expire_reason": "task absent from refreshed projection",
            }
        )
    reasons: list[str] = []
    if item.contract_digest != previous.contract_digest:
        reasons.append(
            f"contract_digest changed {previous.contract_digest!r} -> {item.contract_digest!r}"
        )
    if dict(report.source_revisions) != dict(previous.source_revisions):
        reasons.append("source_revisions drifted")
    if tuple(item.mutation_paths) != tuple(previous.mutation_paths):
        reasons.append("mutation_paths changed")
    if item.active_claim_id is not None:
        reasons.append(f"active claim appeared: {item.active_claim_id}")
    if item.bucket is not SelectionBucket.OFFERABLE_TO_DISPATCHER:
        reasons.append(f"bucket is {item.bucket.value}, not OFFERABLE_TO_DISPATCHER")

    expected_id = stable_handoff_id(
        task_id=item.task_id,
        contract_digest=item.contract_digest,
        source_revisions=report.source_revisions,
        mutation_paths=item.mutation_paths,
    )
    if expected_id != previous.handoff_id and not reasons:
        reasons.append("handoff_id no longer matches recomputed identity")

    if reasons:
        return previous.model_copy(
            update={
                "expired": True,
                "expire_reason": "; ".join(reasons),
            }
        )
    # Re-prepare identical body (idempotent — same handoff_id).
    return prepare_handoff(
        report,
        item.task_id,
        proposed_agent_or_capabilities=previous.proposed_agent_or_capabilities,
        execution_limits=dict(previous.execution_limits),
    )


def _require_item(report: WorkQueueReport, task_id: str) -> WorkItemProjection:
    for item in report.items:
        if item.task_id == task_id:
            return item
    raise KeyError(f"task_id not in projection: {task_id}")
