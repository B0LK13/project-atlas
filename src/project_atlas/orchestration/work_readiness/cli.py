"""CLI for AS-WORK-READINESS-001. Advises only; never claims or dispatches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.orchestration.work_readiness.adapters import ports_from_fixture_bundle
from project_atlas.orchestration.work_readiness.backlog_reader import read_backlog_seeds
from project_atlas.orchestration.work_readiness.capacity import capacity_view
from project_atlas.orchestration.work_readiness.handoff import prepare_handoff, refresh_handoff
from project_atlas.orchestration.work_readiness.models import HandoffProposal
from project_atlas.orchestration.work_readiness.project import project_queue
from project_atlas.orchestration.work_readiness.select import explain_item, select_next

WORK_READINESS_COMMAND = "work-readiness"


def register_work_readiness_parsers(subparsers: argparse._SubParsersAction[Any]) -> None:
    root = subparsers.add_parser(
        WORK_READINESS_COMMAND,
        help=(
            "Derived work-queue readiness + handoff prep "
            "(AS-WORK-READINESS-001; PROJECTION != AUTHORITY)."
        ),
    )
    sub = root.add_subparsers(dest="work_readiness_command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--fixture",
            type=Path,
            required=True,
            help="Versioned fixture bundle (work-readiness-fixture-bundle.v1).",
        )
        p.add_argument(
            "--backlog",
            type=Path,
            default=None,
            help="Optional backlog markdown for seed discovery (read-only, bounded).",
        )
        p.add_argument(
            "--seeds-json",
            type=Path,
            default=None,
            help="Optional explicit seed list JSON ([{task_id, objective, ...}]).",
        )
        p.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout.")

    project_p = sub.add_parser("project", help="Build the derived work-queue projection.")
    _common(project_p)

    select_p = sub.add_parser("select", help="Deterministic next-task selection with explanation.")
    _common(select_p)
    select_p.add_argument("--runtime-profile", default=None)

    explain_p = sub.add_parser("explain", help="Explain why one task is/isn't suitable.")
    _common(explain_p)
    explain_p.add_argument("--task-id", required=True)

    handoff_p = sub.add_parser("handoff", help="Prepare an idempotent handoff proposal.")
    _common(handoff_p)
    handoff_p.add_argument("--task-id", required=True)
    handoff_p.add_argument("--propose-for", required=True, help="Agent id or capability string.")
    handoff_p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write proposal JSON (idempotent; same inputs → same handoff_id).",
    )

    refresh_p = sub.add_parser(
        "refresh", help="Re-validate a prior handoff against a fresh projection."
    )
    _common(refresh_p)
    refresh_p.add_argument("--proposal", type=Path, required=True)

    capacity_p = sub.add_parser(
        "capacity", help="Compact capacity / conflict view (does not raise limits)."
    )
    _common(capacity_p)

    demo_p = sub.add_parser(
        "demo",
        help="Read-only demo: real backlog seeds + fixture positive path (no claims).",
    )
    demo_p.add_argument("--fixture", type=Path, required=True)
    demo_p.add_argument("--backlog", type=Path, required=True)
    demo_p.add_argument("--json", action="store_true")


def _load_report(
    args: argparse.Namespace,
) -> tuple[Any, Any]:
    """Build projection + enrollment from CLI args."""
    contracts, claims, enrollment, results, deps, missing = ports_from_fixture_bundle(
        args.fixture
    )
    seeds: list[dict[str, Any]] = []
    revisions: dict[str, str] = {"fixture": str(args.fixture)}
    backlog_seed_count = 0
    if getattr(args, "seeds_json", None):
        seeds = json.loads(Path(args.seeds_json).read_text(encoding="utf-8"))
        revisions["seeds"] = "explicit-json"
    if getattr(args, "backlog", None):
        backlog_seeds, br = read_backlog_seeds(Path(args.backlog))
        revisions.update(br)
        backlog_seed_count = len(backlog_seeds)
        # Prefer fixture contract task_ids; intersect with backlog when both exist.
        fixture_ids = set(contracts.contracts.keys())
        if fixture_ids:
            matched = [s for s in backlog_seeds if s["task_id"] in fixture_ids]
            extras = [
                {
                    "task_id": tid,
                    "source_ref": f"fixture:{tid}",
                    "source_revision": revisions.get("fixture"),
                    "objective": contracts.contracts[tid].objective,
                    "priority": contracts.contracts[tid].priority,
                }
                for tid in sorted(fixture_ids)
                if tid not in {s["task_id"] for s in matched}
            ]
            seeds = matched + extras
            revisions["backlog_open_checkbox_count"] = str(backlog_seed_count)
            revisions["backlog_fixture_intersection"] = str(len(matched))
        else:
            seeds = backlog_seeds
    if not seeds:
        # Fixture-only: every contract row is a seed.
        seeds = [
            {
                "task_id": tid,
                "source_ref": f"fixture:{tid}",
                "source_revision": "fixture",
                "objective": c.objective,
                "priority": c.priority,
            }
            for tid, c in sorted(contracts.contracts.items())
        ]
    report = project_queue(
        seeds=seeds,
        contracts=contracts,
        claims=claims,
        enrollment=enrollment,
        results=results,
        dependencies=deps,
        fixture_adapters_used=(
            contracts.fixture_id,
            claims.fixture_id,
            enrollment.fixture_id,
            results.fixture_id,
            deps.fixture_id,
        ),
        missing_integrations=missing,
        source_revisions=revisions,
        observed_at="1970-01-01T00:00:00Z",  # deterministic CLI default for hermetic runs
    )
    return report, enrollment


def _human_report(report: Any) -> str:
    lines = [
        f"observed_at={report.observed_at}",
        f"offerable={list(report.offerable)}",
        f"awaiting_authorization={list(report.awaiting_authorization)}",
        f"blocked={list(report.blocked)}",
        f"missing_integrations={list(report.missing_integrations)}",
        f"fixture_adapters_used={list(report.fixture_adapters_used)}",
    ]
    if report.shared_blockers:
        lines.append("shared_blockers:")
        for b in report.shared_blockers:
            lines.append(
                f"  - {b.code.value} object={b.object_ref} impact={b.dependency_impact}"
            )
    if report.empty_queue_reasons:
        lines.append("empty_queue_reasons:")
        for r in report.empty_queue_reasons:
            lines.append(f"  - {r}")
    for item in report.items:
        lines.append(
            f"item {item.task_id} bucket={item.bucket.value} "
            f"contract={item.contract_id}/{item.contract_digest}"
        )
    return "\n".join(lines) + "\n"


def dispatch_work_readiness(args: argparse.Namespace) -> int | None:
    if getattr(args, "command", None) != WORK_READINESS_COMMAND:
        return None
    cmd = args.work_readiness_command

    if cmd == "demo":
        # Phase A: read-only real backlog seeds without inventing contracts.
        backlog_seeds, backlog_revs = read_backlog_seeds(Path(args.backlog))
        from project_atlas.orchestration.work_readiness.adapters import (
            FixtureClaimPort,
            FixtureContractPort,
            FixtureDependencyPort,
            FixtureEnrollmentPort,
            FixtureResultPort,
        )

        backlog_only = project_queue(
            seeds=backlog_seeds[:40],
            contracts=FixtureContractPort(contracts={}),
            claims=FixtureClaimPort(claims=()),
            enrollment=FixtureEnrollmentPort(roster=()),
            results=FixtureResultPort(results={}),
            dependencies=FixtureDependencyPort(nodes={}),
            observed_at="1970-01-01T00:00:00Z",
            fixture_adapters_used=("fixture.empty.v1",),
            missing_integrations=(
                "Live ContractPort unbound — backlog seeds lack task contracts",
            ),
            source_revisions=backlog_revs,
        )
        # Phase B: labeled fixture positive path (FIXTURE != LIVE).
        report, enrollment = _load_report(args)
        selection = select_next(report)
        cap = capacity_view(report, enrollment)
        payload = {
            "backlog_snapshot": {
                "open_checkbox_seeds_sampled": len(backlog_only.items),
                "offerable": list(backlog_only.offerable),
                "empty_queue_reasons": list(backlog_only.empty_queue_reasons),
                "source_revisions": backlog_only.source_revisions,
                "note": (
                    "Under observed main-branch sources, task contracts are not "
                    "bound live; empty offerable queue is valid. Positive path "
                    "below uses explicit FIXTURE adapters only."
                ),
            },
            "fixture_positive_path": {
                "projection": report.model_dump(mode="json"),
                "selection": {
                    "selected_task_id": selection.selected_task_id,
                    "explanation": list(selection.explanation),
                    "empty_reasons": list(selection.empty_reasons),
                },
                "capacity": {
                    "profile_matches": {
                        k: list(v) for k, v in cap.profile_matches.items()
                    },
                    "conflict_pairs": [list(p) for p in cap.conflict_pairs],
                    "flow_limits": list(cap.flow_limits),
                    "conflict_check": cap.conflict_check,
                    "raises_limits": cap.raises_limits,
                },
            },
            "truth_boundaries": {
                "PROJECTION_NE_AUTHORITY": True,
                "FIXTURE_ADAPTER_NE_LIVE_INTEGRATION": True,
                "DEMO_NE_CLAIM": True,
            },
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("=== backlog snapshot (read-only; no live contracts) ===")
            print(
                f"open_checkbox_seeds_sampled={len(backlog_only.items)} "
                f"offerable={list(backlog_only.offerable)}"
            )
            for r in backlog_only.empty_queue_reasons:
                print(f"  reason: {r}")
            print("=== fixture positive path (FIXTURE != LIVE) ===")
            print(_human_report(report))
            print("selection:", selection.selected_task_id)
            for line in selection.explanation:
                print(" ", line)
            if selection.selected_task_id:
                proposal = prepare_handoff(
                    report,
                    selection.selected_task_id,
                    proposed_agent_or_capabilities="demo-operator",
                )
                print("handoff_id:", proposal.handoff_id)
                print("contract_id:", proposal.contract_id)
                print("contract_digest:", proposal.contract_digest)
        return 0

    report, enrollment = _load_report(args)

    if cmd == "project":
        if args.json:
            print(report.model_dump_json_stable(), end="")
        else:
            print(_human_report(report), end="")
        return 0

    if cmd == "select":
        selection = select_next(report, runtime_profile=args.runtime_profile)
        select_payload: dict[str, Any] = {
            "selected_task_id": selection.selected_task_id,
            "bucket": selection.bucket.value if selection.bucket else None,
            "rank_key": list(selection.rank_key) if selection.rank_key else None,
            "explanation": list(selection.explanation),
            "offerable": list(selection.offerable),
            "awaiting_authorization": list(selection.awaiting_authorization),
            "blocked": list(selection.blocked),
            "empty_reasons": list(selection.empty_reasons),
        }
        if args.json:
            print(json.dumps(select_payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(select_payload, indent=2, sort_keys=True))
        return 0

    if cmd == "explain":
        lines = explain_item(report, args.task_id)
        if args.json:
            print(json.dumps({"task_id": args.task_id, "lines": list(lines)}, indent=2))
        else:
            print("\n".join(lines))
        return 0

    if cmd == "handoff":
        proposal = prepare_handoff(
            report,
            args.task_id,
            proposed_agent_or_capabilities=args.propose_for,
        )
        text = json.dumps(proposal.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            # Idempotent write: same content → same bytes
            args.out.write_text(text, encoding="utf-8")
        if args.json or not args.out:
            print(text, end="")
        else:
            print(f"wrote {args.out} handoff_id={proposal.handoff_id}")
        return 0

    if cmd == "refresh":
        previous = HandoffProposal.model_validate_json(
            Path(args.proposal).read_text(encoding="utf-8")
        )
        refreshed = refresh_handoff(previous, report)
        print(json.dumps(refreshed.model_dump(mode="json"), indent=2, sort_keys=True))
        return 1 if refreshed.expired else 0

    if cmd == "capacity":
        cap = capacity_view(report, enrollment)
        capacity_payload: dict[str, Any] = {
            "profile_matches": {k: list(v) for k, v in cap.profile_matches.items()},
            "conflict_pairs": [list(p) for p in cap.conflict_pairs],
            "independent_pairs": [list(p) for p in cap.independent_pairs],
            "flow_limits": list(cap.flow_limits),
            "conflict_check": cap.conflict_check,
            "raises_limits": False,
        }
        print(json.dumps(capacity_payload, indent=2, sort_keys=True))
        return 0

    raise SystemExit(f"unknown work-readiness command: {cmd}")
