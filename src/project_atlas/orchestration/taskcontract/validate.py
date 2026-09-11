"""Contract validation. Reads; never runs anything the contract supplies.

SEVERITY IS NOT DECORATION -- the same three words the program preflight uses,
with the same meanings, so an operator reading both reports reads one language:

    ERROR    objectively wrong now, and checkable without running anything.
    WARNING  suspicious, or true-but-recoverable; a human should look.
    UNKNOWN  not checkable from here. Said out loud instead of assumed away.

WHAT THIS NEVER DOES
    It never executes an acceptance ``argv``. Not to see whether it works, not
    to resolve a path, not once. A contract is drafted from backlog text, and
    backlog text is written by whoever can edit the backlog; running a command
    it names would make "can edit docs/backlog.md" equal to "can execute code
    on this host". ``shutil.which`` resolves a name without running it, and
    that is the whole of what this module does with argv.

FIVE DIMENSIONS, KEPT APART
    A contract can be structurally valid, content-complete, and still not
    launchable. Collapsing these into one "ready" boolean is how a green report
    becomes an authorization nobody granted.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from project_atlas.orchestration.program.models import AcceptanceKind
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.taskcontract.models import (
    PRESENCE_ONLY_KINDS,
    DeploymentBinding,
    TaskContract,
    VerificationMode,
    binding_digest,
    contract_digest,
    find_placeholders,
)

ERROR, WARNING, UNKNOWN, OK = "ERROR", "WARNING", "UNKNOWN", "OK"


class Dimension(StrEnum):
    STRUCTURALLY_VALID = "structurally_valid"
    CONTENT_COMPLETE = "content_complete"
    PRECONDITIONS_CHECKED = "preconditions_checked"
    EXECUTION_AUTHORIZATION = "execution_authorization"
    ACCEPTANCE_OUTCOME = "acceptance_outcome"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------- content completeness


def check_placeholders(contract: TaskContract) -> list[Finding]:
    """Template markers left in fields that drive execution.

    Prose fields are checked too, but an unresolved marker inside an acceptance
    argv or a mutation path is the one that silently becomes a literal.
    """
    out: list[Finding] = []
    fields: list[tuple[str, str]] = [
        ("objective", contract.objective),
        ("observable_outcome", contract.observable_outcome),
        *[(f"scope[{i}]", s) for i, s in enumerate(contract.scope)],
        *[(f"mutation_paths[{i}]", p) for i, p in enumerate(contract.mutation_paths)],
        *[
            (f"expected_output_paths[{i}]", p)
            for i, p in enumerate(contract.expected_output_paths)
        ],
        *[
            (f"requirements[{r.requirement_id}].statement", r.statement)
            for r in contract.requirements
        ],
    ]
    for check in contract.acceptance:
        fields.extend(
            (f"acceptance[{check.check_id}].argv[{i}]", token)
            for i, token in enumerate(check.argv)
        )
        if check.path:
            fields.append((f"acceptance[{check.check_id}].path", check.path))
        if check.pattern:
            fields.append((f"acceptance[{check.check_id}].pattern", check.pattern))

    for name, text in fields:
        markers = find_placeholders(text)
        if markers:
            out.append(
                Finding(
                    "content.placeholder",
                    ERROR,
                    f"{name} still contains template markers: {', '.join(markers)}",
                    {"field": name, "markers": list(markers)},
                )
            )
    return out


def check_requirement_coverage(contract: TaskContract) -> list[Finding]:
    """Every requirement judged, every check attached to something.

    The two directions are separate defects. A requirement with no check is
    work nobody will notice is missing; a check with no requirement is a
    condition nobody decided mattered, and it will be argued away the first
    time it fails.
    """
    out: list[Finding] = []
    check_kinds = {c.check_id: c.kind for c in contract.acceptance}
    referenced: set[str] = set()

    for requirement in contract.requirements:
        referenced.update(requirement.check_ids)
        unknown = [cid for cid in requirement.check_ids if cid not in check_kinds]
        if unknown:
            out.append(
                Finding(
                    "content.check_unknown_ref",
                    ERROR,
                    f"requirement {requirement.requirement_id} references check(s) "
                    f"this contract does not define: {', '.join(sorted(unknown))}",
                    {"requirement_id": requirement.requirement_id,
                     "unknown": sorted(unknown)},
                )
            )
            continue

        if requirement.verification is VerificationMode.AUTOMATED:
            if not requirement.check_ids:
                out.append(
                    Finding(
                        "content.requirement_unchecked",
                        ERROR,
                        f"requirement {requirement.requirement_id} claims AUTOMATED "
                        "verification but names no check",
                        {"requirement_id": requirement.requirement_id},
                    )
                )
                continue
            kinds = {check_kinds[cid] for cid in requirement.check_ids}
            if kinds <= PRESENCE_ONLY_KINDS:
                out.append(
                    Finding(
                        "content.requirement_presence_only",
                        ERROR,
                        f"requirement {requirement.requirement_id} is judged only by "
                        f"{'/'.join(sorted(k.value for k in kinds))}, which observes "
                        "that something exists or changed, never what it does. A "
                        "worker that writes an empty file passes it. Presence is "
                        "supporting evidence; it is not the whole check.",
                        {
                            "requirement_id": requirement.requirement_id,
                            "kinds": sorted(k.value for k in kinds),
                        },
                    )
                )
        elif requirement.verification is VerificationMode.HUMAN_REVIEW:
            out.append(
                Finding(
                    "content.requirement_human_review",
                    WARNING,
                    f"requirement {requirement.requirement_id} needs human review; no "
                    "check can close it and acceptance passing does not either",
                    {"requirement_id": requirement.requirement_id,
                     "review_note": requirement.review_note},
                )
            )
        else:
            out.append(
                Finding(
                    "content.requirement_no_check_available",
                    UNKNOWN,
                    f"requirement {requirement.requirement_id} has no suitable check "
                    "yet; it is recorded as unverified rather than covered by a "
                    "weaker one",
                    {"requirement_id": requirement.requirement_id},
                )
            )

    for check in contract.acceptance:
        if check.check_id not in referenced:
            out.append(
                Finding(
                    "content.check_orphan",
                    ERROR,
                    f"acceptance check {check.check_id} is linked to no result "
                    "requirement, so nothing says why it must pass",
                    {"check_id": check.check_id},
                )
            )
    return out


def check_paths_repeated_in_prose(contract: TaskContract) -> list[Finding]:
    """A path written out again in prose is a second copy that will drift.

    Heuristic, so it is a WARNING and never more: prose legitimately names a
    file sometimes, and text matching cannot tell "the loop in src/x.py" from a
    hand-maintained duplicate of the mutation path. It is reported because the
    duplicate is invisible until the structured field moves and the sentence
    does not -- which is exactly the failure this package exists to prevent.
    """
    prose: list[tuple[str, str]] = [
        ("objective", contract.objective),
        ("observable_outcome", contract.observable_outcome),
        *[(f"scope[{i}]", s) for i, s in enumerate(contract.scope)],
        *[(f"exclusions[{i}]", s) for i, s in enumerate(contract.exclusions)],
        # Requirement prose reaches the worker verbatim, so a path written
        # there is as much a second copy as one in the objective.
        *[
            (f"requirements[{r.requirement_id}].statement", r.statement)
            for r in contract.requirements
        ],
        *[
            (f"requirements[{r.requirement_id}].review_note", r.review_note)
            for r in contract.requirements
            if r.review_note
        ],
    ]
    out: list[Finding] = []
    for path in (*contract.mutation_paths, *contract.expected_output_paths):
        for name, text in prose:
            # A field whose whole value IS the path is a structured statement,
            # not a sentence that quotes one. This project's own acceptance
            # contracts write scope as a bare path list, and warning about
            # those would be noise that trains an operator to skip the section.
            if text.strip() == path:
                continue
            if path in text:
                out.append(
                    Finding(
                        "content.path_repeated_in_prose",
                        WARNING,
                        f"{name} writes out the path {path!r} that a structured "
                        "field already carries; if the structured field moves, this "
                        "sentence will not move with it",
                        {"field": name, "path": path},
                    )
                )
    return out


def check_budget_and_limits(contract: TaskContract) -> list[Finding]:
    out: list[Finding] = []
    if contract.budget.max_estimated_cost_usd is None:
        out.append(
            Finding(
                "content.budget_unbounded",
                WARNING,
                "no per-launch cost ceiling is set; "
                f"enforcement recorded as {contract.budget.enforced_by!r}",
                {"enforced_by": contract.budget.enforced_by},
            )
        )
    if contract.budget.not_enforced:
        out.append(
            Finding(
                "content.budget_not_enforced",
                UNKNOWN,
                "the contract records limits it cannot enforce: "
                + "; ".join(contract.budget.not_enforced),
                {"not_enforced": list(contract.budget.not_enforced)},
            )
        )
    if contract.limits.max_task_seconds > contract.limits.max_task_launches * 86_400:
        out.append(
            Finding("content.limits_incoherent", WARNING, "limits are mutually implausible")
        )
    return out


# ------------------------------------------------------------------- paths


def _under(candidate: str, prefixes: tuple[str, ...]) -> bool:
    cand = PurePosixParts(candidate)
    return any(cand.under(PurePosixParts(prefix)) for prefix in prefixes)


class PurePosixParts:
    """Path-prefix comparison on segments, so ``src/a`` never matches ``src/ab``."""

    def __init__(self, value: str) -> None:
        self.parts = tuple(p for p in value.strip("/").split("/") if p not in ("", "."))

    def under(self, prefix: PurePosixParts) -> bool:
        if not prefix.parts:  # "" means the whole workspace
            return True
        return self.parts[: len(prefix.parts)] == prefix.parts


def check_paths(contract: TaskContract) -> list[Finding]:
    """Outputs must land where the task is allowed to write.

    A declared output that does not exist yet is deliberately NOT a finding:
    before the first run, its absence is the normal state, and reporting it
    would train an operator to ignore this section.
    """
    out: list[Finding] = []
    mutation = contract.mutation_paths

    for path in contract.expected_output_paths:
        if not _under(path, mutation):
            out.append(
                Finding(
                    "paths.output_outside_mutation",
                    ERROR,
                    f"expected output {path!r} is not under any mutation path; the "
                    "supervisor would refuse to dispatch work that must write it",
                    {"path": path, "mutation_paths": list(mutation)},
                )
            )

    for path in contract.evidence.evidence_paths:
        if not _under(path, mutation):
            out.append(
                Finding(
                    "paths.evidence_outside_mutation",
                    WARNING,
                    f"evidence path {path!r} lies outside the mutation paths; it must "
                    "be written by something other than this worker",
                    {"path": path},
                )
            )

    seen: dict[str, int] = {}
    for path in mutation:
        seen[path] = seen.get(path, 0) + 1
    duplicates = sorted(p for p, n in seen.items() if n > 1)
    if duplicates:
        out.append(
            Finding(
                "paths.mutation_duplicate",
                WARNING,
                f"mutation paths repeat: {', '.join(duplicates)}",
                {"duplicates": duplicates},
            )
        )
    for outer in mutation:
        for inner in mutation:
            if outer != inner and _under(inner, (outer,)):
                out.append(
                    Finding(
                        "paths.mutation_nested",
                        WARNING,
                        f"mutation path {inner!r} is already covered by {outer!r}",
                        {"outer": outer, "inner": inner},
                    )
                )
    return out


# ----------------------------------------------------------------- runtime


def check_runtime(contract: TaskContract) -> list[Finding]:
    out: list[Finding] = []
    if contract.runtime.adapter not in set(AdapterKind):
        out.append(
            Finding(
                "runtime.adapter_unsupported",
                ERROR,
                f"no adapter is written for {contract.runtime.adapter!r}",
                {"adapter": str(contract.runtime.adapter)},
            )
        )
    if contract.runtime.adapter_min_version is None:
        out.append(
            Finding(
                "runtime.version_unpinned",
                UNKNOWN,
                "no minimum runtime version is required, so the version the worker "
                "will actually run is not constrained by this contract",
            )
        )
    for constraint in contract.runtime.constraints:
        out.append(
            Finding(
                "runtime.constraint_unverified",
                UNKNOWN,
                f"constraint {constraint!r} is recorded but not checkable from here",
                {"constraint": constraint},
            )
        )
    return out


# ------------------------------------------------- acceptance executables


def check_acceptance_executables(
    contract: TaskContract, binding: DeploymentBinding | None
) -> list[Finding]:
    """What is locally demonstrable about each COMMAND's executable.

    Resolving a bare name here says something about THIS host's PATH and
    nothing about the worker's. That distinction is the whole point of the
    WARNING: a bare executable is not automatically available in the future
    worker environment, and a contract that pins an absolute interpreter is
    the only version of this check that can be an OK.
    """
    out: list[Finding] = []
    for check in contract.acceptance:
        if check.kind is not AcceptanceKind.COMMAND:
            continue
        if not check.argv:
            out.append(
                Finding(
                    "acceptance.argv_empty",
                    ERROR,
                    f"check {check.check_id} is a COMMAND with no argv",
                    {"check_id": check.check_id},
                )
            )
            continue
        executable = check.argv[0]
        if os.path.isabs(executable):
            if Path(executable).is_file() and os.access(executable, os.X_OK):
                out.append(
                    Finding(
                        "acceptance.executable",
                        OK,
                        f"check {check.check_id} names an absolute executable that "
                        "exists here",
                        {"check_id": check.check_id, "executable": executable},
                    )
                )
            else:
                out.append(
                    Finding(
                        "acceptance.executable_missing",
                        ERROR,
                        f"check {check.check_id} names {executable!r}, which is not "
                        "an executable file on this host",
                        {"check_id": check.check_id, "executable": executable},
                    )
                )
            continue

        resolved = shutil.which(executable)
        if resolved is None:
            out.append(
                Finding(
                    "acceptance.executable_unresolvable",
                    ERROR,
                    f"check {check.check_id} names {executable!r}, which resolves to "
                    "nothing on this host's PATH",
                    {"check_id": check.check_id, "executable": executable},
                )
            )
        else:
            hint = ""
            if binding is not None and executable in {"python", "python3"}:
                hint = f" The binding pins {binding.interpreter!r}; use it."
            out.append(
                Finding(
                    "acceptance.executable_bare",
                    WARNING,
                    f"check {check.check_id} names the bare executable {executable!r}. "
                    f"It resolves here (to {resolved}), which says nothing about the "
                    f"worker's environment.{hint}",
                    {"check_id": check.check_id, "executable": executable,
                     "resolved_here": resolved},
                )
            )
    return out


# ------------------------------------------------------- deployment binding


def check_binding(
    contract: TaskContract, binding: DeploymentBinding | None
) -> list[Finding]:
    if binding is None:
        return [
            Finding(
                "binding.absent",
                UNKNOWN,
                "no deployment binding given; workspace, state, registry and "
                "interpreter cannot be checked",
            )
        ]
    out: list[Finding] = []
    workspace = Path(binding.workspace_root)
    state = Path(binding.state_root)
    registry = Path(binding.registry_root)

    if not workspace.is_dir():
        out.append(
            Finding("binding.workspace_missing", ERROR,
                    f"workspace_root does not exist: {workspace}",
                    {"workspace_root": str(workspace)}))
    elif not (workspace / ".git").exists():
        out.append(
            Finding("binding.workspace_not_git", ERROR,
                    f"workspace_root is not a git checkout: {workspace}",
                    {"workspace_root": str(workspace)}))

    try:
        inside = state.resolve().is_relative_to(workspace.resolve())
    except OSError:
        inside = False
    if inside:
        out.append(
            Finding("binding.state_inside_workspace", ERROR,
                    "state_root lies inside the workspace; program state the worker "
                    "can edit is not state",
                    {"state_root": str(state), "workspace_root": str(workspace)}))

    if not registry.is_dir():
        out.append(
            Finding("binding.registry_missing", ERROR,
                    f"registry_root does not exist: {registry}",
                    {"registry_root": str(registry)}))

    interpreter = Path(binding.interpreter)
    if not (interpreter.is_file() and os.access(interpreter, os.X_OK)):
        out.append(
            Finding("binding.interpreter_missing", ERROR,
                    f"the binding's interpreter is not executable: {interpreter}",
                    {"interpreter": str(interpreter)}))

    if workspace.is_dir():
        head = _rev_parse(workspace, contract.base_pin)
        if head is None:
            out.append(
                Finding("binding.base_pin_absent", WARNING,
                        f"base_pin {contract.base_pin} is not an object in this "
                        "workspace; the worker would start from something else",
                        {"base_pin": contract.base_pin}))

    for source in contract.context:
        if workspace.is_dir() and not (workspace / source.path).exists():
            out.append(
                Finding("binding.context_missing", ERROR,
                        f"context source {source.path!r} does not exist in the "
                        "workspace, so the worker cannot be given it",
                        {"source_id": source.source_id, "path": source.path}))
    return out


def _rev_parse(workspace: Path, rev: str) -> str | None:
    """Resolve a revision without a subprocess: read the object database.

    Deliberately not ``git rev-parse``: this module runs on contract content,
    and shelling out on a value the contract supplies is exactly the habit this
    package exists to avoid. A loose object or a packed ref is enough to answer
    "does this commit exist here".
    """
    git_dir = workspace / ".git"
    if git_dir.is_file():  # worktree: .git is a pointer file
        try:
            text = git_dir.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir:"):
            git_dir = Path(text.split(":", 1)[1].strip())
            common = git_dir / "commondir"
            if common.is_file():
                try:
                    git_dir = (git_dir / common.read_text(encoding="utf-8").strip()).resolve()
                except OSError:
                    return None
    loose = git_dir / "objects" / rev[:2] / rev[2:]
    if loose.is_file():
        return rev
    packs = git_dir / "objects" / "pack"
    if packs.is_dir():
        for idx in packs.glob("*.idx"):
            if _in_pack_index(idx, rev):
                return rev
    return None


def _in_pack_index(idx_path: Path, rev: str) -> bool:
    """Membership test against a v2 pack index. Read-only, no subprocess."""
    try:
        data = idx_path.read_bytes()
    except OSError:
        return False
    if len(data) < 8 + 256 * 4 or data[:4] != b"\xfftOc":
        return False
    want = bytes.fromhex(rev)
    total = int.from_bytes(data[8 + 255 * 4 : 8 + 256 * 4], "big")
    start = 8 + 256 * 4
    lo, hi = 0, total
    while lo < hi:
        mid = (lo + hi) // 2
        offset = start + mid * 20
        current = data[offset : offset + 20]
        if current == want:
            return True
        if current < want:
            lo = mid + 1
        else:
            hi = mid
    return False


# ------------------------------------------------------------ dependencies


def check_dependencies(
    contract: TaskContract, project_root: Path | None
) -> list[Finding]:
    """Do the named dependencies exist, and does the task depend on itself?

    Resolution goes through the declared origination sources, so a dependency
    only "exists" if it is a real item in a source the project declared -- not
    because a string looks like an id.
    """
    out: list[Finding] = []
    if contract.source.item_id in contract.depends_on:
        out.append(
            Finding(
                "dependencies.self_reference",
                ERROR,
                f"{contract.source.item_id} depends on itself; it can never become "
                "eligible",
                {"item_id": contract.source.item_id},
            )
        )
    if not contract.depends_on:
        return out
    if project_root is None:
        out.append(
            Finding(
                "dependencies.unresolved",
                UNKNOWN,
                "no project root given; "
                f"{len(contract.depends_on)} dependency reference(s) not resolved",
                {"depends_on": list(contract.depends_on)},
            )
        )
        return out

    from project_atlas.orchestration.origination.sources import eligible_work_items

    try:
        known = {item.item_id for item in eligible_work_items(project_root)}
    except (OSError, ValueError) as exc:
        return [
            *out,
            Finding(
                "dependencies.sources_unreadable",
                UNKNOWN,
                f"the declared origination sources could not be read: {exc}",
            ),
        ]
    missing = [dep for dep in contract.depends_on if dep not in known]
    if missing:
        out.append(
            Finding(
                "dependencies.missing",
                ERROR,
                "dependency not found in any declared origination source: "
                + ", ".join(sorted(missing)),
                {"missing": sorted(missing)},
            )
        )
    return out


# --------------------------------------------------------------- freshness


def check_freshness(contract: TaskContract, project_root: Path | None) -> list[Finding]:
    """Has the backlog item moved under the contract that quotes it?"""
    if project_root is None:
        return [
            Finding(
                "freshness.source_unchecked",
                UNKNOWN,
                "no project root given; the source item's current digest was not "
                "compared against the one this contract pins",
                {"pinned_digest": contract.source.item_digest},
            )
        ]
    from project_atlas.orchestration.origination.sources import eligible_work_items

    try:
        items = {item.item_id: item for item in eligible_work_items(project_root)}
    except (OSError, ValueError) as exc:
        return [
            Finding("freshness.sources_unreadable", UNKNOWN,
                    f"the declared origination sources could not be read: {exc}")
        ]
    current = items.get(contract.source.item_id)
    if current is None:
        return [
            Finding(
                "freshness.source_item_gone",
                ERROR,
                f"item {contract.source.item_id} is no longer an eligible item in any "
                "declared source; the contract quotes work the backlog no longer has",
                {"item_id": contract.source.item_id},
            )
        ]
    if current.item_digest != contract.source.item_digest:
        return [
            Finding(
                "freshness.source_changed",
                ERROR,
                f"the backlog item {contract.source.item_id} has changed since this "
                "contract was drafted; every review of it is about older text",
                {
                    "pinned_digest": contract.source.item_digest,
                    "current_digest": current.item_digest,
                },
            )
        ]
    return [
        Finding("freshness.source", OK,
                f"item {contract.source.item_id} is unchanged since drafting")
    ]


# ----------------------------------------------------------- authorization


def check_authorization(
    contract: TaskContract,
    binding: DeploymentBinding | None,
    program_path: Path | None,
) -> tuple[str, list[Finding]]:
    """Is execution authorization DEMONSTRABLE? Never read from the contract.

    The contract's ``authorization_references`` are pointers. This resolves the
    one kind that has a machine-checkable answer -- a registry assignment --
    through the enrolment module that owns it. Everything else is reported as
    a reference a human must follow.

    Returns ``(dimension_value, findings)``. A DEMONSTRATED result still is not
    permission to launch: the supervisor re-checks status and assignment
    immediately before every dispatch, and that check is the authoritative one.
    """
    findings: list[Finding] = []
    for reference in contract.authorization_references:
        if reference.kind != "REGISTRY_ASSIGNMENT":
            findings.append(
                Finding(
                    "authorization.reference_manual",
                    UNKNOWN,
                    f"{reference.kind} reference {reference.reference!r} must be "
                    "followed by a human; this tool cannot resolve it",
                    {"kind": reference.kind, "reference": reference.reference},
                )
            )

    if binding is None or program_path is None:
        absent = [
            name
            for name, value in (("--binding", binding), ("--program", program_path))
            if value is None
        ]
        findings.append(
            Finding(
                "authorization.not_checkable",
                UNKNOWN,
                f"no registry to ask without {' and '.join(absent)}, so "
                "authorization stays NOT_DEMONSTRATED",
                {"missing": absent},
            )
        )
        return "NOT_DEMONSTRATED", findings

    from project_atlas.orchestration.program.enrollment import (
        AgentStatus,
        load_registry,
    )

    try:
        registry = load_registry(Path(binding.registry_root))
    except (OSError, ValueError) as exc:  # ProgramError is a ValueError
        findings.append(
            Finding("authorization.registry_unreadable", UNKNOWN,
                    f"the agent registry could not be read: {exc}"))
        return "NOT_DEMONSTRATED", findings

    expected = str(program_path.expanduser().resolve())
    for agent in registry.agents.values():
        if agent.role != binding.agent_role:
            continue
        if agent.status is not AgentStatus.ACTIVE:
            findings.append(
                Finding(
                    "authorization.agent_not_active",
                    WARNING,
                    f"agent {agent.agent_id} holds role {agent.role!r} but is "
                    f"{agent.status.value}",
                    {"agent_id": agent.agent_id, "status": agent.status.value},
                )
            )
            continue
        if agent.assigned_program != expected:
            findings.append(
                Finding(
                    "authorization.assignment_elsewhere",
                    WARNING,
                    f"agent {agent.agent_id} is ACTIVE for role {agent.role!r} but is "
                    f"assigned {agent.assigned_program!r}, not this program",
                    {"agent_id": agent.agent_id, "assigned": agent.assigned_program,
                     "expected": expected},
                )
            )
            continue
        findings.append(
            Finding(
                "authorization.registry_assignment",
                OK,
                f"agent {agent.agent_id} is ACTIVE and assigned this program. The "
                "supervisor re-checks this immediately before every dispatch; that "
                "check, not this one, is what authorizes a launch.",
                {"agent_id": agent.agent_id},
            )
        )
        return "DEMONSTRATED", findings

    findings.append(
        Finding(
            "authorization.no_assignment",
            WARNING,
            f"no ACTIVE agent is assigned this program for role "
            f"{binding.agent_role!r}",
            {"role": binding.agent_role},
        )
    )
    return "NOT_DEMONSTRATED", findings


# -------------------------------------------------------------- the report


CONTENT_CHECKS = (
    "content.placeholder",
    "content.check_unknown_ref",
    "content.requirement_unchecked",
    "content.requirement_presence_only",
    "content.check_orphan",
    "acceptance.argv_empty",
)
PRECONDITION_CHECKS = ("binding.", "dependencies.", "freshness.", "acceptance.executable")


def validate_contract(
    contract: TaskContract,
    *,
    binding: DeploymentBinding | None = None,
    project_root: Path | None = None,
    program_path: Path | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Validate one contract. Executes nothing the contract names."""
    findings: list[Finding] = []
    findings += check_placeholders(contract)
    findings += check_requirement_coverage(contract)
    findings += check_budget_and_limits(contract)
    findings += check_paths_repeated_in_prose(contract)
    findings += check_paths(contract)
    findings += check_runtime(contract)
    findings += check_acceptance_executables(contract, binding)
    findings += check_binding(contract, binding)
    findings += check_dependencies(contract, project_root)
    findings += check_freshness(contract, project_root)
    authorization, auth_findings = check_authorization(contract, binding, program_path)
    findings += auth_findings

    counts = {sev: sum(1 for f in findings if f.severity == sev)
              for sev in (ERROR, WARNING, UNKNOWN, OK)}

    content_failed = any(
        f.severity == ERROR and f.check in CONTENT_CHECKS for f in findings
    )
    precondition_failed = any(
        f.severity == ERROR and f.check.startswith(PRECONDITION_CHECKS) for f in findings
    )
    precondition_unknown = any(
        f.severity == UNKNOWN and f.check.startswith(PRECONDITION_CHECKS)
        for f in findings
    )

    verdict = ("BLOCKED" if counts[ERROR]
               else "READY_WITH_WARNINGS" if counts[WARNING] or counts[UNKNOWN]
               else "READY")

    report: dict[str, Any] = {
        "schema": "atlas.taskcontract.validation/1",
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "verdict": verdict,
        "counts": counts,
        "dimensions": {
            Dimension.STRUCTURALLY_VALID.value: "PASS",
            Dimension.CONTENT_COMPLETE.value: "FAIL" if content_failed else "PASS",
            Dimension.PRECONDITIONS_CHECKED.value: (
                "FAIL" if precondition_failed
                else "UNKNOWN" if precondition_unknown
                else "PASS"
            ),
            Dimension.EXECUTION_AUTHORIZATION.value: authorization,
            Dimension.ACCEPTANCE_OUTCOME.value: "NOT_EVALUATED",
        },
        "checked": {
            "contract_digest": contract_digest(contract),
            "binding_digest": binding_digest(binding) if binding else None,
            "source_item_digest": contract.source.item_digest,
            "base_pin": contract.base_pin,
            "program_path": str(program_path) if program_path else None,
            "project_root": str(project_root) if project_root else None,
        },
        "findings": [asdict(f) for f in findings],
        "grants": (
            "NOTHING. Structural validity is not execution authority, and "
            "acceptance_outcome is NOT_EVALUATED because this tool runs no check."
        ),
        "executed": "no acceptance command was executed",
    }
    if observed_at is not None:
        # Report metadata, kept OUT of every digest so the same input digests
        # the same however often it is validated.
        report["observed_at"] = observed_at
    return report


def report_is_stale(
    report: dict[str, Any],
    *,
    contract: TaskContract,
    binding: DeploymentBinding | None = None,
) -> tuple[bool, list[str]]:
    """Does an earlier report still describe these inputs?

    A prior review or launch approval must not quietly survive a changed
    contract or a changed installation, so this compares identities rather
    than trusting the report's own verdict.
    """
    checked = report.get("checked") or {}
    reasons: list[str] = []
    if checked.get("contract_digest") != contract_digest(contract):
        reasons.append(
            "the contract changed since this report: "
            f"{checked.get('contract_digest')} -> {contract_digest(contract)}"
        )
    current_binding = binding_digest(binding) if binding else None
    if checked.get("binding_digest") != current_binding:
        reasons.append(
            "the deployment binding changed since this report: "
            f"{checked.get('binding_digest')} -> {current_binding}"
        )
    if checked.get("source_item_digest") != contract.source.item_digest:
        reasons.append("the source item digest changed since this report")
    return bool(reasons), reasons
