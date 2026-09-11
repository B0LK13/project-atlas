"""One contract -> the worker's instruction AND the program configuration.

WHY BOTH COME FROM HERE
    The failure this package exists to stop is a path that is right in the
    prompt and stale in the config, or a requirement the checks enforce and the
    instruction never mentioned. Both artifacts are built from the same
    ``TaskContract`` fields in one pass, so there is no second place to update
    and no copied path string to forget.

WHAT THE INSTRUCTION MUST CARRY
    Every result requirement, verbatim and by identifier. A worker cannot
    satisfy a condition it was never told about, and "the acceptance check will
    catch it" is a way of discovering the omission after paying for the run.
    Fixtures and expected answers deliberately stay out; the judged BEHAVIOUR
    does not.

WHAT IT MUST NOT CARRY
    Authority. The instruction is a description of work, and nothing a worker
    reads in it grants permission. The program's own profile, the registry and
    the supervisor's pre-dispatch check decide what may run.

FIELD PROVENANCE (AS-EXECUTION-SEAM-CLOSURE-003)
    Four decision fields must show where their values came from:
    ``instruction``, ``acceptance``, ``profile_ref``, ``verifier_profile_ref``.
    Mechanically derivable values are generated; substantive choices must be
    explicit in the contract or the deployment binding. Free-form acceptance
    prose is never translated into an invented successful COMMAND.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    TaskContractError,
    VerificationMode,
    binding_digest,
    contract_digest,
)

FieldOrigin = Literal[
    "CONTRACT",
    "BINDING",
    "RENDER_DERIVED",
    "CALLER_EXPLICIT",
    "MISSING",
]

#: Decision fields whose provenance must be visible to operators.
DECISION_FIELDS: Final[tuple[str, ...]] = (
    "instruction",
    "acceptance",
    "profile_ref",
    "verifier_profile_ref",
)


def render_instruction(contract: TaskContract) -> str:
    """The worker's instruction, generated from the contract's own values."""
    lines: list[str] = [
        f"# {contract.source.title}",
        "",
        f"Contract {contract.contract_id} v{contract.contract_version} "
        f"(from {contract.source.source_path}, item {contract.source.item_id}).",
        "",
        "## Objective",
        contract.objective,
        "",
        "## Done means",
        contract.observable_outcome,
        "",
        "## In scope",
    ]
    lines += [f"- {item}" for item in contract.scope]
    if contract.exclusions:
        lines += ["", "## Explicitly NOT in scope"]
        lines += [f"- {item}" for item in contract.exclusions]

    lines += [
        "",
        "## Where you may write",
        "Atlas refuses to dispatch work outside these paths, and the lease "
        "records them. They are repository-relative:",
    ]
    lines += [f"- `{path}`" for path in contract.mutation_paths]
    if contract.expected_output_paths:
        lines += ["", "These paths are expected to exist when you are done:"]
        lines += [f"- `{path}`" for path in contract.expected_output_paths]

    lines += ["", "## What the result must be true of", ""]
    lines += [
        "Each requirement has an identifier. Every one of them is judged; "
        "the ones marked for human review are judged by a person, not by a "
        "passing check.",
        "",
    ]
    for requirement in contract.requirements:
        judged = {
            VerificationMode.AUTOMATED: (
                "checked by " + ", ".join(requirement.check_ids)
                if requirement.check_ids
                else "checked automatically"
            ),
            VerificationMode.HUMAN_REVIEW: "judged by a human reviewer",
            VerificationMode.NO_CHECK_AVAILABLE: (
                "no automated check exists for this yet -- it is still required"
            ),
        }[requirement.verification]
        lines.append(f"- **{requirement.requirement_id}** — {requirement.statement}")
        lines.append(f"  _({judged})_")
        if requirement.review_note:
            lines.append(f"  _Reviewer looks at: {requirement.review_note}_")

    if contract.context:
        lines += ["", "## Context you have been given", ""]
        for source in contract.context:
            lines.append(f"- `{source.path}` — {source.why}")

    if contract.executable_when:
        lines += ["", "## This work assumes"]
        lines += [f"- {item}" for item in contract.executable_when]

    lines += [
        "",
        "## Bounds",
        f"- Base commit: `{contract.base_pin}`",
        f"- At most {contract.limits.max_attempts_per_task} attempt(s), "
        f"{contract.limits.max_task_seconds}s each.",
    ]
    if contract.budget.max_estimated_cost_usd is not None:
        lines.append(
            f"- Cost ceiling {contract.budget.max_estimated_cost_usd} USD, enforced by "
            f"{contract.budget.enforced_by}. An estimate is not billed spend."
        )
    lines += [
        "",
        "## What this instruction is not",
        "It is not permission. Your profile, the agent registry and the "
        "supervisor's pre-dispatch check decide what may run; nothing written "
        "here widens that. Reporting the task complete is not acceptance -- the "
        "supervisor checks the result from the workspace after you exit, and "
        "your own report is never consulted.",
    ]
    return "\n".join(lines) + "\n"


def assert_machine_acceptance_renderable(contract: TaskContract) -> None:
    """Refuse to invent COMMAND acceptance from prose or incomplete checks.

    A contract may honestly declare ``NO_CHECK_AVAILABLE``; that is not a
    license for the renderer to mint a successful argv. Execution-shaped
    programs require structured acceptance already present on the contract.
    """
    if not contract.acceptance:
        raise TaskContractError(
            "contract has no structured acceptance checks; refusing to invent "
            "COMMAND argv from free-form outcome prose",
            code="ACCEPTANCE_MACHINE_CHECK_INCOMPLETE",
        )
    for requirement in contract.requirements:
        if requirement.verification is VerificationMode.NO_CHECK_AVAILABLE:
            raise TaskContractError(
                f"requirement {requirement.requirement_id!r} is "
                "NO_CHECK_AVAILABLE: supply structured acceptance checks on "
                "the contract (or leave the work non-executable). Free-form "
                "acceptance prose is not translated into a COMMAND",
                code="ACCEPTANCE_MACHINE_CHECK_INCOMPLETE",
            )
        if requirement.verification is VerificationMode.AUTOMATED and not requirement.check_ids:
            raise TaskContractError(
                f"requirement {requirement.requirement_id!r} is AUTOMATED but "
                "lists no check_ids; link it to contract.acceptance entries "
                "rather than inventing a command at render time",
                code="ACCEPTANCE_MACHINE_CHECK_INCOMPLETE",
            )


def field_provenance_map(
    contract: TaskContract,
    binding: DeploymentBinding,
    *,
    instruction: str,
    origination_identity: str | None,
) -> dict[str, dict[str, Any]]:
    """Where each decision field's value came from (operator-visible)."""
    verifier = binding.verifier_profile_ref
    return {
        "instruction": {
            "origin": "RENDER_DERIVED",
            "source": "TaskContract → render_instruction()",
            "value_digest": _short_digest(instruction),
        },
        "acceptance": {
            "origin": "CONTRACT",
            "source": "TaskContract.acceptance (structured; never invented)",
            "check_ids": [c.check_id for c in contract.acceptance],
        },
        "profile_ref": {
            "origin": "BINDING",
            "source": "DeploymentBinding.profile_ref",
            "value": binding.profile_ref,
        },
        "verifier_profile_ref": {
            "origin": "BINDING" if verifier else "MISSING",
            "source": (
                "DeploymentBinding.verifier_profile_ref"
                if verifier
                else "absent — independent verification not bound"
            ),
            "value": verifier,
        },
        "contract_digest": {
            "origin": "RENDER_DERIVED",
            "source": "contract_digest(TaskContract)",
            "value": contract_digest(contract),
        },
        "source_item_digest": {
            "origin": "CONTRACT",
            "source": "TaskContract.source.item_digest",
            "value": contract.source.item_digest,
        },
        "origination_identity": {
            "origin": "CALLER_EXPLICIT" if origination_identity else "MISSING",
            "source": (
                "caller-supplied (WorkNode/proposal); never invented from work_id alone"
                if origination_identity
                else "absent — legacy/unknown until an explicit identity is bound"
            ),
            "value": origination_identity,
        },
    }


