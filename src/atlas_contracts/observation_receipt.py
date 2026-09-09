"""ULT-01b-1 — Observation receipt, v1.

A content-addressed record of *how* each dimension of an ``ExecutionIdentity``
was observed — or why it stayed ``UNKNOWN``. The sealed identity is embedded
verbatim and re-validated on every strict load, so a receipt cannot carry an
identity whose digest does not verify, and the receipt's own ``content_hash``
binds the embedded identity, the observer, and every per-dimension method
and reason code.

Honesty rules made structural:

- the receipt carries **no timestamp** — "when" is answered by *which exact
  object* was observed (``identity.source.candidate_*``); a receipt on disk
  is a record of a past observation, never a statement about the present
  (``observed_is_current`` is a constant ``False``: ``OBSERVED != CURRENT``);
- every dimension's ``status`` must agree with the embedded identity's
  ``OBSERVED | UNKNOWN`` status for that block (``DIMENSION_STATUS_MISMATCH``),
  so a receipt cannot claim more observation than the identity carries;
- an ``UNKNOWN`` dimension must name a reason code; an ``OBSERVED`` one must
  name its method and must not carry a reason (``UNKNOWN != FAILURE``: the
  reason is a classification, not an error);
- the observer is a ``tool``; a ``model`` or ``agent`` observer is refused
  (``MODEL_OUTPUT != OBSERVATION``);
- ``method_refs`` are short ASCII command *references*, never executed
  strings, and may not contain URLs, so a remote URL (which may embed a
  token) can never be persisted here;
- no authority field exists and none can be added (``extra="forbid"``):
  ``OBSERVATION != AUTHORITY``.

Like the identity, this module only defines and verifies the contract. The
observer that produces receipts lives in ``project_atlas.execution_observation``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationInfo,
    model_validator,
)

from atlas_contracts.attestation import VERSION_PATTERN
from atlas_contracts.canonical import content_digest, short_id
from atlas_contracts.execution_identity import ExecutionIdentity
from atlas_contracts.identity import safe_relative_component
from atlas_contracts.versions import HASH_PATTERN, ID_PATTERN

OBSERVATION_RECEIPT_SCHEMA: Final[str] = "atlas.observation-receipt.v1"
OBSERVATION_ID_PREFIX: Final[str] = "obs"
REASON_CODE_PATTERN: Final[str] = r"^[A-Z][A-Z0-9_]{2,63}$"
METHOD_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$"
METHOD_REF_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9 ._+/^{}=-]{0,127}$"
GIT_REF_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$"
REMOTE_NAME_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"

DIMENSIONS: Final[tuple[str, ...]] = (
    "source",
    "environment",
    "toolchain",
    "agent",
    "context",
    "capabilities",
)

_SEAL_CONTEXT_KEY: Final[str] = "atlas_contracts.seal_receipt"
_DIGEST_FIELDS: Final[frozenset[str]] = frozenset({"content_hash", "observation_id"})


class ObservationReceiptError(ValueError):
    """Fail-closed receipt error with a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _sealing(info: ValidationInfo) -> bool:
    context = info.context
    return bool(context and context.get(_SEAL_CONTEXT_KEY) is True)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class DimensionObservation(_Contract):
    """How one identity block was (not) observed."""

    status: Literal["OBSERVED", "UNKNOWN"]
    method: str | None = Field(default=None, pattern=METHOD_PATTERN)
    method_refs: tuple[str, ...] = ()
    reason: str | None = Field(default=None, pattern=REASON_CODE_PATTERN)

    @model_validator(mode="after")
    def _consistent(self) -> DimensionObservation:
        for ref in self.method_refs:
            if not _valid_method_ref(ref):
                raise ObservationReceiptError(
                    "METHOD_REF_INVALID", "method refs are short ASCII references, never URLs"
                )
        if self.status == "OBSERVED":
            if self.method is None:
                raise ObservationReceiptError(
                    "OBSERVATION_METHOD_REQUIRED", "an OBSERVED dimension must name its method"
                )
            if self.reason is not None:
                raise ObservationReceiptError(
                    "OBSERVED_WITH_REASON", "an OBSERVED dimension carries no reason code"
                )
        else:
            if self.reason is None:
                raise ObservationReceiptError(
                    "UNKNOWN_REASON_REQUIRED", "an UNKNOWN dimension must name a reason code"
                )
        return self


def _valid_method_ref(ref: str) -> bool:
    import re

    return bool(re.fullmatch(METHOD_REF_PATTERN, ref)) and "://" not in ref and "@" not in ref


class GitDimension(DimensionObservation):
    base_ref: str | None = Field(default=None, pattern=GIT_REF_PATTERN)
    remote_name: str | None = Field(default=None, pattern=REMOTE_NAME_PATTERN)
    worktree_clean: StrictBool | None = None
    shallow: StrictBool | None = None
    git_version: str | None = Field(default=None, pattern=VERSION_PATTERN)
    git_executable_path_digest: str | None = Field(default=None, pattern=HASH_PATTERN)

    @model_validator(mode="after")
    def _git_consistent(self) -> GitDimension:
        if self.base_ref is not None and ".." in self.base_ref:
            raise ObservationReceiptError("BASE_REF_INVALID", "base ref must be a plain ref name")
        incomplete = (
            self.base_ref is None or self.remote_name is None or self.worktree_clean is not True
        )
        if self.status == "OBSERVED" and incomplete:
            raise ObservationReceiptError(
                "GIT_OBSERVATION_INCOMPLETE",
                "an OBSERVED git dimension records base_ref, remote_name and a clean worktree",
            )
        return self


class EnvironmentDimension(DimensionObservation):
    arch_raw: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


class ToolchainDimension(DimensionObservation):
    declared: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _sets(self) -> ToolchainDimension:
        import re

        for group in (self.declared, self.absent):
            if any(not re.fullmatch(ID_PATTERN, name) or len(name) > 128 for name in group):
                raise ObservationReceiptError("TOOL_NAME_INVALID", "tool names are identifiers")
            if list(group) != sorted(set(group)):
                raise ObservationReceiptError("TOOL_ORDER", "tool sets must be unique and sorted")
        if not set(self.absent).issubset(self.declared):
            raise ObservationReceiptError(
                "TOOL_ABSENT_NOT_DECLARED", "absent tools must be declared"
            )
        return self


class ObservedDimensions(_Contract):
    source: GitDimension
    environment: EnvironmentDimension
    toolchain: ToolchainDimension
    agent: DimensionObservation
    context: DimensionObservation
    capabilities: DimensionObservation


class Observer(_Contract):
    kind: Literal["tool"]
    name: str = Field(pattern=ID_PATTERN, max_length=128)
    version: str = Field(pattern=VERSION_PATTERN)
    version_status: Literal["OBSERVED", "UNKNOWN"]

    @model_validator(mode="after")
    def _version_consistent(self) -> Observer:
        if self.version_status == "UNKNOWN" and self.version != "UNKNOWN":
            raise ObservationReceiptError(
                "OBSERVER_VERSION_UNKNOWN_WITH_VALUE",
                "an UNKNOWN observer version is the token UNKNOWN",
            )
        if self.version_status == "OBSERVED" and self.version == "UNKNOWN":
            raise ObservationReceiptError(
                "OBSERVER_VERSION_INCOMPLETE", "an OBSERVED observer version carries a value"
            )
        return self


