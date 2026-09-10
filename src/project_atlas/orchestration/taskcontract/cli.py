"""``atlas task ...`` -- prepare a backlog item into a reviewable contract.

Seven verbs, one per step of the preparation flow, all of which run with zero
model calls:

    sources    what the declared origination sources currently offer
    draft      one item -> a draft contract, with the gaps named
    validate   structural + content + precondition checks; runs nothing
    render     the worker instruction and the program configuration
    review     one export a reviewer can read end to end
    diff       what changed between two contract versions
    verify     does an earlier validation report still describe these inputs

Every command prints one JSON object, the same output contract the ``program``
and ``agent`` commands use, so the three read alike.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.orchestration.taskcontract.diff import diff_contracts
from project_atlas.orchestration.taskcontract.draft import draft_from_item
from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    TaskContractError,
    binding_digest,
    contract_digest,
)
from project_atlas.orchestration.taskcontract.render import (
    render_instruction,
    render_program,
    render_review_package,
    write_review_package,
)
from project_atlas.orchestration.taskcontract.validate import (
    ERROR,
    OK,
    UNKNOWN,
    WARNING,
    report_is_stale,
    validate_contract,
)

EXIT_OK, EXIT_ERROR, EXIT_USAGE = 0, 1, 2
EXIT_BLOCKED = 3


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TaskContractError(f"cannot read {path}: {exc}", code="FILE_UNREADABLE") from exc
    except ValueError as exc:
        raise TaskContractError(f"{path} is not valid JSON: {exc}", code="FILE_MALFORMED") from exc
    if not isinstance(data, dict):
        raise TaskContractError(f"{path} is not a JSON object", code="FILE_MALFORMED")
    return data


def _load_contract(path: Path) -> TaskContract:
    return TaskContract.model_validate(_read_json(path))


def _load_binding(path: Path | None) -> DeploymentBinding | None:
    return None if path is None else DeploymentBinding.model_validate(_read_json(path))


# ------------------------------------------------------------- operator view


def render_operator_view(report: dict[str, Any], contract: TaskContract) -> str:
    """The compact view: purpose, scope, checks, limits, blockers, next action."""
    dims = report["dimensions"]
    counts = report["counts"]
    lines = [
        "=" * 72,
        f"TASK CONTRACT  {contract.contract_id} v{contract.contract_version}"
        f"   {report['verdict']}",
        "=" * 72,
        f"objective   {contract.objective}",
        f"done means  {contract.observable_outcome}",
        f"owner       {contract.owner}",
        f"source      {contract.source.source_path}#{contract.source.item_id}",
        "",
        "scope:",
    ]
    lines += [f"  + {item}" for item in contract.scope]
    lines += [f"  - {item}" for item in contract.exclusions]
    lines += ["", "writes:"]
    lines += [f"  {path}" for path in contract.mutation_paths]

    lines += ["", "requirements and what judges them:"]
    for requirement in contract.requirements:
        judged = ", ".join(requirement.check_ids) or "-"
        lines.append(
            f"  {requirement.requirement_id:<24} {requirement.verification.value:<20} {judged}"
        )

    lines += [
        "",
        f"limits      {contract.limits.max_attempts_per_task} attempt(s), "
        f"{contract.limits.max_task_seconds}s, "
        f"{contract.limits.max_concurrent_workers} worker(s)",
        f"budget      {contract.budget.max_estimated_cost_usd or 'none'} "
        f"(enforced by {contract.budget.enforced_by})",
        "",
        "dimensions:",
    ]
    for name, value in dims.items():
        lines.append(f"  {name:<26} {value}")
    lines += [
        "",
        f"{counts[ERROR]} error(s)  {counts[WARNING]} warning(s)  "
        f"{counts[UNKNOWN]} unknown  {counts[OK]} ok",
    ]

    for severity in (ERROR, WARNING, UNKNOWN):
        rows = [f for f in report["findings"] if f["severity"] == severity]
        if not rows:
            continue
        lines += ["", f"--- {severity} ---"]
        lines += [f"  [{row['check']}] {row['message']}" for row in rows]

    lines += ["", "next action:", f"  {_next_action(report)}"]
    lines += [
        "",
        "A valid contract is not execution authority and proves nothing about "
        "the result.",
    ]
    return "\n".join(lines)


def _next_action(report: dict[str, Any]) -> str:
    dims = report["dimensions"]
    if dims["content_complete"] == "FAIL":
        return "Fix the content errors above; the contract does not yet say what it must."
    if dims["preconditions_checked"] == "FAIL":
        return "Fix the deployment or dependency errors above, then re-validate."
    if dims["preconditions_checked"] == "UNKNOWN":
        return (
            "Re-run with --binding and --project so the preconditions can be "
            "checked rather than reported as unknown."
        )
    if dims["execution_authorization"] != "DEMONSTRATED":
        return (
            "Contract content is ready. Execution authorization is not "
            "demonstrated: assign an ACTIVE agent to the rendered program."
        )
    return "Ready for review. Review approves content; launching stays a separate act."


# ---------------------------------------------------------------- handlers


def _cmd_sources(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from project_atlas.orchestration.origination.sources import eligible_work_items

    items = eligible_work_items(Path(args.project))
    return {
        "project_root": str(args.project),
        "item_count": len(items),
        "items": [
            {
                "item_id": item.item_id,
                "title": item.title,
                "source_path": item.source_path,
                "status": item.status,
                "lifecycle": item.lifecycle,
                "depends_on": list(item.depends_on),
                "blockers": list(item.blockers),
                "item_digest": item.item_digest,
                "has_acceptance_contract": item.contract_proposed_scope is not None,
            }
            for item in items
        ],
        "grants": "NOTHING. Listing eligible work is not selecting or approving it.",
    }, EXIT_OK


def _cmd_draft(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from project_atlas.orchestration.origination.sources import eligible_work_items

    items = {item.item_id: item for item in eligible_work_items(Path(args.project))}
    item = items.get(args.item)
    if item is None:
        return {
            "error": f"no eligible item {args.item!r} in any declared origination source",
            "code": "ITEM_NOT_ELIGIBLE",
            "known": sorted(items),
        }, EXIT_ERROR

    supplied = _read_json(Path(args.supplied)) if args.supplied else None
    result = draft_from_item(
        item,
        supplied=supplied,
        contract_id=args.contract_id,
        source_revision=args.source_revision,
    )
    payload = result.as_dict()
    if result.contract is not None:
        payload["contract_digest"] = contract_digest(result.contract)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(
                json.dumps(result.contract.model_dump(mode="json"), indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            payload["written"] = str(args.out)
    return payload, EXIT_OK if result.complete else EXIT_ERROR


def _cmd_validate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    contract = _load_contract(Path(args.contract))
    binding = _load_binding(Path(args.binding) if args.binding else None)
    report = validate_contract(
        contract,
        binding=binding,
        project_root=Path(args.project) if args.project else None,
        program_path=Path(args.program) if args.program else None,
    )
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report["written"] = str(args.json_out)
    if not args.json:
        print(render_operator_view(report, contract))
        return {}, EXIT_BLOCKED if report["counts"][ERROR] else EXIT_OK
    return report, EXIT_BLOCKED if report["counts"][ERROR] else EXIT_OK


def _cmd_render(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    contract = _load_contract(Path(args.contract))
    binding = _load_binding(Path(args.binding))
    assert binding is not None
    profile = _read_json(Path(args.profile))
    verifier_profile = (
        _read_json(Path(args.verifier_profile)) if args.verifier_profile else None
    )
    instruction = render_instruction(contract)
    try:
        program = render_program(
            contract,
            binding,
            approved_by=args.approved_by,
            approval_reference=args.approval_reference,
            profile=profile,
            verifier_profile=verifier_profile,
            origination_identity=args.origination_identity,
        )
    except TaskContractError as exc:
        return {
            "ok": False,
            "code": getattr(exc, "code", "RENDER_REFUSED"),
            "error": str(exc),
            "grants": "NOTHING",
        }, EXIT_ERROR
    written: dict[str, str] = {}
    if args.out_program:
        Path(args.out_program).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_program).write_text(
            json.dumps(program, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written["program"] = str(args.out_program)
    if args.out_instruction:
        Path(args.out_instruction).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_instruction).write_text(instruction, encoding="utf-8")
        written["instruction"] = str(args.out_instruction)
    return {
        "contract_id": contract.contract_id,
        "contract_digest": contract_digest(contract),
        "binding_digest": binding_digest(binding),
        "instruction": instruction,
        "program": program,
        "field_provenance": program.get("field_provenance"),
        "identity_chain": program.get("identity_chain"),
        "written": written,
        "grants": (
            "NOTHING. A rendered program is a proposal; the supervisor validates "
            "it and re-checks authority before any dispatch."
        ),
    }, EXIT_OK


def _cmd_review(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    contract = _load_contract(Path(args.contract))
    binding = _load_binding(Path(args.binding) if args.binding else None)
    program = _read_json(Path(args.program_file)) if args.program_file else None
    report = validate_contract(
        contract,
        binding=binding,
        project_root=Path(args.project) if args.project else None,
        program_path=Path(args.program) if args.program else None,
    )
    package = render_review_package(contract, binding, report, program=program)
    if args.out:
        write_review_package(package, Path(args.out))
        package["written"] = str(args.out)
    return package, EXIT_BLOCKED if report["counts"][ERROR] else EXIT_OK


def _cmd_diff(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return diff_contracts(
        _load_contract(Path(args.before)),
        _load_contract(Path(args.after)),
        binding_before=_load_binding(Path(args.binding_before) if args.binding_before else None),
        binding_after=_load_binding(Path(args.binding_after) if args.binding_after else None),
    ), EXIT_OK


def _cmd_verify(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    contract = _load_contract(Path(args.contract))
    binding = _load_binding(Path(args.binding) if args.binding else None)
    report = _read_json(Path(args.report))
    stale, reasons = report_is_stale(report, contract=contract, binding=binding)
    return {
        "report_contract_id": report.get("contract_id"),
        "stale": stale,
        "reasons": reasons,
        "current": {
            "contract_digest": contract_digest(contract),
            "binding_digest": binding_digest(binding) if binding else None,
        },
        "verdict_of_stale_report_is_not_current": stale,
        "grants": (
            "NOTHING. A fresh report is not approval; a stale one is not evidence."
        ),
    }, EXIT_ERROR if stale else EXIT_OK


_HANDLERS = {
    "sources": _cmd_sources,
    "draft": _cmd_draft,
    "validate": _cmd_validate,
    "render": _cmd_render,
    "review": _cmd_review,
    "diff": _cmd_diff,
    "verify": _cmd_verify,
}


def register_task_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    """Attach ``task`` to any argparse subparser collection."""
    parser = subparsers.add_parser(
        "task",
        help="Turn a backlog item into a reviewable task contract (read-only).",
        description=(
            "Prepare a declared backlog item into one versionable contract, and "
            "render the worker instruction, program configuration and review "
            "package from it. Runs no model calls and executes no acceptance "
            "command. A valid contract grants no execution authority."
        ),
    )
    sub = parser.add_subparsers(dest="task_command", required=True)

    p = sub.add_parser("sources", help="List eligible items from declared sources.")
    p.add_argument("--project", required=True, type=Path)

    p = sub.add_parser("draft", help="Draft a contract from one backlog item.")
    p.add_argument("--project", required=True, type=Path)
    p.add_argument("--item", required=True, help="item_id from `task sources`.")
    p.add_argument("--supplied", type=Path, default=None,
                   help="JSON with the decisions no source can make.")
    p.add_argument("--contract-id", default=None)
    p.add_argument("--source-revision", default=None)
    p.add_argument("--out", type=Path, default=None)

    p = sub.add_parser("validate", help="Check a contract. Executes nothing.")
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--binding", type=Path, default=None)
    p.add_argument("--project", type=Path, default=None)
    p.add_argument("--program", type=Path, default=None,
                   help="Rendered program path, for the registry assignment check.")
    p.add_argument("--json-out", type=Path, default=None)
    p.add_argument("--json", action="store_true", help="Machine-readable only.")

    p = sub.add_parser("render", help="Generate the instruction and program config.")
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--binding", required=True, type=Path)
    p.add_argument("--profile", required=True, type=Path,
                   help="The runtime profile. Never invented by this tool.")
    p.add_argument(
        "--verifier-profile",
        type=Path,
        default=None,
        help="Verifier profile body when binding.verifier_profile_ref is set.",
    )
    p.add_argument(
        "--origination-identity",
        default=None,
        help=(
            "Explicit sha256 origination identity from the proposal/WorkNode. "
            "Never derived from work_id alone."
        ),
    )
    p.add_argument("--approved-by", required=True)
    p.add_argument("--approval-reference", required=True)
    p.add_argument("--out-program", type=Path, default=None)
    p.add_argument("--out-instruction", type=Path, default=None)

    p = sub.add_parser("review", help="Export one review package.")
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--binding", type=Path, default=None)
    p.add_argument("--project", type=Path, default=None)
    p.add_argument("--program", type=Path, default=None)
    p.add_argument("--program-file", type=Path, default=None,
                   help="A rendered program to embed in the package.")
    p.add_argument("--out", type=Path, default=None)

    p = sub.add_parser("diff", help="What changed between two contract versions.")
    p.add_argument("--before", required=True, type=Path)
    p.add_argument("--after", required=True, type=Path)
    p.add_argument("--binding-before", type=Path, default=None)
    p.add_argument("--binding-after", type=Path, default=None)

    p = sub.add_parser("verify", help="Is an earlier validation report still current?")
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--binding", type=Path, default=None)

    return parser


def dispatch_task(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    handler = _HANDLERS.get(getattr(args, "task_command", ""))
    if handler is None:
        return {"error": "unknown task command"}, EXIT_USAGE
    try:
        return handler(args)
    except TaskContractError as exc:
        return {"error": str(exc), "code": exc.code, "merge_authorized": False}, EXIT_ERROR
    except ValueError as exc:
        return {"error": str(exc), "code": "CONTRACT_INVALID",
                "merge_authorized": False}, EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas-task")
    register_task_parser(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    payload, exit_code = dispatch_task(args)
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
