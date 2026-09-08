"""AT3-103 — Evidence attestation, v1.

A typed, content-addressed statement that one producer observed one result
for one exact object under one execution identity. It replaces the
presence-only ``{"evidence_ref": "..."}`` of proof v1.

Honesty rules made structural rather than left to a flag:

- ``producer.kind == "model"`` is refused at construction — a model's claim is
  never evidence (``MODEL CLAIM != PROOF``);
- ``INDEPENDENT_VERIFICATION`` and ``ADV`` attestations must *declare*
  independence from the implementer (``independent_of_implementer: true``);
  a declaration is not an observation, and a later package binds it to a
  principal registry;
- ``result.summary`` accepts only identifier keys with integer counts, and
  refuses authority-shaped keys, so an attestation cannot smuggle
  ``merge_authorization`` or ``trust_score`` into a proof;
- every attestation is object-bound (``DEP_HEAD`` and ``DEP_TREE`` are always
  among its dependencies) — an attestation for another object is a different
  attestation.

The stage vocabulary is duplicated from ``project_atlas.atlas3.proof`` on
purpose: ``atlas_contracts`` is the lower layer and must not import Core. A
test pins the two tuples equal.

Domain neutrality: ``evidence_type`` is an open identifier constrained by the
stage compatibility table below. v1 lists only the software types proof v2
needs; a later profile adds research/learning types by extending the table,
not by a second attestation system.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from atlas_contracts.canonical import content_digest, short_id
from atlas_contracts.execution_identity import GIT_SHA_PATTERN
from atlas_contracts.identity import safe_relative_component
from atlas_contracts.versions import HASH_PATTERN, ID_PATTERN

EVIDENCE_ATTESTATION_SCHEMA: Final[str] = "atlas.evidence-attestation.v1"
EVIDENCE_ATTESTATION_SCHEMA_VERSION: Final[int] = 1
ATTESTATION_ID_PREFIX: Final[str] = "att"

EVIDENCE_STAGES: Final[tuple[str, ...]] = (
    "TASK",
    "IMPLEMENTATION",
    "TESTS",
    "CI",
    "INDEPENDENT_VERIFICATION",
    "ADV",
    "INTEGRATION",
    "POST_MERGE",
)

STAGE_EVIDENCE_TYPES: Final[dict[str, frozenset[str]]] = {
    "TASK": frozenset({"TASK_RECORD"}),
    "IMPLEMENTATION": frozenset({"IMPLEMENTATION_RECORD"}),
    "TESTS": frozenset({"TEST_RESULT", "LINT_RESULT", "TYPECHECK_RESULT"}),
    "CI": frozenset({"CI_RESULT"}),
    "INDEPENDENT_VERIFICATION": frozenset({"VERIFICATION_RESULT"}),
    "ADV": frozenset({"ADVERSARIAL_RESULT"}),
    "INTEGRATION": frozenset({"INTEGRATION_RESULT"}),
    "POST_MERGE": frozenset({"POST_MERGE_RESULT"}),
}
EVIDENCE_TYPES: Final[frozenset[str]] = frozenset().union(*STAGE_EVIDENCE_TYPES.values())
INDEPENDENT_STAGES: Final[frozenset[str]] = frozenset({"INDEPENDENT_VERIFICATION", "ADV"})

PRODUCER_KINDS: Final[tuple[str, ...]] = ("tool", "ci", "human", "agent", "model")
RESULT_STATUSES: Final[tuple[str, ...]] = ("PASS", "FAIL", "UNKNOWN")

# Vocabulary aligned with the (unmerged) atlas-dag evidence graph so the two
# converge if it lands; names only, no code or authority transferred.
DEPENDENCY_CLASSES: Final[tuple[str, ...]] = (
    "DEP_HEAD",
    "DEP_TREE",
    "DEP_PARENT_HEAD",
    "DEP_MAIN_HEAD",
    "DEP_PATH_SET",
    "DEP_SUBSYSTEM",
    "DEP_PLATFORM",
    "DEP_TEST_SET",
    "DEP_TOOLCHAIN",
    "DEP_VERIFIER_PRINCIPAL",
    "DEP_VERIFIER_SESSION",
)
OBJECT_DEPENDENCIES: Final[frozenset[str]] = frozenset({"DEP_HEAD", "DEP_TREE"})

AUTHORITY_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "merge_authorization",
        "merge_authorized",
        "certified_for_merge",
        "execution_authorized",
        "owner_authority",
        "owner_authorized",
        "owner_origin",
        "trust_score",
        "graph_winner",
        "self_merge",
        "auto_merge",
        "promoted_to_truth_core",
    }
)

_SEAL_CONTEXT_KEY: Final[str] = "atlas_contracts.seal"
_DIGEST_FIELDS: Final[frozenset[str]] = frozenset({"content_hash", "attestation_id"})


class AttestationError(ValueError):
    """Fail-closed attestation error with a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _sealing(info: ValidationInfo) -> bool:
    context = info.context
    return bool(context and context.get(_SEAL_CONTEXT_KEY) is True)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Producer(_Contract):
    kind: Literal["tool", "ci", "human", "agent", "model"]
    name: str = Field(pattern=ID_PATTERN, max_length=128)
    version: str = Field(min_length=1, max_length=128, pattern=r"^\S+$")
    independent_of_implementer: bool = False

    @model_validator(mode="after")
    def _model_is_not_evidence(self) -> Producer:
        if self.kind == "model":
            raise AttestationError(
                "MODEL_PRODUCER_NOT_EVIDENCE", "a model claim is never an evidence attestation"
            )
        return self


