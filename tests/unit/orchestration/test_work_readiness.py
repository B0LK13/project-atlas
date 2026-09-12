"""Hermetic tests for AS-WORK-READINESS-001. Zero model calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.work_readiness.adapters import (
    ClaimView,
    FixtureClaimPort,
    ports_from_fixture_bundle,
)
from project_atlas.orchestration.work_readiness.capacity import capacity_view
from project_atlas.orchestration.work_readiness.handoff import prepare_handoff, refresh_handoff
from project_atlas.orchestration.work_readiness.models import (
    BlockerCode,
    SelectionBucket,
    TriState,
)
from project_atlas.orchestration.work_readiness.project import project_queue
from project_atlas.orchestration.work_readiness.select import select_next

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "work_readiness"
    / "positive_and_negative.v1.json"
)


@pytest.fixture
def ports():
    return ports_from_fixture_bundle(FIXTURE)


def _report(ports, *, seeds=None, contract_reachable=True):
    contracts, claims, enrollment, results, deps, missing = ports
    if seeds is None:
        seeds = [
            {
                "task_id": tid,
                "source_ref": f"fixture:{tid}",
                "source_revision": "v1",
                "objective": c.objective,
                "priority": c.priority,
            }
            for tid, c in contracts.contracts.items()
        ]
    return project_queue(
        seeds=seeds,
        contracts=contracts,
        claims=claims,
        enrollment=enrollment,
        results=results,
        dependencies=deps,
        contract_port_reachable=contract_reachable,
        observed_at="1970-01-01T00:00:00Z",
        fixture_adapters_used=(contracts.fixture_id,),
        missing_integrations=missing,
        source_revisions={"fixture": "v1"},
    ), enrollment


def test_complete_suitable_task_selected_with_explanation(ports):
    report, _ = _report(ports)
    selection = select_next(report)
    assert selection.selected_task_id == "WR-READY-001"
    assert selection.bucket is SelectionBucket.OFFERABLE_TO_DISPATCHER
    assert any("selected=WR-READY-001" in line for line in selection.explanation)
    assert any("no model score" in line for line in selection.explanation)


def test_blocked_dependency_excludes_selection(ports):
    report, _ = _report(ports)
    item = next(i for i in report.items if i.task_id == "WR-BLOCKED-DEP")
    assert item.bucket is SelectionBucket.BLOCKED
    assert any(b.code is BlockerCode.UNSATISFIED_DEPENDENCY for b in item.blockers)
    assert "WR-BLOCKED-DEP" not in report.offerable


def test_unknown_data_not_positive_ready(ports):
    report, _ = _report(ports, contract_reachable=False)
    for item in report.items:
        assert item.bucket is not SelectionBucket.OFFERABLE_TO_DISPATCHER
        assert (
            item.axes.content_prepared is not TriState.YES
            or item.contract_valid is TriState.UNKNOWN
        )


def test_active_claim_blocks_second_executor(ports):
    report, _ = _report(ports)
    item = next(i for i in report.items if i.task_id == "WR-CLAIMED")
    assert item.bucket is SelectionBucket.BLOCKED
    assert any(b.code is BlockerCode.ACTIVE_FOREIGN_CLAIM for b in item.blockers)
    selection = select_next(report)
    assert selection.selected_task_id != "WR-CLAIMED"


def test_mutation_conflict_via_overlap_logic(ports):
    report, _ = _report(ports)
    item = next(i for i in report.items if i.task_id == "WR-OVERLAP")
    assert any(b.code is BlockerCode.MUTATION_SCOPE_OVERLAP for b in item.blockers)
    assert item.bucket is SelectionBucket.BLOCKED


def test_contract_change_invalidates_handoff(ports):
    report, _enrollment = _report(ports)
    proposal = prepare_handoff(
        report, "WR-READY-001", proposed_agent_or_capabilities="agent-codex-1"
    )
    contracts, claims, enr, results, deps, _missing = ports
    # Mutate digest on the ready contract
    old = contracts.contracts["WR-READY-001"]
    from dataclasses import replace

    new_contracts = type(contracts)(
        contracts={
            **contracts.contracts,
            "WR-READY-001": replace(old, digest="digest-ready-CHANGED"),
        }
    )
    report2 = project_queue(
        seeds=[{"task_id": "WR-READY-001", "source_ref": "f", "objective": "x", "priority": 10}],
        contracts=new_contracts,
        claims=claims,
        enrollment=enr,
        results=results,
        dependencies=deps,
        observed_at="1970-01-01T00:00:00Z",
        source_revisions={"fixture": "v1"},
    )
    refreshed = refresh_handoff(proposal, report2)
    assert refreshed.expired is True
    assert refreshed.expire_reason and "contract_digest changed" in refreshed.expire_reason


def test_ownership_change_detected_on_refresh(ports):
    report, _ = _report(ports)
    proposal = prepare_handoff(
        report, "WR-READY-001", proposed_agent_or_capabilities="agent-codex-1"
    )
    contracts, _claims, enrollment, results, deps, _missing = ports
    claimed = FixtureClaimPort(
        claims=(
            ClaimView(
                lease_id="lease-new",
                agent_id="agent-beta",
                task_or_package_id="WR-READY-001",
                mutation_paths=("src/project_atlas/orchestration/work_readiness/",),
                status="ACTIVE",
            ),
        )
    )
    report2 = project_queue(
        seeds=[{"task_id": "WR-READY-001", "source_ref": "f", "objective": "x", "priority": 10}],
        contracts=contracts,
        claims=claimed,
        enrollment=enrollment,
        results=results,
        dependencies=deps,
        observed_at="1970-01-01T00:00:00Z",
        source_revisions={"fixture": "v1"},
    )
    refreshed = refresh_handoff(proposal, report2)
    assert refreshed.expired is True
    assert "active claim" in (refreshed.expire_reason or "")


def test_identical_input_same_ranking(ports):
    report1, _ = _report(ports)
    report2, _ = _report(ports)
    s1 = select_next(report1)
    s2 = select_next(report2)
    assert s1.selected_task_id == s2.selected_task_id
    assert s1.rank_key == s2.rank_key
    assert report1.model_dump(mode="json") == report2.model_dump(mode="json")


def test_repeated_handoff_prep_no_duplicates(ports):
    report, _ = _report(ports)
    a = prepare_handoff(report, "WR-READY-001", proposed_agent_or_capabilities="agent-codex-1")
    b = prepare_handoff(report, "WR-READY-001", proposed_agent_or_capabilities="agent-codex-1")
    assert a.handoff_id == b.handoff_id
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_missing_launch_authorization_separate(ports):
    report, _ = _report(ports)
    assert "WR-AWAIT-AUTH" in report.awaiting_authorization
    item = next(i for i in report.items if i.task_id == "WR-AWAIT-AUTH")
    assert item.bucket is SelectionBucket.CONTENT_READY_AWAITING_AUTHORIZATION
    assert item.axes.execution_authorized is TriState.NO
    assert item.axes.technically_prepared is TriState.YES
    assert "WR-AWAIT-AUTH" not in report.offerable


def test_worker_exit_zero_acceptance_failure_not_complete(ports):
    report, _ = _report(ports)
    item = next(i for i in report.items if i.task_id == "WR-EXIT-NOT-DONE")
    assert item.worker_exit_zero is True
    assert item.acceptance_passed is False
    assert item.axes.lifecycle_complete is TriState.NO
    assert any(b.code is BlockerCode.WORKER_EXIT_NOT_COMPLETION for b in item.blockers)
    assert any(b.code is BlockerCode.ACCEPTANCE_FAILED for b in item.blockers)


def test_source_outage_not_free_capacity(ports):
    report, enrollment = _report(ports, contract_reachable=False)
    assert report.offerable == ()
    for item in report.items:
        assert any(b.code is BlockerCode.SOURCE_UNREACHABLE for b in item.blockers)
    cap = capacity_view(report, enrollment)
    assert cap.raises_limits is False


def test_empty_suitable_queue_gives_reasons_no_filler(ports):
    contracts, claims, enrollment, results, deps, _missing = ports
    # Only blocked seeds
    seeds = [
        {"task_id": "WR-BLOCKED-DEP", "source_ref": "f", "objective": "x", "priority": 1},
        {"task_id": "WR-STALE-CONTRACT", "source_ref": "f", "objective": "y", "priority": 2},
    ]
    report = project_queue(
        seeds=seeds,
        contracts=contracts,
        claims=claims,
        enrollment=enrollment,
        results=results,
        dependencies=deps,
        observed_at="1970-01-01T00:00:00Z",
        source_revisions={"fixture": "v1"},
    )
    selection = select_next(report)
    assert selection.selected_task_id is None
    assert selection.empty_reasons
    assert not any("invent" in r.lower() for r in selection.empty_reasons)


def test_shared_blocker_dependency_impact(ports):
    report, _ = _report(ports)
    shared = [b for b in report.shared_blockers if b.object_ref == "DEP-MISSING-001"]
    assert shared
    assert shared[0].dependency_impact == 2


def test_missing_priority_not_silent_zero(ports):
    contracts, claims, enrollment, results, deps, _missing = ports
    from dataclasses import replace

    # Two offerable-like tasks: one without priority must sort after known priority.
    c1 = replace(
        contracts.contracts["WR-READY-001"], priority=None, mutation_paths=("a/",), digest="d1"
    )
    c2 = replace(
        contracts.contracts["WR-READY-002"],
        priority=1,
        mutation_paths=("b/",),
        digest="d2",
        authorization_ref="registry://verified/auth/p",
    )
    new_c = type(contracts)(contracts={"WR-READY-001": c1, "WR-READY-002": c2})
    report = project_queue(
        seeds=[
            {"task_id": "WR-READY-001", "source_ref": "f", "objective": "x"},
            {"task_id": "WR-READY-002", "source_ref": "f", "objective": "y"},
        ],
        contracts=new_c,
        claims=claims,
        enrollment=enrollment,
        results=results,
        dependencies=deps,
        observed_at="1970-01-01T00:00:00Z",
        source_revisions={"fixture": "v1"},
    )
    selection = select_next(report)
    assert selection.selected_task_id == "WR-READY-002"


def test_proposal_does_not_reserve_work(ports):
    report, _ = _report(ports)
    proposal = prepare_handoff(report, "WR-READY-001", proposed_agent_or_capabilities="x")
    assert proposal.reserves_work is False
    assert proposal.execution_authorized is False
    assert proposal.merge_authorized is False
