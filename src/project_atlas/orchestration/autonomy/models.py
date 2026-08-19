"""AS-ORCH-AUTONOMY-001 typed contracts for the autonomous control plane.

Evidence and scheduling state only. Never authority.
GOVERNOR_STATE != AUTHORITY
LEASE != DISPATCH
CERTIFIED != MERGED
MERGE_ELIGIBLE != MERGED
READY_FOR_OWNER_MERGE_GATE != MERGE_AUTHORIZATION
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas_contracts.versions import HASH_PATTERN, ID_PATTERN

AUTONOMY_PACKAGE_ID: Final[Literal["AS-ORCH-AUTONOMY-001"]] = "AS-ORCH-AUTONOMY-001"
DIRECTIVE_ID: Final[Literal["D-AUTONOMY-TRANSITION-001"]] = "D-AUTONOMY-TRANSITION-001"
PIN_RETARGET_PACKAGE_ID: Final[str] = "AS-ORCH-AUTONOMY-001-PIN-RETARGET"
PIN_RETARGET_DIRECTIVE_ID: Final[str] = "D-AUTONOMY-PIN-RETARGET-003"
MAX_AUTONOMOUS_REMEDIATION_CYCLES: Final[int] = 3
# Historical genesis only. Not runtime authority after pin-retarget.
BOOTSTRAP_MAIN: Final[str] = "23ebc0293a8988bc4f144cad6b478c6bff4d32d0"
BOOTSTRAP_TREE: Final[str] = "d7f5059d99e879502570245358e5a1612c52e739"
EXPECTED_BASE_MAIN: Final[str] = BOOTSTRAP_MAIN
EXPECTED_BASE_TREE: Final[str] = BOOTSTRAP_TREE
# Verification expectations for the shipped #398 retarget artifact.
# Missing or corrupt records do not fall back to these constants.
INITIAL_RETARGET_MAIN: Final[str] = "62f8d59f170150d5ceab1610f49be00ad25fdd50"
INITIAL_RETARGET_TREE: Final[str] = "aed48e4854c9f32ed281b5009c92327d93971ae7"
INITIAL_RETARGET_CERTIFIED_HEAD: Final[str] = "aca44c2b207e4eac01b9d54353d3ef8841367e65"
INITIAL_RETARGET_SOURCE_PR: Final[int] = 398
INITIAL_RETARGET_SOURCE_DIRECTIVE: Final[str] = "D-AUTONOMY-OWNER-MERGE-GATE-002"
INITIAL_RETARGET_EVIDENCE_DIGEST: Final[str] = (
    "7265052e8e30a6c3058751a96a9b10c410f2c49797fab700983a562528bdd04a"
)
CANONICAL_REPOSITORY_IDENTITY: Final[str] = "github.com/b0lk13/project-atlas"
PILOT_PACKAGE_ID: Final[str] = "AS-ORCH-AUTONOMY-001-PILOT"
TRUTH_BOUNDARY: Final[str] = (
    "GOVERNOR_STATE != AUTHORITY / LEASE != DISPATCH / CERTIFIED != MERGED / "
    "MERGE_ELIGIBLE != MERGED / READY_FOR_OWNER_MERGE_GATE != MERGE_AUTHORIZATION / "
    "CONTINUATION != 001D MULTI-HOP / PILOT != SUCCESSOR EXECUTION / "
    "OWNER AUTHORITY = STILL REQUIRED"
)

_STATE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SURFACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REL_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_PIN_RE = re.compile(r"^[0-9a-f]{40}$")


class NodeState(StrEnum):
    """Explicit DAG node lifecycle. Transitions are recorded; unknown is rejected."""

    DISCOVERED = "DISCOVERED"
    READY = "READY"
    LEASED = "LEASED"
    ACTIVE = "ACTIVE"
    VERIFYING = "VERIFYING"
    REMEDIATING = "REMEDIATING"
    CERTIFIED = "CERTIFIED"
    OWNER_HELD = "OWNER_HELD"
    MERGE_ELIGIBLE = "MERGE_ELIGIBLE"
    MERGED = "MERGED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    CLOSED = "CLOSED"


class OwnerGateKind(StrEnum):
    """Owner gates A-F. Autonomous code cannot grant any of these."""

    A_PROTECTED_MAIN_MERGE = "A_PROTECTED_MAIN_MERGE"
    B_ACCEPTANCE_WAIVER = "B_ACCEPTANCE_WAIVER"
    C_CERTIFIED_OBJECT_MUTATION = "C_CERTIFIED_OBJECT_MUTATION"
    D_SECURITY_GOVERNANCE_POLICY = "D_SECURITY_GOVERNANCE_POLICY"
    E_DESTRUCTIVE_OPS = "E_DESTRUCTIVE_OPS"
    F_MATERIAL_EXTERNAL_SPEND = "F_MATERIAL_EXTERNAL_SPEND"


class StopReason(StrEnum):
    """Why autonomous continuation halted. Not an authority grant."""

    OWNER_GATE = "OWNER_GATE"
    HARD_BLOCKER = "HARD_BLOCKER"
    NO_ELIGIBLE_WORK = "NO_ELIGIBLE_WORK"
    SAFETY_BOUNDARY = "SAFETY_BOUNDARY"
    RESOURCE_BOUNDARY = "RESOURCE_BOUNDARY"
    PILOT_COMPLETE = "PILOT_COMPLETE"


class AgentCapability(StrEnum):
    """Closed capability vocabulary. Unknown capabilities fail closed."""

    DISCOVER = "DISCOVER"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    REMEDIATE = "REMEDIATE"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"


class RiskTag(StrEnum):
    """Triggers for mandatory adversarial review."""

    SECURITY_RELEVANT = "SECURITY_RELEVANT"
    CONTROL_PLANE = "CONTROL_PLANE"
    AUTHORIZATION = "AUTHORIZATION"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    CROSS_PROJECT_ISOLATION = "CROSS_PROJECT_ISOLATION"
    HIGH_BLAST_RADIUS = "HIGH_BLAST_RADIUS"


class ExecutionHostClass(StrEnum):
    """Where leased work may run. In-process is the only host this package executes."""

    IN_PROCESS = "IN_PROCESS"
    EXTERNAL_AGENT = "EXTERNAL_AGENT"


class AdvancementReason(StrEnum):
    """Why a trusted runtime anchor advanced. Not an authority grant."""

    VERIFIED_OWNER_AUTHORIZED_MERGE = "VERIFIED_OWNER_AUTHORIZED_MERGE"


class TrustState(StrEnum):
    """Runtime trust classification. UNVERIFIABLE never falls back."""

    TRUSTED = "TRUSTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    BLOCKED = "BLOCKED"
    TARGET_MOVED = "TARGET_MOVED"


class CiState(StrEnum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"


class IvState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    ROUTED = "ROUTED"
    PASS = "PASS"
    FAIL = "FAIL"


class CertificationState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    CERTIFIED = "CERTIFIED"
    BLOCKED = "BLOCKED"


class MutationSurface(BaseModel):
    """Semantic/physical mutation surface used by the overlap gate."""

    model_config = ConfigDict(extra="forbid")

    surface_id: str = Field(min_length=1, max_length=128)
    paths: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    semantic: str = Field(min_length=1, max_length=64)

    @field_validator("surface_id")
    @classmethod
    def _surface_id(cls, value: str) -> str:
        if not _SURFACE_RE.fullmatch(value):
            raise ValueError("surface_id must be a safe identifier")
        return value

    @field_validator("semantic")
    @classmethod
    def _semantic(cls, value: str) -> str:
        if not _STATE_RE.fullmatch(value):
            raise ValueError("semantic must be an uppercase identifier")
        return value

    @field_validator("paths")
    @classmethod
    def _paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if not _REL_PATH_RE.fullmatch(path):
                raise ValueError("mutation paths must be safe relative identifiers")
        return value


class RetryPolicy(BaseModel):
    """Bounded autonomous retry. Exceeding max cycles is a hard block."""

    model_config = ConfigDict(extra="forbid")

    max_autonomous_cycles: Literal[3] = 3
    cycles_used: int = Field(default=0, ge=0, le=MAX_AUTONOMOUS_REMEDIATION_CYCLES)


class IvRequirements(BaseModel):
    """When certification is required, implementer cannot be the verifier."""

    model_config = ConfigDict(extra="forbid")

    certification_required: bool
    implementer_cannot_verify: Literal[True] = True
    adversarial_required: bool = False


class WorkNode(BaseModel):
    """One DAG node. TaskDirective != execution still holds for 001B payloads."""

    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    objective: str = Field(min_length=1, max_length=512)
    base_pin: str = Field(min_length=40, max_length=40)
    dependencies: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    mutation_surface: MutationSurface
    execution_host_class: ExecutionHostClass
    agent_capabilities_required: tuple[AgentCapability, ...] = Field(min_length=1, max_length=8)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1, max_length=16)
    test_requirements: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    iv_requirements: IvRequirements
    owner_gate: OwnerGateKind | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    state: NodeState = NodeState.DISCOVERED
    risk_tags: tuple[RiskTag, ...] = Field(default_factory=tuple, max_length=8)
    destructive: Literal[False] = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False

    @field_validator("base_pin")
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("base_pin must be a 40-char lowercase git SHA")
        return value

    @field_validator("dependencies")
    @classmethod
    def _deps(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not re.fullmatch(ID_PATTERN, item):
                raise ValueError("dependency ids must be safe identifiers")
        return value

    @model_validator(mode="after")
    def _no_authority(self) -> WorkNode:
        if self.merge_authorized is not False:
            raise ValueError("WorkNode cannot authorize merge")
        if self.execution_authorized is not False:
            raise ValueError("WorkNode cannot authorize privileged execution")
        if self.destructive is not False:
            raise ValueError("destructive nodes are rejected by this control plane")
        return self


class AgentRecord(BaseModel):
    """Registered agent identity and capabilities."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    capabilities: tuple[AgentCapability, ...] = Field(min_length=1, max_length=8)
    available: bool = True


