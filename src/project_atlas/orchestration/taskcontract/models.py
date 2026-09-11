"""One versionable task contract: AS-TASK-CONTRACT-001.

WHAT A CONTRACT IS
    The single structured source for three things that otherwise drift apart:
    the instruction a worker receives, the program configuration that launches
    it, and the acceptance checks that judge the result. Written once, rendered
    into all three, so a changed path changes everywhere or nowhere.

WHAT A CONTRACT IS NOT
    ``VALID_CONTRACT != EXECUTION_AUTHORIZATION``. A structurally valid,
    content-complete contract authorizes nothing. Authorization lives in the
    agent registry and is re-checked by the supervisor immediately before every
    dispatch; a contract can only *reference* it. There is deliberately no
    ``authorized`` field: a boolean in a file the task author writes would be
    an authority claim with no principal behind it.

    ``VALID_CONTRACT != TASK_COMPLETE``. Nothing here observes a result.

TASK CONTENT vs DEPLOYMENT BINDING
    ``TaskContract`` is repository-relative and portable: it survives being
    moved between machines, checkouts and operators. ``DeploymentBinding``
    holds the absolute workspace, state, registry and interpreter paths of one
    installation. They are separate objects with separate digests because a
    contract reviewed on one host must not silently inherit approval on
    another -- a changed binding invalidates binding-dependent validation
    while leaving the contract's own review intact.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.autonomy.models import AgentCapability
from project_atlas.orchestration.program.models import AcceptanceCheck, AcceptanceKind
from project_atlas.orchestration.program.profiles import AdapterKind

PACKAGE_ID: Final[Literal["AS-TASK-CONTRACT-001"]] = "AS-TASK-CONTRACT-001"
SCHEMA_VERSION: Final[Literal[1]] = 1

#: Acceptance kinds that observe that something EXISTS or CHANGED, never what
#: it does. Supporting evidence for a behavioural requirement, never the whole
#: of it -- a worker that writes an empty file passes both.
PRESENCE_ONLY_KINDS: Final[frozenset[AcceptanceKind]] = frozenset(
    {AcceptanceKind.FILE_EXISTS, AcceptanceKind.GIT_TREE_CHANGED}
)

#: Markers a template leaves behind. Matched case-sensitively on purpose:
#: lowercase "todo" appears in ordinary prose, "TODO" does not.
_PLACEHOLDER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"OPERATOR[-_ ]SUPPLIED"),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"<[A-Za-z0-9_ -]{1,40}>"),
    re.compile(r"\{\{.{0,40}?\}\}"),
    re.compile(r"\bXXX\b"),
)

_SHA1_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")


class TaskContractError(ValueError):
    """A refusal from this package, with a stable code."""

    def __init__(self, message: str, *, code: str = "TASK_CONTRACT_ERROR") -> None:
        super().__init__(message)
        self.code = code


def find_placeholders(text: str) -> tuple[str, ...]:
    """Unresolved template markers in ``text``, in order, de-duplicated."""
    found: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0)
            if token not in found:
                found.append(token)
    return tuple(found)


class VerificationMode(StrEnum):
    """How a result requirement is judged.

    The three are kept apart because collapsing them is how a task acquires
    imaginary rigour: a requirement nobody can check automatically is not the
    same as one that simply has no check written yet, and neither is the same
    as one a command decides.
    """

    #: A check in this contract decides it.
    AUTOMATED = "AUTOMATED"
    #: A person must judge it. No check can, and the contract says so.
    HUMAN_REVIEW = "HUMAN_REVIEW"
    #: Automatable in principle, but no suitable check exists yet. Honest
    #: about the gap rather than pretending a weaker check covers it.
    NO_CHECK_AVAILABLE = "NO_CHECK_AVAILABLE"


class SourceReference(BaseModel):
    """Where this contract's intent came from, pinned so drift is visible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Repository-relative path of the declared origination source.
    source_path: str = Field(min_length=1, max_length=512)
    #: The backlog item's own identifier, as the source declares it.
    item_id: str = Field(min_length=1, max_length=128)
    #: Content digest of the item as read. Changes when the item is edited.
    item_digest: str = Field(min_length=8, max_length=128)
    #: Revision the source was read at, when the caller knows it.
    source_revision: str | None = Field(default=None, max_length=64)
    #: The item's own title, carried for the operator view.
    title: str = Field(min_length=1, max_length=512)