class ObservationReceipt(_Contract):
    """Content-addressed record of one live observation. ``content_hash`` self-verifies."""

    schema_id: Literal["atlas.observation-receipt.v1"] = Field(
        default="atlas.observation-receipt.v1", alias="schema"
    )
    schema_version: StrictInt = Field(default=1, ge=1, le=1)
    project_id: str = Field(min_length=1, max_length=128)
    identity: ExecutionIdentity
    identity_digest: str = Field(pattern=HASH_PATTERN)
    observer: Observer
    observed: ObservedDimensions
    observed_is_current: StrictBool = False
    authority: Literal["derived"] = "derived"
    merge_authorization: Literal["NOT_GRANTED"] = "NOT_GRANTED"
    content_hash: str = Field(pattern=HASH_PATTERN)
    observation_id: str = Field(pattern=r"^obs-[0-9a-f]{16}$")

    @model_validator(mode="before")
    @classmethod
    def _seal_placeholders(cls, data: Any, info: ValidationInfo) -> Any:
        if not _sealing(info) or not isinstance(data, Mapping):
            return data
        if any(key in data for key in _DIGEST_FIELDS):
            raise ObservationReceiptError(
                "DIGEST_SUPPLIED_ON_SEAL", "content_hash/observation_id are computed, not supplied"
            )
        placeholder = "0" * 64
        return {
            **data,
            "content_hash": placeholder,
            "observation_id": short_id(OBSERVATION_ID_PREFIX, placeholder),
        }

    @model_validator(mode="after")
    def _verify(self, info: ValidationInfo) -> ObservationReceipt:
        if self.observed_is_current is not False:
            raise ObservationReceiptError(
                "OBSERVED_IS_NOT_CURRENT", "a receipt is a record of a past observation"
            )
        try:
            safe_relative_component(self.project_id, label="project id")
        except ValueError as exc:
            raise ObservationReceiptError("UNSAFE_PROJECT_ID", str(exc)) from exc
        if self.project_id != self.identity.project_id:
            raise ObservationReceiptError(
                "RECEIPT_PROJECT_MISMATCH", "receipt and identity belong to different projects"
            )
        if self.identity_digest != self.identity.identity_digest:
            raise ObservationReceiptError(
                "RECEIPT_IDENTITY_MISMATCH", "identity_digest does not match the embedded identity"
            )
        bindings = self.identity.bindings()
        expected = {
            "source": bindings["object_bound"],
            "environment": bindings["environment_bound"],
            "toolchain": bindings["toolchain_bound"],
            "agent": bindings["agent_bound"],
            "context": bindings["context_bound"],
            "capabilities": bindings["capabilities_bound"],
        }
        for name in DIMENSIONS:
            dimension: DimensionObservation = getattr(self.observed, name)
            observed = dimension.status == "OBSERVED"
            if observed != expected[name]:
                raise ObservationReceiptError(
                    "DIMENSION_STATUS_MISMATCH",
                    f"dimension {name} claims {dimension.status} but the identity block disagrees",
                )
        if _sealing(info):
            return self
        digest = self.compute_digest()
        if self.content_hash != digest:
            raise ObservationReceiptError(
                "RECEIPT_HASH_MISMATCH", "content_hash does not match the canonical content"
            )
        if self.observation_id != short_id(OBSERVATION_ID_PREFIX, digest):
            raise ObservationReceiptError(
                "OBSERVATION_ID_MISMATCH", "observation_id is not derived from content_hash"
            )
        return self

    def body(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json", by_alias=True, exclude=set(_DIGEST_FIELDS), warnings=False
        )

    def compute_digest(self) -> str:
        return content_digest(self.body())

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, warnings=False)


def seal_observation_receipt(payload: Mapping[str, Any]) -> ObservationReceipt:
    """Validate a receipt body and compute ``content_hash`` / ``observation_id``.

    The embedded identity is validated strictly (its own digest must verify);
    only the receipt's digest fields are computed here.
    """
    draft = ObservationReceipt.model_validate(dict(payload), context={_SEAL_CONTEXT_KEY: True})
    digest = draft.compute_digest()
    sealed = draft.model_copy(
        update={
            "content_hash": digest,
            "observation_id": short_id(OBSERVATION_ID_PREFIX, digest),
        }
    )
    return ObservationReceipt.model_validate(sealed.to_record())


def load_observation_receipt(payload: Mapping[str, Any]) -> ObservationReceipt:
    """Strict read: the payload must carry a matching ``content_hash`` and a verifying identity."""
    return ObservationReceipt.model_validate(dict(payload))


__all__ = [
    "DIMENSIONS",
    "GIT_REF_PATTERN",
    "METHOD_PATTERN",
    "METHOD_REF_PATTERN",
    "OBSERVATION_ID_PREFIX",
    "OBSERVATION_RECEIPT_SCHEMA",
    "REASON_CODE_PATTERN",
    "REMOTE_NAME_PATTERN",
    "DimensionObservation",
    "EnvironmentDimension",
    "GitDimension",
    "ObservationReceipt",
    "ObservationReceiptError",
    "ObservedDimensions",
    "Observer",
    "ToolchainDimension",
    "load_observation_receipt",
    "seal_observation_receipt",
]
