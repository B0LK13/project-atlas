"""Compose a derived work-queue projection from declared inputs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from project_atlas.orchestration.work_readiness.adapters import (
    ClaimPort,
    ContractPort,
    ContractView,
    DependencyPort,
    EnrollmentPort,
    ResultPort,
)
from project_atlas.orchestration.work_readiness.models import (
    Blocker,
    BlockerCode,
    DependencyStatus,
    ReadinessAxes,
    SelectionBucket,
    SourceObservation,
    TriState,
    WorkItemProjection,
    WorkQueueReport,
)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _paths_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """Path conflict check aligned with autonomy SURFACE_OVERLAP_GATE path sets.

    Exact path intersection (same rule as ``surfaces_overlap`` path clause).
    Also treats prefix containment as overlap so ``src/foo`` conflicts with
    ``src/foo/bar.py``. Does not invent a scheduler.
    """
    if not a or not b:
        return False
    left = set(a)
    right = set(b)
    if left & right:
        return True
    for lp in left:
        for rp in right:
            if lp.startswith(rp.rstrip("/") + "/") or rp.startswith(lp.rstrip("/") + "/"):
                return True
    return False


def project_item(
    *,
    task_id: str,
    source_ref: str,
    source_revision: str | None,
    objective: str,
    expected_result: str = "",
    priority: int | None = None,
    contract: ContractView | None,
    contract_port_reachable: bool,
    claims: ClaimPort,
    enrollment: EnrollmentPort,
    results: ResultPort,
    dependencies: DependencyPort,
    observed_at: str | None = None,
    other_mutation_index: dict[str, tuple[str, ...]] | None = None,
) -> WorkItemProjection:
    """Project one task. Missing inputs become UNKNOWN — never a positive ready.

    Peer-queue path overlaps are reported in ``capacity_view``, not as hard
    blockers here — only *active claims* create MUTATION_SCOPE_OVERLAP exclusions
    for offerability (reuse of lease/conflict signals without inventing a scheduler).
    """
    del other_mutation_index  # retained for API stability; peer conflicts → capacity_view
    stamp = observed_at or _now()
    blockers: list[Blocker] = []
    sources = [
        SourceObservation(
            source_id="backlog_or_input",
            revision=source_revision,
            observed_at=stamp,
            reachable=True,
        )
    ]

    contract_id = None
    contract_digest = None
    contract_valid = TriState.UNKNOWN
    mutation_paths: tuple[str, ...] = ()
    required_adapter = None
    required_caps: tuple[str, ...] = ()
    dep_ids: tuple[str, ...] = ()
    auth_ref = None
    limits: dict[str, Any] = {}

    if not contract_port_reachable:
        contract_valid = TriState.UNKNOWN
        blockers.append(
            Blocker(
                code=BlockerCode.SOURCE_UNREACHABLE,
                object_ref="contract_port",
                evidence=("contract adapter unreachable",),
                next_step="Restore the task-contract integration or supply a fixture bundle.",
                responsible_role="integrator",
                recheck_fields=("contract_valid", "contract_digest"),
            )
        )
        sources.append(
            SourceObservation(
                source_id="contract_port",
                revision=None,
                observed_at=stamp,
                reachable=False,
                stale=True,
            )
        )
    elif contract is None:
        contract_valid = TriState.NO
        blockers.append(
            Blocker(
                code=BlockerCode.MISSING_OR_STALE_CONTRACT,
                object_ref=task_id,
                evidence=("no contract bound to task",),
                next_step="Author or bind a validated task contract for this item.",
                responsible_role="implementer",
                recheck_fields=("contract_id", "contract_digest", "contract_valid"),
            )
        )
    else:
        contract_id = contract.contract_id
        contract_digest = contract.digest
        contract_valid = TriState.YES if contract.valid else TriState.NO
        mutation_paths = contract.mutation_paths
        required_adapter = contract.required_adapter
        required_caps = contract.required_capabilities
        dep_ids = contract.dependencies
        auth_ref = contract.authorization_ref
        limits = dict(contract.limits)
        objective = contract.objective or objective
        expected_result = contract.expected_result or expected_result
        if contract.priority is not None:
            priority = contract.priority
        if not contract.valid:
            blockers.append(
                Blocker(
                    code=BlockerCode.MISSING_OR_STALE_CONTRACT,
                    object_ref=contract.contract_id,
                    evidence=(f"digest={contract.digest}", "valid=false"),
                    next_step="Repair the contract until validation passes.",
                    responsible_role="implementer",
                    recheck_fields=("contract_valid",),
                )
            )
        sources.append(
            SourceObservation(
                source_id="contract",
                revision=contract.digest,
                observed_at=stamp,
                reachable=True,
            )
        )

    dep_rows: list[DependencyStatus] = []
    deps_axis = TriState.YES
    for dep_id in dep_ids:
        node = dependencies.status_for(dep_id)
        dep_rows.append(
            DependencyStatus(dependency_id=dep_id, status=node.status, evidence=node.evidence)
        )
        if node.status is TriState.NO:
            deps_axis = TriState.NO
            blockers.append(
                Blocker(
                    code=BlockerCode.UNSATISFIED_DEPENDENCY,
                    object_ref=dep_id,
                    evidence=((node.evidence,) if node.evidence else ()),
                    next_step=f"Complete or unblock dependency {dep_id}.",
                    responsible_role="owner",
                    recheck_fields=("dependencies",),
                )
            )
        elif node.status is TriState.UNKNOWN:
            deps_axis = TriState.UNKNOWN if deps_axis is not TriState.NO else TriState.NO
            blockers.append(
                Blocker(
                    code=BlockerCode.UNKNOWN_DEPENDENCY,
                    object_ref=dep_id,
                    evidence=("dependency status UNKNOWN",),
                    next_step=f"Obtain an observable status for dependency {dep_id}.",
                    responsible_role="operator",
                    recheck_fields=("dependencies",),
                )
            )

    active = claims.active_claims()
    owner = None
    claim_id = None
    claim_agent = None
    ownership_axis = TriState.YES
    for claim in active:
        if claim.task_or_package_id == task_id:
            owner = claim.agent_id
            claim_id = claim.lease_id
            claim_agent = claim.agent_id
            ownership_axis = TriState.NO
            blockers.append(
                Blocker(
                    code=BlockerCode.ACTIVE_FOREIGN_CLAIM,
                    object_ref=claim.lease_id,
                    evidence=(f"agent={claim.agent_id}",),
                    next_step="Wait for release or coordinate with the claiming agent.",
                    responsible_role="claiming_agent",
                    known_owner=claim.agent_id,
                    recheck_fields=("active_claim_id", "ownership_clear"),
                )
            )
        elif (
            mutation_paths
            and claim.mutation_paths
            and _paths_overlap(mutation_paths, claim.mutation_paths)
        ):
            blockers.append(
                Blocker(
                    code=BlockerCode.MUTATION_SCOPE_OVERLAP,
                    object_ref=claim.lease_id,
                    evidence=(
                        f"active claim by {claim.agent_id}",
                        f"task={claim.task_or_package_id}",
                    ),
                    next_step="Wait for the overlapping claim to release before offering.",
                    responsible_role="claiming_agent",
                    known_owner=claim.agent_id,
                    recheck_fields=("mutation_paths", "mutation_conflict_clear"),
                )
            )

    mutation_axis = TriState.YES
    if any(b.code is BlockerCode.MUTATION_SCOPE_OVERLAP for b in blockers):
        mutation_axis = TriState.NO

    runtime_axis = TriState.UNKNOWN
    agents = enrollment.agents()
    if required_adapter:
        matches = [a for a in agents if a.adapter == required_adapter and a.status == "ACTIVE"]
        if not agents:
            runtime_axis = TriState.UNKNOWN
            blockers.append(
                Blocker(
                    code=BlockerCode.MISSING_RUNTIME_CAPACITY,
                    object_ref=required_adapter,
                    evidence=("enrollment roster empty or unread",),
                    next_step="Inspect enrollment; UNKNOWN capacity is not free capacity.",
                    responsible_role="operator",
                    recheck_fields=("runtime_available",),
                )
            )
        elif not matches:
            runtime_axis = TriState.NO
            blockers.append(
                Blocker(
                    code=BlockerCode.MISSING_RUNTIME_CAPACITY,
                    object_ref=required_adapter,
                    evidence=(f"no ACTIVE agent with adapter={required_adapter}",),
                    next_step="Enroll/activate a matching runtime or change the contract adapter.",
                    responsible_role="operator",
                    recheck_fields=("runtime_available",),
                )
            )
        else:
            # Capability intersection when declared.
            if required_caps:
                capable = [a for a in matches if set(required_caps).issubset(set(a.capabilities))]
                runtime_axis = TriState.YES if capable else TriState.NO
                if not capable:
                    blockers.append(
                        Blocker(
                            code=BlockerCode.MISSING_RUNTIME_CAPACITY,
                            object_ref=required_adapter,
                            evidence=(f"capabilities required={list(required_caps)}",),
                            next_step="Activate an agent that provides the required capabilities.",
                            responsible_role="operator",
                            recheck_fields=("runtime_available",),
                        )
                    )
            else:
                runtime_axis = TriState.YES
    else:
        runtime_axis = TriState.UNKNOWN

    auth_axis = TriState.YES if auth_ref else TriState.NO
    if not auth_ref:
        blockers.append(
            Blocker(
                code=BlockerCode.MISSING_AUTHORIZATION,
                object_ref=task_id,
                evidence=("no verified authorization_ref on contract",),
                next_step="Attach a verified registry/program/owner authorization reference.",
                responsible_role="owner",
                recheck_fields=("execution_authorized", "authorization_ref"),
            )
        )

    result = results.result_for(task_id)
    worker_exit = result.worker_exit_zero if result else None
    acceptance = result.acceptance_passed if result else None
    review_axis = TriState.UNKNOWN
    complete_axis = TriState.NO
    if result:
        if result.acceptance_passed is False and result.worker_exit_zero:
            blockers.append(
                Blocker(
                    code=BlockerCode.WORKER_EXIT_NOT_COMPLETION,
                    object_ref=result.evidence_ref or task_id,
                    evidence=("worker_exit_zero=true", "acceptance_passed=false"),
                    next_step="Treat as acceptance failure; do not mark lifecycle complete.",
                    responsible_role="operator",
                    recheck_fields=("acceptance_passed", "lifecycle_complete"),
                )
            )
            blockers.append(
                Blocker(
                    code=BlockerCode.ACCEPTANCE_FAILED,
                    object_ref=result.evidence_ref or task_id,
                    evidence=("acceptance_passed=false",),
                    next_step="Repair the artifact or revise the contract; do not relaunch.",
                    responsible_role="implementer",
                    recheck_fields=("acceptance_passed",),
                )
            )
        if result.acceptance_passed is True and result.review_complete is not True:
            review_axis = TriState.NO
            blockers.append(
                Blocker(
                    code=BlockerCode.AWAITING_INDEPENDENT_REVIEW,
                    object_ref=task_id,
                    evidence=("acceptance_passed=true", "review_complete!=true"),
                    next_step="Schedule independent review; acceptance is not review.",
                    responsible_role="reviewer",
                    recheck_fields=("ready_for_independent_review",),
                )
            )
        elif result.review_complete is True and result.acceptance_passed is True:
            review_axis = TriState.YES
            complete_axis = TriState.YES

    content_axis = (
        TriState.YES
        if contract_valid is TriState.YES and objective.strip()
        else TriState.NO
        if contract_valid is TriState.NO
        else TriState.UNKNOWN
    )
    technical_axis = (
        TriState.YES
        if contract_valid is TriState.YES and mutation_paths and required_adapter
        else TriState.NO
        if contract_valid is TriState.NO
        else TriState.UNKNOWN
    )

    axes = ReadinessAxes(
        content_prepared=content_axis,
        technically_prepared=technical_axis,
        dependencies_satisfied=deps_axis,
        ownership_clear=ownership_axis,
        mutation_conflict_clear=mutation_axis,
        runtime_available=runtime_axis,
        execution_authorized=auth_axis,
        ready_for_independent_review=review_axis,
        lifecycle_complete=complete_axis,
    )

    hard_block_codes = {
        BlockerCode.MISSING_OR_STALE_CONTRACT,
        BlockerCode.UNSATISFIED_DEPENDENCY,
        BlockerCode.UNKNOWN_DEPENDENCY,
        BlockerCode.ACTIVE_FOREIGN_CLAIM,
        BlockerCode.MUTATION_SCOPE_OVERLAP,
        BlockerCode.MISSING_RUNTIME_CAPACITY,
        BlockerCode.SOURCE_UNREACHABLE,
        BlockerCode.SOURCE_CONFLICTING,
        BlockerCode.EXECUTION_LIMIT_EXHAUSTED,
        BlockerCode.CI_OR_REVIEW_INCOMPLETE,
        BlockerCode.ACCEPTANCE_FAILED,
        BlockerCode.UNKNOWN_OWNERSHIP,
    }
    hard = [b for b in blockers if b.code in hard_block_codes]
    explanation: list[str] = []

    if complete_axis is TriState.YES:
        bucket = SelectionBucket.COMPLETE
        explanation.append("lifecycle_complete=YES under observed acceptance+review evidence")
    elif hard:
        bucket = SelectionBucket.BLOCKED
        explanation.append(f"hard blockers: {', '.join(sorted({b.code.value for b in hard}))}")
    elif (
        content_axis is TriState.YES
        and technical_axis is TriState.YES
        and deps_axis is TriState.YES
        and ownership_axis is TriState.YES
        and mutation_axis is TriState.YES
        and runtime_axis is TriState.YES
        and auth_axis is TriState.YES
    ):
        bucket = SelectionBucket.OFFERABLE_TO_DISPATCHER
        explanation.append("all hard suitability axes YES including verified auth_ref")
    elif (
        content_axis is TriState.YES
        and technical_axis is TriState.YES
        and deps_axis is TriState.YES
        and ownership_axis is TriState.YES
        and mutation_axis is TriState.YES
        and auth_axis is TriState.NO
        and not hard
    ):
        bucket = SelectionBucket.CONTENT_READY_AWAITING_AUTHORIZATION
        explanation.append(
            "technically ready; execution_authorized=NO (launch authorization pending)"
        )
        # Keep MISSING_AUTHORIZATION visible but bucket is awaiting-auth, not offerable.
    else:
        bucket = SelectionBucket.BLOCKED
        explanation.append(
            "one or more readiness axes are NO/UNKNOWN without soft-auth-only pattern"
        )

    # Exhausted limits (if declared on contract)
    if limits.get("launches_remaining") == 0:
        blockers.append(
            Blocker(
                code=BlockerCode.EXECUTION_LIMIT_EXHAUSTED,
                object_ref=task_id,
                evidence=("launches_remaining=0",),
                next_step="Do not relaunch; obtain a new authorized program/attempt budget.",
                responsible_role="owner",
                recheck_fields=("execution_limits",),
            )
        )
        bucket = SelectionBucket.BLOCKED

    return WorkItemProjection(
        task_id=task_id,
        source_ref=source_ref,
        source_revision=source_revision,
        contract_id=contract_id,
        contract_digest=contract_digest,
        contract_valid=contract_valid,
        objective=objective,
        expected_result=expected_result,
        owner=owner,
        active_claim_id=claim_id,
        active_claim_agent=claim_agent,
        dependencies=tuple(dep_rows),
        mutation_paths=mutation_paths,
        required_capabilities=required_caps,
        required_adapter=required_adapter,
        priority=priority,
        axes=axes,
        blockers=tuple(blockers),
        bucket=bucket,
        authorization_ref=auth_ref,
        acceptance_ref=result.evidence_ref if result else None,
        worker_exit_zero=worker_exit,
        acceptance_passed=acceptance,
        sources=tuple(sources),
        observed_at=stamp,
        selection_explanation=tuple(explanation),
    )


def project_queue(
    *,
    seeds: Iterable[dict[str, Any]],
    contracts: ContractPort,
    claims: ClaimPort,
    enrollment: EnrollmentPort,
    results: ResultPort,
    dependencies: DependencyPort,
    contract_port_reachable: bool = True,
    observed_at: str | None = None,
    fixture_adapters_used: tuple[str, ...] = (),
    missing_integrations: tuple[str, ...] = (),
    source_revisions: dict[str, str] | None = None,
) -> WorkQueueReport:
    """Project many tasks; compute shared-blocker impact."""
    stamp = observed_at or _now()
    seed_list = list(seeds)

    items: list[WorkItemProjection] = []
    for seed in seed_list:
        tid = seed["task_id"]
        c = contracts.load_for_task(tid) if contract_port_reachable else None
        items.append(
            project_item(
                task_id=tid,
                source_ref=seed.get("source_ref", "unknown"),
                source_revision=seed.get("source_revision"),
                objective=seed.get("objective", tid),
                expected_result=seed.get("expected_result", ""),
                priority=seed.get("priority"),
                contract=c,
                contract_port_reachable=contract_port_reachable,
                claims=claims,
                enrollment=enrollment,
                results=results,
                dependencies=dependencies,
                observed_at=stamp,
            )
        )

    # Shared blocker impact: group by (code, object_ref)
    impact: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in items:
        for b in item.blockers:
            impact[(b.code.value, b.object_ref)].append(item.task_id)

    shared: list[Blocker] = []
    for (code, obj), task_ids in sorted(impact.items()):
        if len(task_ids) < 2:
            continue
        sample = next(
            b for it in items for b in it.blockers if b.code.value == code and b.object_ref == obj
        )
        shared.append(
            Blocker(
                code=sample.code,
                object_ref=obj,
                evidence=tuple(sorted(task_ids)),
                next_step=sample.next_step,
                responsible_role=sample.responsible_role,
                known_owner=sample.known_owner,
                recheck_fields=sample.recheck_fields,
                dependency_impact=len(task_ids),
            )
        )

    # Annotate per-item dependency_impact where shared
    impact_lookup = {(b.code, b.object_ref): b.dependency_impact for b in shared}
    annotated: list[WorkItemProjection] = []
    for item in items:
        new_blockers = []
        for b in item.blockers:
            key = (b.code, b.object_ref)
            if impact_lookup.get(key):
                new_blockers.append(b.model_copy(update={"dependency_impact": impact_lookup[key]}))
            else:
                new_blockers.append(b)
        annotated.append(item.model_copy(update={"blockers": tuple(new_blockers)}))

    offerable = tuple(
        i.task_id for i in annotated if i.bucket is SelectionBucket.OFFERABLE_TO_DISPATCHER
    )
    awaiting = tuple(
        i.task_id
        for i in annotated
        if i.bucket is SelectionBucket.CONTENT_READY_AWAITING_AUTHORIZATION
    )
    blocked = tuple(i.task_id for i in annotated if i.bucket is SelectionBucket.BLOCKED)

    empty_reasons: list[str] = []
    if not offerable:
        empty_reasons.append(
            "no task passed all hard suitability axes including verified authorization"
        )
        if awaiting:
            empty_reasons.append(
                f"{len(awaiting)} task(s) content-ready but awaiting launch authorization"
            )
        if blocked:
            empty_reasons.append(f"{len(blocked)} task(s) blocked with concrete next steps")
        if not annotated:
            empty_reasons.append("input seed list was empty; no filler tasks invented")

    return WorkQueueReport(
        observed_at=stamp,
        source_revisions=dict(source_revisions or {}),
        items=tuple(annotated),
        shared_blockers=tuple(shared),
        offerable=offerable,
        awaiting_authorization=awaiting,
        blocked=blocked,
        empty_queue_reasons=tuple(empty_reasons),
        fixture_adapters_used=fixture_adapters_used,
        missing_integrations=missing_integrations,
    )
