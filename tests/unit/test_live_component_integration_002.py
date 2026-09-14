"""Hermetic live-interface integration tests. Zero model calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.orchestration.live_integration.bridge import (
    IntegrationError,
    live_contract_to_context_snapshot,
    live_contract_to_readiness_view,
    load_live_task_contract,
    project_from_live_contracts,
    run_controlled_chain,
)
from project_atlas.orchestration.taskcontract.models import contract_digest
from project_atlas.orchestration.work_readiness.adapters import (
    DependencyNodeView,
    EnrollmentView,
)
from project_atlas.orchestration.work_readiness.handoff import prepare_handoff, refresh_handoff
from project_atlas.orchestration.work_readiness.models import (
    BlockerCode,
    SelectionBucket,
    TriState,
)
from project_atlas.task_context.assemble import assemble_packet

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "live_integration"
CTX_REPO = (
    Path(__file__).resolve().parents[1] / "fixtures" / "task-context-continuity" / "repo"
)
OWNED = FIX / "LCI-002-TEST-OWNED.contract.json"
INT013 = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "orchestration"
    / "taskcontract"
    / "demo"
    / "contract.v1.json"
)


def _enrollment() -> tuple[EnrollmentView, ...]:
    return (
        EnrollmentView(
            agent_id="test-local-1",
            adapter="local-command",
            status="ACTIVE",
            capabilities=("IMPLEMENT",),
        ),
    )


def _deps_ok() -> dict[str, DependencyNodeView]:
    return {
        "LCI-DEP-SATISFIED": DependencyNodeView(
            node_id="LCI-DEP-SATISFIED",
            status=TriState.YES,
            evidence="test-owned dependency satisfied",
        )
    }


def test_contract_flows_to_context_and_readiness_without_duplication():
    tc = load_live_task_contract(OWNED)
    snap = live_contract_to_context_snapshot(tc)
    view = live_contract_to_readiness_view(tc)
    assert snap.contract_id == tc.contract_id == view.contract_id
    assert snap.mutation_paths == tc.mutation_paths == view.mutation_paths
    assert view.digest == contract_digest(tc)
    assert snap.source_kind == "LIVE_MODULE"
    packet = assemble_packet(contract=snap, workspace_root=CTX_REPO)
    assert packet.contract.mutation_paths == tc.mutation_paths
    report, _ = project_from_live_contracts(
        contract_paths=[OWNED],
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
        ownership_registry_reachable=True,
    )
    item = report.items[0]
    assert item.contract_digest == contract_digest(tc)
    assert item.contract_id == tc.contract_id


def test_contract_change_invalidates_context_and_handoff():
    tc = load_live_task_contract(OWNED)
    snap = live_contract_to_context_snapshot(tc)
    packet = assemble_packet(contract=snap, workspace_root=CTX_REPO)
    report, _ = project_from_live_contracts(
        contract_paths=[OWNED],
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
    )
    proposal = prepare_handoff(
        report, "LCI-002-TEST-OWNED", proposed_agent_or_capabilities="test-local-1"
    )
    # Mutate objective → new digest
    raw = json.loads(OWNED.read_text(encoding="utf-8"))
    raw["objective"] = "CHANGED objective for invalidation proof"
    changed = FIX / "_changed.contract.json"
    changed.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        report2, _ = project_from_live_contracts(
            contract_paths=[changed],
            enrollment=_enrollment(),
            dependency_status=_deps_ok(),
        )
        refreshed = refresh_handoff(proposal, report2)
        assert refreshed.expired is True
        assert "contract_digest changed" in (refreshed.expire_reason or "")
        # Context packet identity must change when the live contract changes.
        snap2 = live_contract_to_context_snapshot(load_live_task_contract(changed))
        packet2 = assemble_packet(contract=snap2, workspace_root=CTX_REPO)
        assert packet.content_digest != packet2.content_digest
        assert contract_digest(tc) != contract_digest(load_live_task_contract(changed))
    finally:
        changed.unlink(missing_ok=True)


def test_missing_dependency_blocks_execution_readiness():
    report, _ = project_from_live_contracts(
        contract_paths=[OWNED],
        enrollment=_enrollment(),
        dependency_status={
            "LCI-DEP-SATISFIED": DependencyNodeView(
                node_id="LCI-DEP-SATISFIED",
                status=TriState.NO,
                evidence="unsatisfied in test",
            )
        },
    )
    item = report.items[0]
    assert item.bucket is SelectionBucket.BLOCKED
    assert any(b.code is BlockerCode.UNSATISFIED_DEPENDENCY for b in item.blockers)


def test_unknown_ownership_not_free_capacity():
    report, _ = project_from_live_contracts(
        contract_paths=[OWNED],
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
        ownership_registry_reachable=False,
    )
    assert report.offerable == ()
    item = report.items[0]
    assert item.bucket is SelectionBucket.BLOCKED
    assert any(b.code is BlockerCode.UNKNOWN_OWNERSHIP for b in item.blockers)


def test_context_does_not_widen_mutation_scope():
    chain = run_controlled_chain(
        contract_path=OWNED,
        workspace=CTX_REPO,
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
    )
    assert chain["mutation_paths_unchanged"] is True


def test_repeated_generation_stable_digests_no_duplicate_handoff():
    a = run_controlled_chain(
        contract_path=OWNED,
        workspace=CTX_REPO,
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
    )
    b = run_controlled_chain(
        contract_path=OWNED,
        workspace=CTX_REPO,
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
    )
    assert a["contract_digest"] == b["contract_digest"]
    assert a["context_content_digest"] == b["context_content_digest"]
    assert a["review_package"]["handoff_id"] == b["review_package"]["handoff_id"]


def test_incompatible_schema_errors_without_fixture_fallback():
    bad = FIX / "_bad.schema.json"
    bad.write_text('{"schema_version": 1, "not_a_task_contract": true}\n', encoding="utf-8")
    try:
        with pytest.raises(IntegrationError) as exc:
            load_live_task_contract(bad)
        assert exc.value.code == "SCHEMA_INCOMPATIBLE"
    finally:
        bad.unlink(missing_ok=True)


def test_int013_valid_program_does_not_clear_external_blocked():
    """INT-013 read-only: generated contract remains EXTERNAL_BLOCKED / not launchable."""
    tc = load_live_task_contract(INT013)
    assert tc.execution_authorized is False
    assert tc.merge_authorized is False
    blocked_markers = " ".join(tc.executable_when) + " " + " ".join(tc.exclusions)
    assert "EXTERNAL_BLOCKED" in blocked_markers or "external_blocked" in blocked_markers.lower()
    # Readiness must not offer INT-013 as launchable without live auth + enrollment.
    report, _ = project_from_live_contracts(
        contract_paths=[INT013],
        enrollment=(),  # no runtime
        dependency_status={},
        ownership_registry_reachable=True,
    )
    item = next(i for i in report.items if i.task_id == "INT-013")
    assert item.bucket is not SelectionBucket.OFFERABLE_TO_DISPATCHER
    assert item.axes.execution_authorized is not TriState.YES or item.authorization_ref


def test_cli_groups_still_registered():
    from project_atlas.cli import build_parser

    parser = build_parser()
    cmd = next(a for a in parser._actions if a.dest == "command")
    choices = set(cmd.choices or [])
    for required in ("task", "task-context", "work-readiness", "program", "agent"):
        assert required in choices, f"missing CLI group: {required}"
    assert "live-integrate" in choices


def test_positive_selection_on_test_owned_only():
    chain = run_controlled_chain(
        contract_path=OWNED,
        workspace=CTX_REPO,
        enrollment=_enrollment(),
        dependency_status=_deps_ok(),
    )
    # With auth_ref + enrollment + deps, may be offerable or awaiting depending
    # on axes — either way review package points at live digest.
    assert chain["review_package"]["contract_id"] == "LCI-002-TEST-OWNED"
    assert chain["review_package"]["contract_digest"] == chain["contract_digest"]
    assert chain["review_package"]["context_packet_id"]
    assert chain["independent_review"] is False
    assert chain["real_launch_authorized"] is False