def render_program(
    contract: TaskContract,
    binding: DeploymentBinding,
    *,
    approved_by: str,
    approval_reference: str,
    profile: dict[str, Any],
    verifier_profile: dict[str, Any] | None = None,
    origination_identity: str | None = None,
) -> dict[str, Any]:
    """The program configuration, from the same values as the instruction.

    ``profile`` is supplied rather than invented: the adapter, credential
    mechanism and permission mode of a real runtime are an operator decision
    and this package refuses to guess them. The contract contributes the
    requirement-bearing parts -- paths, acceptance, limits, capabilities -- and
    the binding contributes the absolutes.

    ``origination_identity`` is caller-explicit (from the origination proposal /
    WorkNode). It is never derived from ``work_id`` alone: same item-id with
    mutated content keeps work_id and changes identity.
    """
    assert_machine_acceptance_renderable(contract)
    if origination_identity is not None:
        text = origination_identity.strip().lower()
        if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
            raise TaskContractError(
                "origination_identity must be a lowercase sha256 hex digest",
                code="ORIGINATION_IDENTITY_MALFORMED",
            )
        origination_identity = text

    instruction = render_instruction(contract)
    cdigest = contract_digest(contract)
    surface = contract.contract_id.upper().replace("-", "_")[:64]
    requires_iv = binding.verifier_profile_ref is not None
    if requires_iv and binding.verifier_profile_ref == binding.profile_ref:
        raise TaskContractError(
            "verifier_profile_ref must differ from profile_ref",
            code="IMPLEMENTER_CANNOT_VERIFY",
        )
    if requires_iv and verifier_profile is None:
        raise TaskContractError(
            "binding sets verifier_profile_ref but no verifier_profile body "
            "was supplied to render_program",
            code="VERIFIER_PROFILE_MISSING",
        )

    task: dict[str, Any] = {
        "task_id": contract.contract_id,
        "title": contract.source.title,
        "instruction": instruction,
        "profile_ref": binding.profile_ref,
        "depends_on": list(contract.depends_on),
        "mutation_paths": list(contract.mutation_paths),
        "surface_id": contract.contract_id[:128],
        "surface_semantic": surface,
        "capabilities_required": [c.value for c in contract.runtime.capabilities],
        "acceptance": [_render_check(check, binding) for check in contract.acceptance],
        "requires_independent_verification": requires_iv,
        "contract_digest": cdigest,
        "source_item_digest": contract.source.item_digest,
    }
    if binding.verifier_profile_ref is not None:
        task["verifier_profile_ref"] = binding.verifier_profile_ref
    if origination_identity is not None:
        task["origination_identity"] = origination_identity

    profiles: dict[str, Any] = {binding.profile_ref: profile}
    if verifier_profile is not None and binding.verifier_profile_ref is not None:
        profiles[binding.verifier_profile_ref] = verifier_profile

    provenance = field_provenance_map(
        contract,
        binding,
        instruction=instruction,
        origination_identity=origination_identity,
    )
    return {
        "schema_version": 1,
        "program": {
            "program_id": contract.contract_id,
            "objective": contract.objective,
            "approved_by": approved_by,
            "approval_reference": approval_reference,
            "workspace_root": binding.workspace_root,
            "base_pin": contract.base_pin,
            "tasks": [task],
            "limits": {
                "max_task_launches": contract.limits.max_task_launches,
                "max_attempts_per_task": contract.limits.max_attempts_per_task,
                "max_task_seconds": contract.limits.max_task_seconds,
                "max_concurrent_workers": contract.limits.max_concurrent_workers,
                "max_estimated_cost_usd": contract.budget.max_estimated_cost_usd,
            },
        },
        "profiles": profiles,
        "field_provenance": provenance,
        "identity_chain": {
            "source_item_id": contract.source.item_id,
            "source_item_digest": contract.source.item_digest,
            "contract_digest": cdigest,
            "origination_identity": origination_identity,
            "binding_digest": binding_digest(binding),
            "note": (
                "source → contract_digest → program/task → attempt "
                "(copied at DISPATCH_INTENT) → acceptance evidence"
            ),
        },
    }