class ObjectBinding(_Contract):
    head: str = Field(pattern=GIT_SHA_PATTERN)
    tree: str = Field(pattern=GIT_SHA_PATTERN)


class AttestationResult(_Contract):
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    exit_code: int | None = Field(default=None, ge=-255, le=255)
    artifact_digest: str | None = Field(default=None, pattern=HASH_PATTERN)
    summary: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _summary_keys(self) -> AttestationResult:
        for key, value in self.summary.items():
            if key in AUTHORITY_FIELD_NAMES or key.lower() in AUTHORITY_FIELD_NAMES:
                raise AttestationError(
                    "AUTHORITY_FIELD_FORBIDDEN", f"summary key {key!r} is an authority field"
                )
            if not key or not key[0].isalnum() or any(c.isspace() for c in key):
                raise AttestationError("SUMMARY_KEY_INVALID", f"summary key {key!r} is not an id")
            if isinstance(value, bool) or value < 0:
                raise AttestationError(
                    "SUMMARY_VALUE_INVALID", f"summary value for {key!r} must be a count"
                )
        return self


class EvidenceAttestation(_Contract):
    """Content-addressed evidence for one stage of one object under one identity."""

    schema_id: Literal["atlas.evidence-attestation.v1"] = Field(
        default="atlas.evidence-attestation.v1", alias="schema"
    )
    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1, max_length=128)
    execution_identity_digest: str = Field(pattern=HASH_PATTERN)
    stage: Literal[
        "TASK",
        "IMPLEMENTATION",
        "TESTS",
        "CI",
        "INDEPENDENT_VERIFICATION",
        "ADV",
        "INTEGRATION",
        "POST_MERGE",
    ]
    evidence_type: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    producer: Producer
    object_binding: ObjectBinding = Field(alias="object")
    command_ref: str | None = Field(default=None, min_length=1, max_length=512)
    result: AttestationResult
    dependencies: tuple[str, ...]
    content_hash: str = Field(pattern=HASH_PATTERN)
    attestation_id: str = Field(pattern=r"^att-[0-9a-f]{16}$")

    @model_validator(mode="before")
    @classmethod
    def _seal_placeholders(cls, data: Any, info: ValidationInfo) -> Any:
        if not _sealing(info) or not isinstance(data, Mapping):
            return data
        if any(key in data for key in _DIGEST_FIELDS):
            raise AttestationError(
                "DIGEST_SUPPLIED_ON_SEAL", "content_hash/attestation_id are computed, not supplied"
            )
        placeholder = "0" * 64
        return {
            **data,
            "content_hash": placeholder,
            "attestation_id": short_id(ATTESTATION_ID_PREFIX, placeholder),
        }

    @model_validator(mode="after")
    def _verify(self, info: ValidationInfo) -> EvidenceAttestation:
        try:
            safe_relative_component(self.project_id, label="project id")
        except ValueError as exc:
            raise AttestationError("UNSAFE_PROJECT_ID", str(exc)) from exc
        allowed = STAGE_EVIDENCE_TYPES[self.stage]
        if self.evidence_type not in allowed:
            raise AttestationError(
                "EVIDENCE_TYPE_STAGE_MISMATCH",
                f"{self.evidence_type} cannot evidence stage {self.stage}",
            )
        if self.stage in INDEPENDENT_STAGES and not self.producer.independent_of_implementer:
            raise AttestationError(
                "INDEPENDENCE_NOT_DECLARED",
                f"{self.stage} evidence must declare independence from the implementer",
            )
        deps = list(self.dependencies)
        if any(dep not in DEPENDENCY_CLASSES for dep in deps):
            raise AttestationError("DEPENDENCY_UNKNOWN", f"unknown dependency class in {deps!r}")
        if len(set(deps)) != len(deps) or deps != sorted(deps):
            raise AttestationError("DEPENDENCY_ORDER", "dependencies must be unique and sorted")
        if not OBJECT_DEPENDENCIES.issubset(deps):
            raise AttestationError(
                "OBJECT_DEPENDENCY_REQUIRED", "DEP_HEAD and DEP_TREE are required in v1"
            )
        if _sealing(info):
            return self
        expected = self.compute_digest()
        if self.content_hash != expected:
            raise AttestationError(
                "ATTESTATION_HASH_MISMATCH", "content_hash does not match the canonical content"
            )
        if self.attestation_id != short_id(ATTESTATION_ID_PREFIX, expected):
            raise AttestationError(
                "ATTESTATION_ID_MISMATCH", "attestation_id is not derived from content_hash"
            )
        return self

    def body(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude=set(_DIGEST_FIELDS))

    def compute_digest(self) -> str:
        return content_digest(self.body())

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


