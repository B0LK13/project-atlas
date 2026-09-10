"""Operator surface for AS-ORCH-PROGRAM-SUPERVISOR-001.

Invoked as a module, mirroring ``orchestration.autonomy.cli``'s standalone
parser:

    python -m project_atlas.orchestration.program.cli <command> [options]

Deliberately NOT wired into ``src/project_atlas/cli.py``. That file is under a
structural guard (``tests/unit/test_atlas3_demo_isolation_001.py::
test_cli_mutation_is_additive_only``) that requires every diff to it to add an
Atlas 3 parser hook; a supervisor subcommand is not that, and working around
the guard is not this package's business. ``register_program_parser()`` below
is the whole wiring, so an owner who wants ``atlas program ...`` gets it in one
additive call whenever that grant exists.

Every command prints one JSON object on stdout. Exit codes follow the
repository convention: 0 success, 1 operational error, 2 usage error.

None of these commands merge, grant a gate, or widen a program.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from project_atlas.orchestration.program.loader import (
    LoadedProgram,
    ProgramLoadError,
    load_program,
    profile_digest,
)
from project_atlas.orchestration.program.models import ProgramError
from project_atlas.orchestration.program.profiles import UNENFORCED_MODES
from project_atlas.orchestration.program.store import read_events
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _state_root(args: argparse.Namespace, loaded: LoadedProgram) -> Path:
    explicit = getattr(args, "state_root", None)
    if explicit:
        return Path(explicit).expanduser().resolve()
    return loaded.source_path.parent


def _supervisor(args: argparse.Namespace) -> ProgramSupervisor:
    loaded = load_program(Path(args.program))
    return ProgramSupervisor(loaded, state_root=_state_root(args, loaded))


def run_validate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Validate a program file without running anything.

    Reports the enforcement picture as well as the validity: which permission
    boundaries the runtime will actually apply, and which fields are Atlas's
    own declaration. A program that validates is not thereby a safe one, and
    saying so here is cheaper than discovering it later.
    """
    loaded = load_program(Path(args.program))
    tasks: list[dict[str, Any]] = []
    warnings: list[str] = []
    for task in loaded.program.tasks:
        profile = loaded.effective_profile(task.task_id)
        if profile.permission_mode in UNENFORCED_MODES:
            warnings.append(
                f"task {task.task_id} runs under permission mode "
                f"{profile.permission_mode}, under which the runtime enforces "
                "nothing; only the OS boundary remains"
            )
        if profile.workspace.additional_dirs and not profile.workspace.restricted:
            warnings.append(
                f"profile {profile.profile_id} names additional_dirs without "
                "restricted; those directories are documentation, not a "
                "boundary, and a worker holding Bash can read outside them"
            )
        if task.requires_independent_verification and task.verifier_profile_ref is None:
            warnings.append(
                f"task {task.task_id} requires independent verification but "
                "configures no verifier profile; it will stop at that gate and "
                "wait for a person"
            )
        tasks.append(
            {
                "task_id": task.task_id,
                "title": task.title,
                "depends_on": list(task.depends_on),
                "profile_id": profile.profile_id,
                "agent_id": profile.agent_id,
                "adapter": profile.adapter.value,
                "permission_mode": profile.permission_mode,
                "effective_profile_sha256": profile_digest(profile),
                "acceptance_checks": [check.check_id for check in task.acceptance],
                "owner_gate": task.owner_gate.value if task.owner_gate else None,
                "external_precondition": (
                    task.external_precondition.precondition_id
                    if task.external_precondition
                    else None
                ),
                "requires_independent_verification": (
                    task.requires_independent_verification
                ),
                "verifier_profile_ref": task.verifier_profile_ref,
            }
        )
    return (
        {
            "valid": True,
            "program_id": loaded.program.program_id,
            "program_sha256": loaded.digest,
            "workspace": str(loaded.workspace),
            "base_pin": loaded.program.base_pin,
            "approved_by": loaded.program.approved_by,
            "approval_reference": loaded.program.approval_reference,
            "limits": loaded.program.limits.model_dump(mode="json"),
            "tasks": tasks,
            "warnings": warnings,
            "merge_authorized": False,
            "execution_authorized": False,
        },
        EXIT_OK,
    )


def run_start(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    supervisor = _supervisor(args)
    report = supervisor.start()
    return report.to_public_dict(), EXIT_OK


def run_status(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    supervisor = _supervisor(args)
    return supervisor.status(), EXIT_OK


def run_cancel(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    supervisor = _supervisor(args)
    return supervisor.request_cancel(), EXIT_OK


def run_reconcile(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    supervisor = _supervisor(args)
    return (
        supervisor.reconcile(
            resolve_uncertain=getattr(args, "resolve_uncertain", None)
        ),
        EXIT_OK,
    )


def run_events(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    loaded = load_program(Path(args.program))
    root = _state_root(args, loaded)
    rows = read_events(root, limit=int(getattr(args, "limit", 50) or 50))
    return {"program_id": loaded.program.program_id, "events": rows}, EXIT_OK


_HANDLERS = {
    "validate": run_validate,
    "start": run_start,
    "status": run_status,
    "cancel": run_cancel,
    "reconcile": run_reconcile,
    "events": run_events,
}


def register_program_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    """Attach the ``program`` command to any argparse subparser collection.

    Kept separate from ``_build_parser`` so wiring this into the main ``atlas``
    CLI later is one call plus one dispatch line, with no change to the
    commands themselves.
    """
    parser = subparsers.add_parser(
        "program",
        help="Run an approved work program to completion (read/execute).",
        description=(
            "Execute an approved work program: select eligible tasks, dispatch "
            "one worker at a time through a runtime adapter, check acceptance "
            "locally, checkpoint, and continue. Never merges and never grants "
            "an owner gate."
        ),
    )
    sub = parser.add_subparsers(dest="program_command", required=True)

    for name, help_text in (
        ("validate", "Validate a program file and report its enforcement picture."),
        ("start", "Run the program until a stop reason."),
        ("status", "Compact read-only status. Dispatches nothing."),
        ("cancel", "Ask a running supervisor to stop before its next launch."),
        ("reconcile", "Inspect interrupted attempts; optionally settle one."),
        ("events", "Print the tail of the durable event log."),
    ):
        child = sub.add_parser(name, help=help_text)
        child.add_argument(
            "--program",
            required=True,
            type=Path,
            help="Path to the approved program JSON file.",
        )
        child.add_argument(
            "--state-root",
            type=Path,
            default=None,
            help=(
                "Directory holding program state (default: the program file's "
                "own directory). State never lives inside the workspace."
            ),
        )
        if name == "reconcile":
            child.add_argument(
                "--resolve-uncertain",
                default=None,
                metavar="ATTEMPT_ID",
                help=(
                    "Record an operator judgement that this interrupted "
                    "attempt's effect did not land, and let its task be "
                    "scheduled again. This is your assertion, not the "
                    "supervisor's determination."
                ),
            )
        if name == "events":
            child.add_argument("--limit", type=int, default=50)
    return parser


def dispatch_program(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    handler = _HANDLERS.get(getattr(args, "program_command", ""))
    if handler is None:
        return {"error": "unknown program command"}, EXIT_USAGE
    return handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m project_atlas.orchestration.program.cli",
        description=(
            "AS-ORCH-PROGRAM-SUPERVISOR-001 -- continuous execution of an "
            "approved work program."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    program = register_program_parser(sub)
    _ = program
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload, code = dispatch_program(args)
    except (ProgramLoadError, ProgramError) as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "code": getattr(exc, "code", "PROGRAM_ERROR"),
                    "merge_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_ERROR
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