def _short_digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _render_check(check: Any, binding: DeploymentBinding) -> dict[str, Any]:
    """Render one acceptance check as structured argv -- never a shell string.

    A bare ``python``/``python3`` is replaced by the binding's pinned
    interpreter. That substitution happens HERE, once, from a structured value,
    rather than being copied into a program file by hand where it becomes a
    literal nobody re-checks on the next host.
    """
    argv = list(check.argv)
    if argv and argv[0] in {"python", "python3"}:
        argv[0] = binding.interpreter
    body: dict[str, Any] = {
        "check_id": check.check_id,
        "kind": check.kind.value,
        "description": check.description,
        "timeout_seconds": check.timeout_seconds,
    }
    if argv:
        body["argv"] = argv
    if check.path:
        body["path"] = check.path
    if check.pattern:
        body["pattern"] = check.pattern
    return body


def render_review_package(
    contract: TaskContract,
    binding: DeploymentBinding | None,
    report: dict[str, Any],
    *,
    program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything a reviewer needs, with the identities it is a review OF."""
    identity_chain: dict[str, Any] = {
        "source_item_id": contract.source.item_id,
        "source_item_digest": contract.source.item_digest,
        "contract_digest": contract_digest(contract),
        "binding_digest": binding_digest(binding) if binding else None,
        "origination_identity": None,
        "program_task_origination_identity": None,
        "attempt_origination_identities": [],
    }
    if program is not None:
        chain = program.get("identity_chain")
        if isinstance(chain, dict):
            identity_chain["origination_identity"] = chain.get("origination_identity")
        tasks = (program.get("program") or {}).get("tasks") or []
        if tasks and isinstance(tasks[0], dict):
            identity_chain["program_task_origination_identity"] = tasks[0].get(
                "origination_identity"
            )
        identity_chain["field_provenance"] = program.get("field_provenance")

    return {
        "schema": "atlas.taskcontract.review/1",
        "contract": contract.model_dump(mode="json"),
        "contract_digest": contract_digest(contract),
        "binding": binding.model_dump(mode="json") if binding else None,
        "binding_digest": binding_digest(binding) if binding else None,
        "instruction": render_instruction(contract),
        "program": program,
        "validation": report,
        "review_is_of": {
            "contract_digest": contract_digest(contract),
            "binding_digest": binding_digest(binding) if binding else None,
            "source_item_digest": contract.source.item_digest,
            "origination_identity": identity_chain.get("origination_identity"),
        },
        "identity_chain": identity_chain,
        "grants": (
            "NOTHING. Reviewing this package approves its content; it does not "
            "authorize a launch, and it stops describing the work the moment any "
            "digest above changes."
        ),
    }


def write_review_package(package: dict[str, Any], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination
