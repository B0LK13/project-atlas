"""AS-ORCH-SPECULATIVE-CERTIFICATION-001 — durable candidate-seal + exact-pin barrier.

Encodes the successful D-121/D-122 protocol as a first-class orchestration capability:

* candidate seal binds HEAD/TREE/BASE_MAIN/generation
* parallel lane receipts must bind the sealed pins
* tip drift cancels certification (no silent repair)
* exact-pin evidence promotion is explicit and fail-closed
* merge authorization is never implied

Evidence only. Not merge authority.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.sdk.models import SdkRuntimeError

SPECULATIVE_PACKAGE_ID: Final[Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"]] = (
    "AS-ORCH-SPECULATIVE-CERTIFICATION-001"
)
SEAL_DIR_NAME: Final[str] = "speculative-cert"
SEAL_FILE_NAME: Final[str] = "candidate-seal.json"
BARRIER_FILE_NAME: Final[str] = "certification-barrier.json"
PROMOTED_FILE_NAME: Final[str] = "exact-pin-evidence-promoted.json"

REQUIRED_LANES: Final[tuple[str, ...]] = (
    "CI",
    "IV",
    "ADV",
    "CLOUD_RUNTIME_AUDIT",
    "D116_D119_D121",
    "PRIOR_P1_REGRESSION",
    "AUTHENTIC_CLOUD_SMOKE_V2",
    "FINAL_LINEAGE_AUDIT",
)

_FULL_SHA_LEN: Final[int] = 40


def _require_full_sha(value: str, *, field: str) -> str:
    text = value.strip().lower()
    if len(text) != _FULL_SHA_LEN or any(c not in "0123456789abcdef" for c in text):
        raise SdkRuntimeError(
            f"{field} must be a full 40-char lowercase hex SHA",
            code="SPECULATIVE_CERT_PIN_INVALID",
        )
    return text


class CertificationState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    CANDIDATE_SEALED = "CANDIDATE_SEALED"
    BARRIER_OPEN = "BARRIER_OPEN"
    CERTIFIED = "CERTIFIED"
    CANCELLED_TIP_DRIFT = "CANCELLED_TIP_DRIFT"
    BARRIER_FAILED = "BARRIER_FAILED"


class LaneResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


class CandidateSeal(BaseModel):
    """Frozen candidate object. Observed thereafter; not improved in-generation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = SPECULATIVE_PACKAGE_ID
    generation: int = Field(ge=1, le=1_000_000)
    head: str
    tree: str
    base_main: str
    sealed_at_utc: str
    certification_frozen: Literal[False] = False
    merge_authorization: Literal["NOT_GRANTED"] = "NOT_GRANTED"

    @field_validator("head", "tree", "base_main")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _require_full_sha(value, field="pin")


class LaneReceipt(BaseModel):
    """One parallel certification lane bound to the sealed pins."""

    model_config = ConfigDict(extra="forbid")

    lane: str
    result: LaneResult
    head: str
    tree: str
    new_p0: int = Field(default=0, ge=0)
    new_p1: int = Field(default=0, ge=0)
    previous_p1_reopened: int = Field(default=0, ge=0)

    @field_validator("head", "tree")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _require_full_sha(value, field="lane_pin")


class CertificationBarrier(BaseModel):
    """Aggregate exact-pin barrier over required lanes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = SPECULATIVE_PACKAGE_ID
    generation: int = Field(ge=1, le=1_000_000)
    sealed_head: str
    sealed_tree: str
    sealed_base_main: str
    state: CertificationState
    lanes: dict[str, LaneReceipt]
    new_p0: int = Field(default=0, ge=0)
    new_p1: int = Field(default=0, ge=0)
    previous_p1_reopened: int = Field(default=0, ge=0)
    exact_pin_evidence_promoted: bool = False
    certification_frozen: bool = False
    merge_authorization: Literal["NOT_GRANTED"] = "NOT_GRANTED"
    updated_at_utc: str

    @model_validator(mode="after")
    def _lane_keys(self) -> CertificationBarrier:
        missing = [name for name in REQUIRED_LANES if name not in self.lanes]
        if missing:
            raise SdkRuntimeError(
                f"barrier missing required lanes: {missing}",
                code="SPECULATIVE_CERT_LANE_MISSING",
            )
        return self


def speculative_cert_dir(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime" / SEAL_DIR_NAME


def seal_candidate(
    root: Path,
    *,
    generation: int,
    head: str,
    tree: str,
    base_main: str,
) -> CandidateSeal:
    """Seal a candidate tip. Does not grant merge authority."""
    seal = CandidateSeal(
        generation=generation,
        head=_require_full_sha(head, field="head"),
        tree=_require_full_sha(tree, field="tree"),
        base_main=_require_full_sha(base_main, field="base_main"),
        sealed_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    path = speculative_cert_dir(root)
    path.mkdir(parents=True, exist_ok=True)
    (path / SEAL_FILE_NAME).write_text(
        json.dumps(seal.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pending = {
        name: LaneReceipt(
            lane=name,
            result=LaneResult.PENDING,
            head=seal.head,
            tree=seal.tree,
        )
        for name in REQUIRED_LANES
    }
    barrier = CertificationBarrier(
        generation=seal.generation,
        sealed_head=seal.head,
        sealed_tree=seal.tree,
        sealed_base_main=seal.base_main,
        state=CertificationState.CANDIDATE_SEALED,
        lanes=pending,
        updated_at_utc=seal.sealed_at_utc,
    )
    _persist_barrier(root, barrier)
    return seal


def load_candidate_seal(root: Path) -> CandidateSeal:
    path = speculative_cert_dir(root) / SEAL_FILE_NAME
    if not path.is_file():
        raise SdkRuntimeError("candidate seal missing", code="SPECULATIVE_CERT_SEAL_MISSING")
    return CandidateSeal.model_validate_json(path.read_text(encoding="utf-8"))


def load_barrier(root: Path) -> CertificationBarrier:
    path = speculative_cert_dir(root) / BARRIER_FILE_NAME
    if not path.is_file():
        raise SdkRuntimeError("barrier missing", code="SPECULATIVE_CERT_BARRIER_MISSING")
    return CertificationBarrier.model_validate_json(path.read_text(encoding="utf-8"))


def _persist_barrier(root: Path, barrier: CertificationBarrier) -> None:
    path = speculative_cert_dir(root)
    path.mkdir(parents=True, exist_ok=True)
    (path / BARRIER_FILE_NAME).write_text(
        json.dumps(barrier.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def observe_live_pins(
    *,
    live_head: str,
    live_tree: str,
    live_main: str,
    seal: CandidateSeal,
) -> tuple[bool, bool, bool]:
    """Return (head_match, tree_match, target_moved)."""
    head_match = _require_full_sha(live_head, field="live_head") == seal.head
    tree_match = _require_full_sha(live_tree, field="live_tree") == seal.tree
    target_moved = _require_full_sha(live_main, field="live_main") != seal.base_main
    return head_match, tree_match, target_moved


def cancel_for_tip_drift(root: Path, *, live_head: str, live_tree: str) -> CertificationBarrier:
    """Cancel certification when the sealed tip moved. No repair in-generation."""
    seal = load_candidate_seal(root)
    barrier = load_barrier(root)
    _ = (_require_full_sha(live_head, field="live_head"), _require_full_sha(live_tree, field="live_tree"))
    updated = barrier.model_copy(
        update={
            "state": CertificationState.CANCELLED_TIP_DRIFT,
            "certification_frozen": False,
            "exact_pin_evidence_promoted": False,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    _persist_barrier(root, updated)
    # Keep seal bytes for audit; state machine refuses promotion after cancel.
    _ = seal
    return updated


def record_lane_result(root: Path, receipt: LaneReceipt) -> CertificationBarrier:
    """Record a lane result. Rejects pin mismatch vs sealed candidate."""
    seal = load_candidate_seal(root)
    barrier = load_barrier(root)
    if barrier.state == CertificationState.CANCELLED_TIP_DRIFT:
        raise SdkRuntimeError(
            "generation cancelled for tip drift",
            code="SPECULATIVE_CERT_CANCELLED",
        )
    if receipt.lane not in REQUIRED_LANES:
        raise SdkRuntimeError(
            f"unknown lane {receipt.lane}",
            code="SPECULATIVE_CERT_LANE_UNKNOWN",
        )
    if receipt.head != seal.head or receipt.tree != seal.tree:
        raise SdkRuntimeError(
            "lane receipt pin does not bind sealed candidate",
            code="SPECULATIVE_CERT_PIN_MISMATCH",
        )
    lanes = dict(barrier.lanes)
    lanes[receipt.lane] = receipt
    new_p0 = sum(item.new_p0 for item in lanes.values())
    new_p1 = sum(item.new_p1 for item in lanes.values())
    prev = sum(item.previous_p1_reopened for item in lanes.values())
    updated = barrier.model_copy(
        update={
            "lanes": lanes,
            "new_p0": new_p0,
            "new_p1": new_p1,
            "previous_p1_reopened": prev,
            "state": CertificationState.BARRIER_OPEN,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    _persist_barrier(root, updated)
    return updated


def evaluate_barrier(root: Path) -> CertificationBarrier:
    """Evaluate whether all required lanes PASS on exact sealed pins."""
    barrier = load_barrier(root)
    if barrier.state == CertificationState.CANCELLED_TIP_DRIFT:
        return barrier
    pending = [
        name
        for name, receipt in barrier.lanes.items()
        if receipt.result == LaneResult.PENDING
    ]
    failed = [
        name
        for name, receipt in barrier.lanes.items()
        if receipt.result == LaneResult.FAIL
        or receipt.head != barrier.sealed_head
        or receipt.tree != barrier.sealed_tree
    ]
    if pending:
        return barrier
    if failed or barrier.new_p0 or barrier.new_p1 or barrier.previous_p1_reopened:
        updated = barrier.model_copy(
            update={
                "state": CertificationState.BARRIER_FAILED,
                "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
        _persist_barrier(root, updated)
        return updated
    updated = barrier.model_copy(
        update={
            "state": CertificationState.CERTIFIED,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    _persist_barrier(root, updated)
    return updated


def promote_exact_pin_evidence(
    root: Path,
    *,
    live_head: str,
    live_tree: str,
    live_main: str,
) -> CertificationBarrier:
    """Promote exact-pin evidence only while tip/main remain sealed and barrier CERTIFIED."""
    seal = load_candidate_seal(root)
    barrier = evaluate_barrier(root)
    head_match, tree_match, target_moved = observe_live_pins(
        live_head=live_head,
        live_tree=live_tree,
        live_main=live_main,
        seal=seal,
    )
    if not head_match or not tree_match:
        return cancel_for_tip_drift(root, live_head=live_head, live_tree=live_tree)
    if target_moved:
        raise SdkRuntimeError(
            "target main moved; merge authorization remains NOT_GRANTED",
            code="SPECULATIVE_CERT_TARGET_MOVED",
        )
    if barrier.state != CertificationState.CERTIFIED:
        raise SdkRuntimeError(
            "barrier not CERTIFIED; refuse exact-pin promotion",
            code="SPECULATIVE_CERT_NOT_CERTIFIED",
        )
    promoted = barrier.model_copy(
        update={
            "exact_pin_evidence_promoted": True,
            "certification_frozen": True,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    _persist_barrier(root, promoted)
    path = speculative_cert_dir(root) / PROMOTED_FILE_NAME
    path.write_text(
        json.dumps(
            {
                "package_id": SPECULATIVE_PACKAGE_ID,
                "generation": seal.generation,
                "head": seal.head,
                "tree": seal.tree,
                "base_main": seal.base_main,
                "exact_pin_evidence_promoted": True,
                "certification_frozen": True,
                "merge_authorization": "NOT_GRANTED",
                "promoted_at_utc": promoted.updated_at_utc,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return promoted