def seal_evidence_attestation(payload: Mapping[str, Any]) -> EvidenceAttestation:
    """Validate an attestation body and compute ``content_hash`` / ``attestation_id``."""
    draft = EvidenceAttestation.model_validate(dict(payload), context={_SEAL_CONTEXT_KEY: True})
    digest = draft.compute_digest()
    sealed = draft.model_copy(
        update={
            "content_hash": digest,
            "attestation_id": short_id(ATTESTATION_ID_PREFIX, digest),
        }
    )
    return EvidenceAttestation.model_validate(sealed.to_record())


def load_evidence_attestation(payload: Mapping[str, Any]) -> EvidenceAttestation:
    """Strict read: the payload must carry a matching ``content_hash``."""
    return EvidenceAttestation.model_validate(dict(payload))


__all__ = [
    "ATTESTATION_ID_PREFIX",
    "AUTHORITY_FIELD_NAMES",
    "DEPENDENCY_CLASSES",
    "EVIDENCE_ATTESTATION_SCHEMA",
    "EVIDENCE_ATTESTATION_SCHEMA_VERSION",
    "EVIDENCE_STAGES",
    "EVIDENCE_TYPES",
    "INDEPENDENT_STAGES",
    "OBJECT_DEPENDENCIES",
    "PRODUCER_KINDS",
    "RESULT_STATUSES",
    "STAGE_EVIDENCE_TYPES",
    "AttestationError",
    "AttestationResult",
    "EvidenceAttestation",
    "ObjectBinding",
    "Producer",
    "load_evidence_attestation",
    "seal_evidence_attestation",
]
