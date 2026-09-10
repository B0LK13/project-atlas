"""CLI for ATLAS-LIVE-COMPONENT-INTEGRATION-002."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.orchestration.live_integration.bridge import (
    IntegrationError,
    project_from_live_contracts,
    run_controlled_chain,
)
from project_atlas.orchestration.live_integration.models import (
    ComponentManifest,
    IntegrationReport,
)
from project_atlas.orchestration.work_readiness.adapters import (
    DependencyNodeView,
    EnrollmentView,
)
from project_atlas.orchestration.work_readiness.models import TriState

COMMAND = "live-integrate"


def register_live_integrate_parsers(subparsers: argparse._SubParsersAction[Any]) -> None:
    root = subparsers.add_parser(
        COMMAND,
        help=(
            "Live wiring of taskcontract+context+readiness "
            "(AS-LIVE-COMPONENT-INTEGRATION-002; ≠ launch authority)."
        ),
    )
    sub = root.add_subparsers(dest="live_integrate_command", required=True)

    demo = sub.add_parser(
        "demo",
        help="INT-013 read-only EXTERNAL_BLOCKED proof + test-owned positive path.",
    )
    demo.add_argument("--int013-contract", type=Path, required=True)
    demo.add_argument("--owned-contract", type=Path, required=True)
    demo.add_argument("--workspace", type=Path, required=True)
    demo.add_argument("--out", type=Path, required=True)
    demo.add_argument("--json", action="store_true")

    chain = sub.add_parser("chain", help="Run controlled chain for one live contract.")
    chain.add_argument("--contract", type=Path, required=True)
    chain.add_argument("--workspace", type=Path, required=True)
    chain.add_argument("--out", type=Path, default=None)


def dispatch_live_integrate(args: argparse.Namespace) -> int | None:
    if getattr(args, "command", None) != COMMAND:
        return None
    cmd = args.live_integrate_command
    if cmd == "demo":
        return _demo(args)
    if cmd == "chain":
        enrollment = (
            EnrollmentView(
                agent_id="demo-local",
                adapter="local-command",
                status="ACTIVE",
                capabilities=("IMPLEMENT",),
            ),
        )
        deps = {
            "LCI-DEP-SATISFIED": DependencyNodeView(
                node_id="LCI-DEP-SATISFIED",
                status=TriState.YES,
                evidence="demo dependency",
            )
        }
        try:
            result = run_controlled_chain(
                contract_path=args.contract,
                workspace=args.workspace,
                enrollment=enrollment,
                dependency_status=deps,
            )
        except IntegrationError as exc:
            print(json.dumps({"error": str(exc), "code": exc.code}, indent=2))
            return 1
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    raise SystemExit(f"unknown live-integrate command: {cmd}")


def _demo(args: argparse.Namespace) -> int:
    # Phase A: INT-013 remains non-offerable / EXTERNAL_BLOCKED preserved.
    int_report, _ = project_from_live_contracts(
        contract_paths=[args.int013_contract],
        enrollment=(),
        ownership_registry_reachable=True,
    )
    int_item = int_report.items[0]
    external_blocked_preserved = (
        int_item.bucket.value != "OFFERABLE_TO_DISPATCHER"
        and int_item.axes.lifecycle_complete.value != "YES"
    )

    # Phase B: test-owned positive path (does not mutate real backlog).
    enrollment = (
        EnrollmentView(
            agent_id="demo-local",
            adapter="local-command",
            status="ACTIVE",
            capabilities=("IMPLEMENT",),
        ),
    )
    deps = {
        "LCI-DEP-SATISFIED": DependencyNodeView(
            node_id="LCI-DEP-SATISFIED",
            status=TriState.YES,
            evidence="demo dependency",
        )
    }
    try:
        chain = run_controlled_chain(
            contract_path=args.owned_contract,
            workspace=args.workspace,
            enrollment=enrollment,
            dependency_status=deps,
        )
        controlled_ok = True
        controlled_error = None
    except IntegrationError as exc:
        chain = {"error": str(exc), "code": exc.code}
        controlled_ok = False
        controlled_error = exc.code

    remaining = [
        "Live ClaimPort/EnrollmentPort/ResultPort not production-wired "
        "(demo uses labeled test enrollment only)",
        "Atomic claim-before-dispatch remains supervisor-owned",
        "INDEPENDENT_REVIEW not performed",
        "REAL_LAUNCH_AUTHORIZED remains false",
        "#797 program merge-to-main decision remains owner-owned",
    ]
    report = IntegrationReport(
        components_available=True,
        live_interfaces_connected=True,
        controlled_chain_passed=controlled_ok and external_blocked_preserved,
        remaining_blockers=tuple(remaining),
        evidence={
            "int013_bucket": int_item.bucket.value,
            "int013_external_blocked_preserved": external_blocked_preserved,
            "controlled_chain": chain,
            "controlled_error": controlled_error,
        },
        manifest=ComponentManifest(
            taskcontract_head="b0c35270494890cd9acd067c4a02e70fd0503cf7",
            taskcontract_tree="f195eeb8aecf6af5b5d47ef59bfadb4dc4b51dcf",
            context_tip_head="0a2541b5cc18bd16cbc61ec5c6eba1ffb2cb257d",
            context_tip_tree="9811bd84c20c3bafa8c65737dde24099d1574c5b",
            context_impl_head="94e7b397e9d2400643228f50468be624504e20bd",
            context_impl_tree="cb81c8f072607a1503aedf1be6cd5d2f8cf59077",
            readiness_tip_head="bf98963766f873349ddb46f2fc7dfc4daee3b8f0",
            readiness_tip_tree="81ae18a437190706f6b4738cc8dac19dede2d3a2",
            readiness_impl_head="a6746c2bdabbdb2c58ef60ffced589694433eae6",
            readiness_impl_tree="f6eb52e14a9f452389f6136f9d7d1848055df0d6",
            supervisor_base_head="80280bfe13c77708cada7af17215acdaff3725e4",
            supervisor_base_note="PR #797 program supervisor head (taskcontract base)",
            tested_tips=(
                "taskcontract tip (=impl)",
                "context tip (includes impl+docs pin)",
                "readiness tip (includes impl+docs pins)",
            ),
        ),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report.controlled_chain_passed else 1