class AgentLease(BaseModel):
    """Bounded lease. Scope expansion requires governor reassignment."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    agent_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    package_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    branch: str = Field(min_length=1, max_length=256)
    worktree: str = Field(min_length=1, max_length=256)
    base_pin: str = Field(min_length=40, max_length=40)
    authorized_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    forbidden_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    capabilities: tuple[AgentCapability, ...] = Field(min_length=1, max_length=8)
    start_state: NodeState
    expected_output: str = Field(min_length=1, max_length=256)
    expiry_or_terminal_condition: str = Field(min_length=1, max_length=128)
    active: bool = True
    sequence: int = Field(ge=1, le=1_000_000)

    @field_validator("base_pin")
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("lease base_pin must be a 40-char lowercase git SHA")
        return value

    @field_validator("authorized_paths", "forbidden_paths")
    @classmethod
    def _paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if not _REL_PATH_RE.fullmatch(path):
                raise ValueError("lease paths must be safe relative identifiers")
        return value

    @field_validator("expiry_or_terminal_condition")
    @classmethod
    def _condition(cls, value: str) -> str:
        if not _STATE_RE.fullmatch(value):
            raise ValueError("terminal condition must be an uppercase identifier")
        return value


class TransitionRecord(BaseModel):
    """Auditable DAG transition. Sequence is logical, not wall-clock."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=1_000_000)
    package_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    from_state: NodeState
    to_state: NodeState
    reason: str = Field(min_length=1, max_length=256)


class DagEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    target: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)


class OverlapState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parallel_execution: bool
    conflict_surfaces: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    reason: str = Field(min_length=1, max_length=256)


class ExecutionPlan(BaseModel):
    """Authoritative answers: what can run, wait, run in parallel, needs owner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-AUTONOMY-001"] = AUTONOMY_PACKAGE_ID
    what_can_run_now: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    what_must_wait: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    what_can_run_in_parallel: tuple[tuple[str, ...], ...] = Field(
        default_factory=tuple, max_length=32
    )
    what_requires_owner_authority: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    stop_reason: StopReason | None = None
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    truth_boundary: str = TRUTH_BOUNDARY


class TrustedAnchorRecord(BaseModel):
    """Persisted trusted runtime anchor. Evidence identity, not owner authority.

    ``record_created_at`` is omitted: hashed canonical evidence must stay
    deterministic (NFR-001). ``sequence`` is the logical history key.
    COMMIT_IDENTITY (trusted_main / certified_head) is distinct from
    CONTENT_IDENTITY (trusted_tree / certified_tree).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    repository_identity: str = Field(min_length=1, max_length=256)
    trusted_main: str = Field(min_length=40, max_length=40)
    trusted_tree: str = Field(min_length=40, max_length=40)
    predecessor_main: str = Field(min_length=40, max_length=40)
    predecessor_tree: str = Field(min_length=40, max_length=40)
    advancement_reason: AdvancementReason
    source_package: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    source_directive: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    source_pr: int = Field(ge=1, le=1_000_000)
    merge_commit: str = Field(min_length=40, max_length=40)
    merge_parent_1: str = Field(min_length=40, max_length=40)
    merge_parent_2: str = Field(min_length=40, max_length=40)
    merge_tree: str = Field(min_length=40, max_length=40)
    certified_head: str = Field(min_length=40, max_length=40)
    certified_tree: str = Field(min_length=40, max_length=40)
    certification_status: Literal["CERTIFIED"]
    independent_verification_status: Literal["PASS"]
    post_merge_seal: Literal["PASS"]
    post_merge_ci: Literal["PASS"]
    evidence_reference: str = Field(min_length=1, max_length=256)
    evidence_digest: str = Field(min_length=64, max_length=64)
    sequence: int = Field(ge=1, le=1_000_000)
    record_digest: str = Field(min_length=64, max_length=64)

    @field_validator(
        "trusted_main",
        "trusted_tree",
        "predecessor_main",
        "predecessor_tree",
        "merge_commit",
        "merge_parent_1",
        "merge_parent_2",
        "merge_tree",
        "certified_head",
        "certified_tree",
    )
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("anchor pins must be 40-char lowercase git SHAs")
        return value

    @field_validator("evidence_digest", "record_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not re.fullmatch(HASH_PATTERN, value):
            raise ValueError("digest must be a SHA-256 hex digest")
        return value

    @field_validator("repository_identity", "evidence_reference")
    @classmethod
    def _safe_ref(cls, value: str) -> str:
        if ".." in value.split("/") or "\\" in value or value.startswith("/") or ":" in value:
            raise ValueError("reference must be a safe relative identifier")
        if not _REL_PATH_RE.fullmatch(value):
            raise ValueError("reference must be a safe relative identifier")
        return value

    @model_validator(mode="after")
    def _commit_matches_merge(self) -> TrustedAnchorRecord:
        if self.trusted_main != self.merge_commit:
            raise ValueError("trusted_main must equal merge_commit")
        if self.trusted_tree != self.merge_tree:
            raise ValueError("trusted_tree must equal merge_tree")
        return self

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("record_digest")
        return payload


class AdvancementProof(BaseModel):
    """Owner-supplied advancement artifact. Governor verifies; never invents."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    repository_identity: str = Field(min_length=1, max_length=256)
    owner_authorization: Literal["OWNER_AUTHORIZED"]
    expected_previous_main: str = Field(min_length=40, max_length=40)
    expected_previous_tree: str = Field(min_length=40, max_length=40)
    authorized_candidate_head: str = Field(min_length=40, max_length=40)
    authorized_candidate_tree: str = Field(min_length=40, max_length=40)
    merge_commit: str = Field(min_length=40, max_length=40)
    merge_parent_1: str = Field(min_length=40, max_length=40)
    merge_parent_2: str = Field(min_length=40, max_length=40)
    merge_tree: str = Field(min_length=40, max_length=40)
    post_merge_seal: Literal["PASS", "FAIL"]
    post_merge_ci: Literal["PASS", "FAIL"]
    evidence_reference: str = Field(min_length=1, max_length=256)
    evidence_digest: str = Field(min_length=64, max_length=64)
    source_package: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    source_directive: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    source_pr: int = Field(ge=1, le=1_000_000)
    evidence_payload: dict[str, object] | None = None

    @field_validator(
        "expected_previous_main",
        "expected_previous_tree",
        "authorized_candidate_head",
        "authorized_candidate_tree",
        "merge_commit",
        "merge_parent_1",
        "merge_parent_2",
        "merge_tree",
    )
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("proof pins must be 40-char lowercase git SHAs")
        return value

    @field_validator("evidence_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not re.fullmatch(HASH_PATTERN, value):
            raise ValueError("evidence_digest must be a SHA-256 hex digest")
        return value

    @field_validator("repository_identity", "evidence_reference")
    @classmethod
    def _safe_ref(cls, value: str) -> str:
        if ".." in value.split("/") or "\\" in value or value.startswith("/") or ":" in value:
            raise ValueError("reference must be a safe relative identifier")
        if not _REL_PATH_RE.fullmatch(value):
            raise ValueError("reference must be a safe relative identifier")
        return value


class GovernorState(BaseModel):
    """Single logical governor snapshot. Reconstructable and hashable."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-AUTONOMY-001"] = AUTONOMY_PACKAGE_ID
    directive_id: Literal["D-AUTONOMY-TRANSITION-001"] = DIRECTIVE_ID
    current_main: str = Field(min_length=40, max_length=40)
    current_tree: str = Field(min_length=40, max_length=40)
    trusted_runtime_main: str = Field(min_length=40, max_length=40)
    trusted_runtime_tree: str = Field(min_length=40, max_length=40)
    bootstrap_main: str = BOOTSTRAP_MAIN
    bootstrap_tree: str = BOOTSTRAP_TREE
    trust_state: TrustState
    target_moved: bool
    nodes: tuple[WorkNode, ...] = Field(default_factory=tuple, max_length=256)
    agents: tuple[AgentRecord, ...] = Field(default_factory=tuple, max_length=32)
    leases: tuple[AgentLease, ...] = Field(default_factory=tuple, max_length=64)
    dependencies: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    dag_edges: tuple[DagEdge, ...] = Field(default_factory=tuple, max_length=256)
    mutation_surfaces: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    overlap_state: OverlapState
    ci_state: CiState = CiState.UNKNOWN
    iv_state: IvState = IvState.NOT_REQUIRED
    certification_state: CertificationState = CertificationState.NOT_STARTED
    owner_gates: tuple[OwnerGateKind, ...] = Field(default_factory=tuple, max_length=8)
    hard_blockers: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    sequence: int = Field(ge=0, le=1_000_000)
    merge_authorized: Literal[False] = False
    successor_execution_under_new_model: Literal["NOT_YET_ACTIVE"] = "NOT_YET_ACTIVE"
    truth_boundary: str = TRUTH_BOUNDARY

    @field_validator(
        "current_main",
        "current_tree",
        "trusted_runtime_main",
        "trusted_runtime_tree",
        "bootstrap_main",
        "bootstrap_tree",
    )
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("governor pins must be 40-char lowercase git SHAs")
        return value

    def packages_in(self, *states: NodeState) -> tuple[str, ...]:
        wanted = frozenset(states)
        return tuple(node.package_id for node in self.nodes if node.state in wanted)


