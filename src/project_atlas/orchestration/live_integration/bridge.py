"""Explicit translation layer between live component public models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.orchestration.live_integration.models import ReviewPackage
from project_atlas.orchestration.taskcontract.models import (
    TaskContract,
    contract_digest,
)
from project_atlas.orchestration.work_readiness.adapters import (
    ClaimView,
    ContractView,
    DependencyNodeView,
    EnrollmentView,
    FixtureClaimPort,
    FixtureDependencyPort,
    FixtureEnrollmentPort,
    FixtureResultPort,
    ResultView,
)
from project_atlas.orchestration.work_readiness.handoff import prepare_handoff
from project_atlas.orchestration.work_readiness.models import (
    SelectionBucket,
    TriState,
    WorkQueueReport,
)
from project_atlas.orchestration.work_readiness.project import project_queue
from project_atlas.orchestration.work_readiness.select import select_next
from project_atlas.task_context.adapters import ContextSourceRef, ContractSnapshot
from project_atlas.task_context.assemble import assemble_packet, check_freshness
from project_atlas.task_context.models import TaskContextError


class IntegrationError(ValueError):
    """Fail-closed integration error. Never falls back to fixtures silently."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def live_contract_to_context_snapshot(contract: TaskContract) -> ContractSnapshot:
    """TaskContract → ContractSnapshot (context public shape)."""
    return ContractSnapshot(
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        objective=contract.objective,
        observable_outcome=contract.observable_outcome,
        scope=contract.scope,
        exclusions=contract.exclusions,
        mutation_paths=contract.mutation_paths,
        repository=contract.repository,
        base_pin=contract.base_pin,
        policy_refs=tuple(
            f"{ref.kind}:{ref.reference}" for ref in contract.authorization_references
        ),
        context=tuple(
            ContextSourceRef(
                source_id=item.source_id,
                path=item.path,
                why=item.why,
                digest=item.digest,
            )
            for item in contract.context
        ),
        requirements=tuple(r.model_dump(mode="json") for r in contract.requirements),
        acceptance=tuple(a.model_dump(mode="json") for a in contract.acceptance),
        depends_on=contract.depends_on,
        source_kind="LIVE_MODULE",
    )


def live_contract_to_readiness_view(contract: TaskContract) -> ContractView:
    """TaskContract → work-readiness ContractView (explicit field map)."""
    auth_ref = None
    if contract.authorization_references:
        first = contract.authorization_references[0]
        auth_ref = f"{first.kind}:{first.reference}"
    # execution_authorized on TaskContract is always False — do not invent YES.
    # Readiness treats missing authorization_ref as awaiting-auth / blocked.
    # Only pass a verified pointer string; never mint a grant.
    return ContractView(
        contract_id=contract.contract_id,
        digest=contract_digest(contract),
        valid=True,  # structural load succeeded; validate separately for gates
        objective=contract.objective,
        expected_result=contract.observable_outcome,
        mutation_paths=contract.mutation_paths,
        required_adapter=str(contract.runtime.adapter.value),
        required_capabilities=tuple(c.value for c in contract.runtime.capabilities),
        dependencies=contract.depends_on,
        authorization_ref=auth_ref,
        limits={
            "max_task_launches": contract.limits.max_task_launches,
            "max_attempts_per_task": contract.limits.max_attempts_per_task,
            "max_task_seconds": contract.limits.max_task_seconds,
            "launches_remaining": contract.limits.max_task_launches,
        },
        source_item_id=contract.source.item_id,
        priority=None,
    )


