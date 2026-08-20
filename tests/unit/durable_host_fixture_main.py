"""Subprocess entry for OUTER_SESSION_EXIT_DAG_CONTINUES.

Launched by a short-lived parent. The parent exits; this process remains.
"""

from __future__ import annotations

import sys
from pathlib import Path

from project_atlas.orchestration.autonomy.broker import ContinuationBroker
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.host_service import DurableHostService
from project_atlas.orchestration.autonomy.loop import CallableDispatchPort
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    AgentCapability,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    RiskTag,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.mutating_transport import (
    ProcessMutatingBackend,
    ProcessReadOnlyBackend,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor

PIN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _anchor() -> TrustedAnchorRecord:
    pred = "1111111111111111111111111111111111111111"
    cert = "3333333333333333333333333333333333333333"
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=PIN,
            trusted_tree=TREE,
            predecessor_main=pred,
            predecessor_tree="2222222222222222222222222222222222222222",
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-001D",
            source_directive="D-AS-ORCH-001D-OWNER-MERGE-010",
            source_pr=400,
            merge_commit=PIN,
            merge_parent_1=pred,
            merge_parent_2=cert,
            merge_tree=TREE,
            certified_head=cert,
            certified_tree=TREE,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/unit/d080-host-anchor.json",
            evidence_digest="aa" * 32,
            sequence=3,
            record_digest="00" * 32,
        )
    )


def _node(
    package_id: str,
    *,
    caps: tuple[AgentCapability, ...],
    deps: tuple[str, ...] = (),
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective=f"d080 fixture {package_id}",
        base_pin=PIN,
        dependencies=deps,
        mutation_surface=MutationSurface(
            surface_id=f"d080-{package_id[-8:]}",
            paths=(f"workers/{package_id}",),
            semantic="ORCHESTRATION_AUTONOMY_LOOP",
        ),
        execution_host_class=ExecutionHostClass.EXTERNAL_AGENT,
        agent_capabilities_required=caps,
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(
            certification_required=True,
            adversarial_required=True,
        ),
        state=NodeState.READY,
        risk_tags=(RiskTag.CONTROL_PLANE,),
    )


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    trusted = _anchor()
    gov = AutonomousGovernor(current_main=PIN, current_tree=TREE, trusted_anchor=trusted)
    gov.add_node(_node("AS-ORCH-D080-PKGA-001", caps=(AgentCapability.IMPLEMENT,)))
    gov.add_node(
        _node(
            "AS-ORCH-D080-PKGB-001",
            caps=(AgentCapability.VERIFY,),
            deps=("AS-ORCH-D080-PKGA-001",),
        )
    )
    gov.add_node(
        _node(
            "AS-ORCH-D080-PKGC-001",
            caps=(AgentCapability.IMPLEMENT,),
            deps=("AS-ORCH-D080-PKGB-001",),
        )
    )
    dispatch = CallableDispatchPort(
        lambda _root: {"dispatch_id": "unused-001d", "status": "RUNNING"},
        lambda _root, dispatch_id: {"dispatch_id": dispatch_id, "status": "RUNNING"},
    )
    broker = ContinuationBroker(
        governor=gov,
        trusted=trusted,
        store=root / "broker-store",
        root=root,
        loop_store=root / "loop-store",
        dispatch=dispatch,
    )
    mutating = ProcessMutatingBackend(root=root, store=root / "worker-store" / "mutating")
    readonly = ProcessReadOnlyBackend(root=root, store=root / "worker-store" / "readonly")
    service = DurableHostService(
        governor=gov,
        broker=broker,
        store=root / "host-store",
        root=root,
        trusted=trusted,
        mutating=mutating,
        readonly=readonly,
        poll_seconds=0.05,
        owner_backoff_seconds=0.05,
    )
    (root / "service.ready").write_text("ready\n", encoding="utf-8")
    service.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