class EvidenceBundle(BaseModel):
    """Deterministic reconstructable evidence. Hash is identity, not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-AUTONOMY-001"] = AUTONOMY_PACKAGE_ID
    bundle_kind: str = Field(min_length=1, max_length=64)
    payload_sha256: str = Field(min_length=64, max_length=64)
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("bundle_kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if not _STATE_RE.fullmatch(value):
            raise ValueError("bundle_kind must be an uppercase identifier")
        return value

    @field_validator("payload_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not re.fullmatch(HASH_PATTERN, value):
            raise ValueError("payload_sha256 must be a SHA-256 hex digest")
        return value


class LiveInventory(BaseModel):
    """Observed repository facts used for discovery. Not a work authorization."""

    model_config = ConfigDict(extra="forbid")

    current_main: str = Field(min_length=40, max_length=40)
    current_tree: str = Field(min_length=40, max_length=40)
    worktree_status: str = Field(min_length=1, max_length=64)
    open_relevant_prs: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    active_successor_packages: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    r2_created: Literal["YES", "NO"] = "NO"
    r7_created: Literal["YES", "NO"] = "NO"
    authentic_r6_resumed: Literal["YES", "NO"] = "NO"
    as_orch_001e_started: Literal["YES", "NO"] = "NO"
    pr396_mutated: Literal["YES", "NO", "UNOBSERVED"] = "UNOBSERVED"

    @field_validator("current_main", "current_tree")
    @classmethod
    def _pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("inventory pins must be 40-char lowercase git SHAs")
        return value


class DiscoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    eligible: bool
    destructive: bool
    owner_gate: OwnerGateKind | None = None
    reason: str = Field(min_length=1, max_length=256)


class DiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-AUTONOMY-001"] = AUTONOMY_PACKAGE_ID
    inventory: LiveInventory
    trusted_runtime_main: str = Field(min_length=40, max_length=40)
    trusted_runtime_tree: str = Field(min_length=40, max_length=40)
    target_moved: bool
    successor_already_started: bool
    candidates: tuple[DiscoveryCandidate, ...] = Field(default_factory=tuple, max_length=32)
    selected_package_id: str | None = None
    case: Literal["A-A-PREFLIGHT", "A-B"] = "A-A-PREFLIGHT"
    blocker: str | None = None

    @field_validator("trusted_runtime_main", "trusted_runtime_tree")
    @classmethod
    def _trusted_pin(cls, value: str) -> str:
        if not _PIN_RE.fullmatch(value):
            raise ValueError("discovery trusted pins must be 40-char lowercase git SHAs")
        return value