class AuthorizationReference(BaseModel):
    """A pointer at authorization that lives somewhere else.

    Deliberately has no boolean and no free-text approval. "operator approved"
    written in a backlog item is prose; this records *where* an authorization
    decision can be read, and the validator checks it through the mechanism
    that owns it -- never by believing this record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["REGISTRY_ASSIGNMENT", "OWNER_GATE", "PROGRAM_APPROVAL", "PR_REVIEW"]
    #: Where to look: a registry agent id, a gate name, a PR or document path.
    reference: str = Field(min_length=1, max_length=512)
    note: str = Field(default="", max_length=512)


class ContextSource(BaseModel):
    """One bounded piece of context the worker is given, with its provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=128)
    #: Repository-relative. Absolute paths belong to the deployment binding.
    path: str = Field(min_length=1, max_length=512)
    #: Why the worker needs it. An unexplained file is noise in a prompt.
    why: str = Field(min_length=1, max_length=512)
    digest: str | None = Field(default=None, max_length=128)

    @field_validator("path")
    @classmethod
    def _relative(cls, value: str) -> str:
        return _reject_absolute(value, field="context path")


class ResultRequirement(BaseModel):
    """One thing the finished work must be true of, with a stable identifier.

    The identifier is what lets the instruction, the check and the evidence
    refer to the same requirement instead of three prose restatements that
    drift.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1, max_length=128)
    #: Stated as an observable property of the result, not as an activity.
    statement: str = Field(min_length=1, max_length=2048)
    verification: VerificationMode
    #: ``check_id`` values from this contract's acceptance checks.
    check_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    #: What a reviewer should look at when verification is not AUTOMATED.
    review_note: str = Field(default="", max_length=1024)


class RuntimeRequirement(BaseModel):
    """What the worker runtime must be able to do."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: AdapterKind
    capabilities: tuple[AgentCapability, ...] = Field(min_length=1, max_length=8)
    adapter_min_version: str | None = Field(default=None, max_length=64)
    #: Free-form constraints the contract wants recorded, e.g. "network off".
    constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=16)


class ContractLimits(BaseModel):
    """Bounds on the attempt, in the same units the supervisor enforces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_task_launches: int = Field(ge=1, le=10_000)
    max_attempts_per_task: int = Field(ge=1, le=20)
    max_task_seconds: int = Field(ge=1, le=86_400)
    max_concurrent_workers: int = Field(default=1, ge=1, le=16)


class BudgetTerms(BaseModel):
    """What is actually enforceable, stated separately from what is hoped.

    ``ESTIMATED_COST != BILLED_SPEND``. A per-launch ceiling is forwarded to a
    runtime that supports one and is checked against that runtime's own
    client-side estimate. It is not an account spending limit, and nothing in
    this package can make it one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_estimated_cost_usd: float | None = Field(default=None, gt=0.0, le=10_000.0)
    #: Named honestly, e.g. "runtime per-launch flag" or "not enforceable".
    enforced_by: str = Field(min_length=1, max_length=256)
    not_enforced: tuple[str, ...] = Field(default_factory=tuple, max_length=8)