def load_live_task_contract(path: Path) -> TaskContract:
    """Load via TaskContract schema only. No fixture fallback."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationError(
            f"contract unreadable: {exc}", code="CONTRACT_UNREADABLE"
        ) from exc
    if not isinstance(raw, dict):
        raise IntegrationError("contract must be a JSON object", code="CONTRACT_MALFORMED")
    try:
        return TaskContract.model_validate(raw)
    except Exception as exc:
        raise IntegrationError(
            f"incompatible or invalid TaskContract schema: {exc}",
            code="SCHEMA_INCOMPATIBLE",
        ) from exc


class LiveContractPort:
    """ContractPort backed by on-disk TaskContract JSON (live schema)."""

    fixture_id = "LIVE_MODULE.taskcontract"

    def __init__(
        self,
        by_task_id: dict[str, ContractView],
        *,
        valid_flags: dict[str, bool],
    ) -> None:
        self._by_task = by_task_id
        self._valid = valid_flags

    def load_for_task(self, task_id: str) -> ContractView | None:
        view = self._by_task.get(task_id)
        if view is None:
            return None
        # Prefer validated flag if validate was run.
        if task_id in self._valid and not self._valid[task_id]:
            return ContractView(
                contract_id=view.contract_id,
                digest=view.digest,
                valid=False,
                objective=view.objective,
                expected_result=view.expected_result,
                mutation_paths=view.mutation_paths,
                required_adapter=view.required_adapter,
                required_capabilities=view.required_capabilities,
                dependencies=view.dependencies,
                authorization_ref=view.authorization_ref,
                limits=dict(view.limits),
                source_item_id=view.source_item_id,
                priority=view.priority,
            )
        return view


def project_from_live_contracts(
    *,
    contract_paths: list[Path],
    claims: tuple[ClaimView, ...] = (),
    enrollment: tuple[EnrollmentView, ...] = (),
    results: dict[str, ResultView] | None = None,
    dependency_status: dict[str, DependencyNodeView] | None = None,
    ownership_registry_reachable: bool = True,
    observed_at: str = "1970-01-01T00:00:00Z",
) -> tuple[WorkQueueReport, dict[str, TaskContract]]:
    """Project readiness from live TaskContract files.

    Missing live claim/enrollment/result ports remain explicit: empty enrollment
    with required adapters → capacity blockers; unknown ownership is not free.
    """
    contracts: dict[str, TaskContract] = {}
    views: dict[str, ContractView] = {}
    valid_flags: dict[str, bool] = {}
    for path in contract_paths:
        tc = load_live_task_contract(path)
        # Prefer source.item_id as task key; fall back to contract_id.
        task_id = tc.source.item_id or tc.contract_id
        contracts[task_id] = tc
        views[task_id] = live_contract_to_readiness_view(tc)
        valid_flags[task_id] = True

    missing: tuple[str, ...]
    if not ownership_registry_reachable:
        claim_port = FixtureClaimPort(claims=())
        missing = (
            "ClaimPort/EnrollmentPort live interfaces unavailable — "
            "UNKNOWN ownership is not free availability",
        )
    else:
        claim_port = FixtureClaimPort(claims=claims)
        missing = ()

    # Dependencies: default UNKNOWN unless provided (never invent YES).
    dep_nodes: dict[str, DependencyNodeView] = dict(dependency_status or {})
    for view in views.values():
        for dep in view.dependencies:
            dep_nodes.setdefault(
                dep,
                DependencyNodeView(node_id=dep, status=TriState.UNKNOWN, evidence=None),
            )

    seeds = [
        {
            "task_id": tid,
            "source_ref": f"live-contract:{tid}",
            "source_revision": views[tid].digest,
            "objective": views[tid].objective,
            "priority": views[tid].priority,
        }
        for tid in sorted(views)
    ]
    report = project_queue(
        seeds=seeds,
        contracts=LiveContractPort(views, valid_flags=valid_flags),
        claims=claim_port,
        enrollment=FixtureEnrollmentPort(roster=enrollment),
        results=FixtureResultPort(results=results or {}),
        dependencies=FixtureDependencyPort(nodes=dep_nodes),
        observed_at=observed_at,
        fixture_adapters_used=(),
        missing_integrations=(
            *missing,
            "Live ClaimPort/EnrollmentPort/ResultPort not connected",
            "remaining explicit blockers",
        ),
        source_revisions={
            "mode": "LIVE_TASKCONTRACT",
            **{f"contract:{tid}": views[tid].digest for tid in views},
        },
    )
    if not ownership_registry_reachable:
        from project_atlas.orchestration.work_readiness.models import (
            Blocker,
            BlockerCode,
            SelectionBucket,
        )

        rewritten = []
        for item in report.items:
            blocker = Blocker(
                code=BlockerCode.UNKNOWN_OWNERSHIP,
                object_ref="ownership_registry",
                evidence=("ownership registry unreachable or unread",),
                next_step="Restore ClaimPort/EnrollmentPort; UNKNOWN ≠ available.",
                responsible_role="operator",
                recheck_fields=("ownership_clear", "active_claim_id"),
            )
            rewritten.append(
                item.model_copy(
                    update={
                        "blockers": (*item.blockers, blocker),
                        "bucket": SelectionBucket.BLOCKED,
                        "axes": item.axes.model_copy(
                            update={"ownership_clear": TriState.UNKNOWN}
                        ),
                        "selection_explanation": (
                            *item.selection_explanation,
                            "ownership registry UNKNOWN - not free capacity",
                        ),
                    }
                )
            )
        report = report.model_copy(
            update={
                "items": tuple(rewritten),
                "offerable": (),
                "awaiting_authorization": (),
                "blocked": tuple(i.task_id for i in rewritten),
                "empty_queue_reasons": (
                    *report.empty_queue_reasons,
                    "ownership registry unreachable - not free capacity",
                ),
            }
        )
    return report, contracts


def build_review_package(
    report: WorkQueueReport,
    task_id: str,
    *,
    context_packet: Any | None = None,
    freshness_status: str | None = None,
    propose_for: str = "reviewer",
) -> ReviewPackage:
    item = next((i for i in report.items if i.task_id == task_id), None)
    if item is None:
        raise IntegrationError(f"task_id not in projection: {task_id}", code="TASK_MISSING")
    handoff = None
    if item.bucket is SelectionBucket.OFFERABLE_TO_DISPATCHER:
        handoff = prepare_handoff(report, task_id, proposed_agent_or_capabilities=propose_for)
    packet_id = getattr(context_packet, "packet_id", None) if context_packet else None
    content_digest = getattr(context_packet, "content_digest", None) if context_packet else None
    return ReviewPackage(
        task_id=task_id,
        contract_id=item.contract_id or "",
        contract_digest=item.contract_digest or "",
        selection_bucket=item.bucket.value,
        selection_reasons=item.selection_explanation,
        blockers=tuple(b.model_dump(mode="json") for b in item.blockers),
        source_revisions=dict(report.source_revisions),
        context_packet_id=packet_id,
        context_content_digest=content_digest,
        context_freshness=freshness_status,
        handoff_id=handoff.handoff_id if handoff else None,
        fixture_labeled=False,
    )


def run_controlled_chain(
    *,
    contract_path: Path,
    workspace: Path,
    evidence_path: Path | None = None,
    enrollment: tuple[EnrollmentView, ...] = (),
    dependency_status: dict[str, DependencyNodeView] | None = None,
    claims: tuple[ClaimView, ...] = (),
) -> dict[str, Any]:
    """Compose context + project readiness + review package from one live contract.

    Production path: schema errors raise IntegrationError (no fixture fallback).
    """
    contract = load_live_task_contract(contract_path)
    snapshot = live_contract_to_context_snapshot(contract)
    # Mutation scope must not widen via context assembly.
    pre_paths = set(contract.mutation_paths)
    try:
        packet = assemble_packet(
            contract=snapshot,
            workspace_root=workspace,
            evidence_path=evidence_path,
        )
    except TaskContextError as exc:
        raise IntegrationError(str(exc), code=getattr(exc, "code", "CONTEXT_FAILED")) from exc
    post_paths = set(packet.contract.mutation_paths)
    if not post_paths.issubset(pre_paths):
        raise IntegrationError(
            "context assembly widened mutation_paths",
            code="MUTATION_SCOPE_WIDENED",
        )
    fresh = check_freshness(packet, workspace_root=workspace)
    report, _ = project_from_live_contracts(
        contract_paths=[contract_path],
        claims=claims,
        enrollment=enrollment,
        dependency_status=dependency_status,
    )
    task_id = contract.source.item_id or contract.contract_id
    fresh_status = None
    if isinstance(fresh, dict):
        fresh_status = str(fresh.get("status") or fresh.get("overall") or fresh)
    review = build_review_package(
        report,
        task_id,
        context_packet=packet,
        freshness_status=fresh_status,
    )
    selection = select_next(report)
    return {
        "contract_id": contract.contract_id,
        "contract_digest": contract_digest(contract),
        "context_packet_id": packet.packet_id,
        "context_content_digest": packet.content_digest,
        "freshness": fresh if isinstance(fresh, dict) else {"raw": str(fresh)},
        "readiness_bucket": review.selection_bucket,
        "selection": {
            "selected_task_id": selection.selected_task_id,
            "explanation": list(selection.explanation),
            "empty_reasons": list(selection.empty_reasons),
        },
        "review_package": review.model_dump(mode="json"),
        "mutation_paths_unchanged": sorted(pre_paths) == sorted(post_paths),
        "execution_authorized": False,
        "independent_review": False,
        "real_launch_authorized": False,
    }