class EvidenceTerms(BaseModel):
    """Where the result's evidence lands and what handover requires."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Repository-relative locations written by the run.
    evidence_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    handover_conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=16)

    @field_validator("evidence_paths")
    @classmethod
    def _relative(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_reject_absolute(item, field="evidence path") for item in value)


def _reject_absolute(value: str, *, field: str) -> str:
    """Task content is repository-relative. Absolute paths are a binding."""
    text = value.strip()
    if not text:
        raise TaskContractError(f"{field} is blank", code="PATH_BLANK")
    if text.startswith("/") or text.startswith("~") or re.match(r"^[A-Za-z]:[\\/]", text):
        raise TaskContractError(
            f"{field} {value!r} is absolute; absolute paths belong to the "
            "deployment binding, not to task content",
            code="ABSOLUTE_PATH_IN_CONTRACT",
        )
    if ".." in text.split("/"):
        raise TaskContractError(
            f"{field} {value!r} escapes the workspace", code="PATH_ESCAPES_WORKSPACE"
        )
    return text


class TaskContract(BaseModel):
    """A backlog item, made executable-shaped and reviewable. Grants nothing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = SCHEMA_VERSION
    package_id: Literal["AS-TASK-CONTRACT-001"] = PACKAGE_ID
    contract_id: str = Field(min_length=1, max_length=128)
    contract_version: int = Field(default=1, ge=1, le=10_000)

    source: SourceReference
    objective: str = Field(min_length=1, max_length=2048)
    #: What is observably true when this is done. Not a list of activities.
    observable_outcome: str = Field(min_length=1, max_length=2048)
    scope: tuple[str, ...] = Field(min_length=1, max_length=32)
    exclusions: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    owner: str = Field(min_length=1, max_length=256)
    authorization_references: tuple[AuthorizationReference, ...] = Field(
        default_factory=tuple, max_length=8
    )

    depends_on: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    #: The conditions under which the task becomes runnable, in words a
    #: reviewer can check. Dependencies alone rarely say it.
    executable_when: tuple[str, ...] = Field(default_factory=tuple, max_length=16)

    repository: str = Field(min_length=1, max_length=512)
    base_pin: str = Field(min_length=40, max_length=40)

    mutation_paths: tuple[str, ...] = Field(min_length=1, max_length=64)
    expected_output_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=64)

    runtime: RuntimeRequirement
    context: tuple[ContextSource, ...] = Field(default_factory=tuple, max_length=32)
    requirements: tuple[ResultRequirement, ...] = Field(min_length=1, max_length=32)
    acceptance: tuple[AcceptanceCheck, ...] = Field(min_length=1, max_length=32)
    limits: ContractLimits
    budget: BudgetTerms
    evidence: EvidenceTerms = Field(default_factory=EvidenceTerms)

    #: Never true. Present so a reader looking for the authority field finds
    #: the answer rather than assuming the absence means "unrestricted".
    execution_authorized: Literal[False] = False
    merge_authorized: Literal[False] = False

    @field_validator("base_pin")
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _SHA1_RE.match(value):
            raise TaskContractError(
                "base_pin must be a full 40-character lowercase commit sha",
                code="BASE_PIN_MALFORMED",
            )
        return value

    @field_validator("mutation_paths", "expected_output_paths")
    @classmethod
    def _relative_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_reject_absolute(item, field="path") for item in value)


class DeploymentBinding(BaseModel):
    """One installation's absolute paths. Separately digested on purpose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1, max_length=128)
    #: Absolute. The checkout the worker mutates.
    workspace_root: str = Field(min_length=1, max_length=4096)
    #: Absolute. Program state never lives inside the workspace.
    state_root: str = Field(min_length=1, max_length=4096)
    #: Absolute. Where the agent registry lives.
    registry_root: str = Field(min_length=1, max_length=4096)
    #: Absolute path to the interpreter acceptance COMMANDs should use. Bare
    #: ``python`` has been observed not to resolve on hosts that have python3.
    interpreter: str = Field(min_length=1, max_length=4096)
    #: The program profile this task runs under, and the registry role.
    profile_ref: str = Field(min_length=1, max_length=128)
    agent_role: str = Field(min_length=1, max_length=128)
    #: Distinct verifier profile when independent verification is required.
    #: Operator/binding decision — never invented by the contract renderer.
    verifier_profile_ref: str | None = Field(default=None, max_length=128)

    @field_validator("workspace_root", "state_root", "registry_root", "interpreter")
    @classmethod
    def _absolute(cls, value: str) -> str:
        text = value.strip()
        if not (text.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", text)):
            raise TaskContractError(
                f"deployment binding path {value!r} must be absolute",
                code="BINDING_PATH_NOT_ABSOLUTE",
            )
        return text

    @field_validator("verifier_profile_ref")
    @classmethod
    def _opt_verifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        return text


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def contract_digest(contract: TaskContract) -> str:
    """Content identity of a contract.

    Every field participates: the contract carries no observation time, no
    hostname and no run counter, so the same explicit input always digests the
    same. Report metadata is kept out of this object precisely so that stays
    true.
    """
    return hashlib.sha256(
        _canonical(contract.model_dump(mode="json")).encode("utf-8")
    ).hexdigest()


def binding_digest(binding: DeploymentBinding) -> str:
    """Identity of one installation's paths, separate from the contract's.

    ``None`` optional fields are excluded so adding optional binding knobs
    does not silently rewrite digests of bindings that never set them.
    """
    return hashlib.sha256(
        _canonical(binding.model_dump(mode="json", exclude_none=True)).encode("utf-8")
    ).hexdigest()
