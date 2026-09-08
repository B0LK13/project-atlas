"""AT3-050 — Agent proof-of-work.

MODEL CLAIM OF COMPLETION != PROOF.
Evidence chain: TASK → IMPLEMENTATION → TESTS → CI → IV → ADV → INTEGRATION → POST-MERGE.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from atlas_contracts.attestation import (
    EvidenceAttestation,
    load_evidence_attestation,
)
from atlas_contracts.canonical import canonical_json
from atlas_contracts.execution_identity import (
    ExecutionIdentity,
    load_execution_identity,
)
from atlas_contracts.identity import safe_relative_component
from project_atlas.atlas3.contracts import (
    GENERATOR_ID,
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    read_json,
    require_vault,
    safe_project_id,
    write_json_atomic,
)

PACKAGE_ID: Final[str] = "AT3-050"
PROOF_STAGES: Final[tuple[str, ...]] = (
    "TASK",
    "IMPLEMENTATION",
    "TESTS",
    "CI",
    "INDEPENDENT_VERIFICATION",
    "ADV",
    "INTEGRATION",
    "POST_MERGE",
)
PROOF_V2_SCHEMA: Final[str] = "atlas3.agent-proof.v2"
PROOF_V2_PACKAGE_ID: Final[str] = "AT3-103"
PROOF_V2_RELATIVE: Final[Path] = OPS_RELATIVE / "proof" / "v2"
MAX_TASK_ID_LENGTH: Final[int] = 128
# v2 task ids are safe logical identifiers, not descriptive text: an ASCII
# identifier alphabet that every supported filesystem accepts, so Linux and
# Windows make the same decision before any filesystem access.
TASK_ID_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_TASK_ID_RE: Final[re.Pattern[str]] = re.compile(TASK_ID_PATTERN)


def evaluate_proof(
    vault: Any,
    task_id: str,
    *,
    project_id: str,
    evidence: dict[str, Any] | None = None,
    model_claims_complete: bool = False,
) -> dict[str, Any]:
    """Evaluate a proof chain. Missing stages stay UNKNOWN. Model claim never proves."""
    root = require_vault(vault)
    tid = task_id.strip()
    if not tid or "/" in tid or "\\" in tid or tid in {".", ".."}:
        raise Atlas3Error("UNSAFE_TASK_ID", f"unsafe task id: {task_id!r}")
    pid = safe_project_id(project_id)
    supplied = evidence or {}
    stages: dict[str, Any] = {}
    present = 0
    for name in PROOF_STAGES:
        raw = supplied.get(name)
        if isinstance(raw, dict) and raw.get("evidence_ref"):
            stages[name] = {
                "status": "PRESENT",
                "evidence_ref": str(raw["evidence_ref"]),
                "authority": "derived",
            }
            present += 1
        else:
            stages[name] = {
                "status": "UNKNOWN",
                "reason": "no independent evidence_ref",
                "authority": "none",
            }

    if present == len(PROOF_STAGES):
        chain_status = "PROVEN"
    elif present == 0:
        chain_status = "UNKNOWN"
    else:
        chain_status = "PARTIAL"

    if model_claims_complete and chain_status != "PROVEN":
        chain_status = "UNPROVEN_MODEL_CLAIM"

    report = {
        "schema": "atlas3.agent-proof.v1",
        "schema_version": 1,
        "package": PACKAGE_ID,
        "task_id": tid,
        "project_id": pid,
        "stages": stages,
        "present_count": present,
        "chain_status": chain_status,
        "model_claims_complete": model_claims_complete,
        "model_claim_is_proof": False,
        "merge_authorization": "NOT_GRANTED",
        "authority": "derived",
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "generated": {"by": GENERATOR_ID},
    }
    write_json_atomic(root / OPS_RELATIVE / "proof" / f"{tid}.json", report)
    return report


def _safe_task_id(task_id: object) -> str:
    """v2 task ids name a directory: a bounded ASCII identifier, then the shared
    path-component guard (reserved Windows names, trailing dot, ``..``).

    Stricter than v1's check on purpose; v1's own check is untouched. The value
    is never echoed in the error, because a task id may also be secret-shaped.
    """
    if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):
        raise Atlas3Error(
            "UNSAFE_TASK_ID",
            "task id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}",
        )
    try:
        return safe_relative_component(task_id, label="task id")
    except ValueError as exc:
        raise Atlas3Error("UNSAFE_TASK_ID", "task id is not a safe path component") from exc


def _assert_no_symlink_components(root: Path, relative: Path) -> None:
    """Refuse if any path component below ``root`` is a symlink (checked with
    ``lstat`` on the *unresolved* path, before any ``resolve()``), so a planted
    link at ``proof/v2``, at the task directory or at the locator cannot
    redirect a report inside or outside the vault."""
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise Atlas3Error("PROOF_LOCATOR_UNSAFE", f"proof path component {part!r} is a symlink")


def _load_identity(identity: ExecutionIdentity | Mapping[str, Any]) -> ExecutionIdentity:
    # An instance is re-validated from its record: a draft built in seal
    # context, a model_copy, or model_construct must not carry an unverified
    # digest into a report (ADV S2).
    if isinstance(identity, ExecutionIdentity):
        identity = identity.to_record()
    if not isinstance(identity, Mapping):
        raise Atlas3Error("EXECUTION_IDENTITY_MALFORMED", "identity must be a JSON object")
    try:
        return load_execution_identity(identity)
    except ValidationError as exc:
        code = _pydantic_code(exc, default="EXECUTION_IDENTITY_MALFORMED")
        raise Atlas3Error(code, _pydantic_detail(exc)) from exc


def _load_attestation(
    attestation: EvidenceAttestation | Mapping[str, Any],
) -> EvidenceAttestation:
    if isinstance(attestation, EvidenceAttestation):
        attestation = attestation.to_record()
    if not isinstance(attestation, Mapping):
        raise Atlas3Error("ATTESTATION_MALFORMED", "attestation must be a JSON object")
    try:
        return load_evidence_attestation(attestation)
    except ValidationError as exc:
        code = _pydantic_code(exc, default="ATTESTATION_MALFORMED")
        raise Atlas3Error(code, _pydantic_detail(exc)) from exc


def _pydantic_code(exc: ValidationError, *, default: str) -> str:
    """Surface a contract error code when the validator raised one; else default."""
    for error in exc.errors():
        message = str(error.get("msg", ""))
        marker = "Value error, "
        if message.startswith(marker):
            head = message[len(marker) :].split(":", 1)[0].strip()
            if head and head.replace("_", "").isalnum() and head.isupper():
                return head
    return default


def _pydantic_detail(exc: ValidationError) -> str:
    """Location/type only; never echo submitted values."""
    parts = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", ()))
        parts.append(f"{loc or '$'}: {error.get('type', 'invalid')}")
    return "; ".join(parts)


def _string_values(payload: object) -> list[str]:
    found: list[str] = []
    if isinstance(payload, str):
        found.append(payload)
    elif isinstance(payload, Mapping):
        for key, value in payload.items():
            found.append(str(key))
            found.extend(_string_values(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.extend(_string_values(item))
    return found


def _scan_for_secrets(payload: object) -> None:
    """Scan raw string values AND the canonical text (ADV S7: escaping defeats
    whitespace-adjacent patterns, so the raw values are scanned too)."""
    from project_atlas.secrets import scan_text

    names: set[str] = set()
    for text in [canonical_json(payload), *_string_values(payload)]:
        names.update(finding.pattern for finding in scan_text(text))
    if names:
        raise Atlas3Error(
            "PROOF_SECRET_FORBIDDEN",
            f"secret-shaped content in proof inputs: {', '.join(sorted(names))}",
        )


def evaluate_proof_v2(
    vault: Any,
    task_id: str,
    *,
    project_id: str,
    identity: ExecutionIdentity | Mapping[str, Any],
    attestations: Sequence[EvidenceAttestation | Mapping[str, Any]],
    model_claims_complete: bool = False,
) -> dict[str, Any]:
    """AT3-103 proof v2: typed, digest-verified, same-object-bound evidence.

    Presence of an ``evidence_ref`` proves nothing here. A stage is PRESENT only
    when at least one valid attestation for that stage carries ``PASS``, and
    every attestation is bound to the identity's candidate object. Any mismatch
    fails closed before anything is written. v1 (``evaluate_proof``) is untouched.

    Storage: ``generated/ops/atlas3/proof/v2/<task_id>/<digest16>.json`` — a
    namespace separate from v1's ``proof/<task_id>.json`` so the two versions
    cannot collide. ``<digest16>`` is a locator only; the full
    ``identity_digest`` inside the file is the identity, and a locator that
    already holds a different full digest fails closed instead of overwriting.
    Every path component under the vault is checked with ``lstat`` before any
    resolution: a symlink at ``proof/v2``, at the task directory or at the
    locator is refused (``PROOF_LOCATOR_UNSAFE``), never followed.
    """
    root = require_vault(vault)
    tid = _safe_task_id(task_id)
    pid = safe_project_id(project_id)
    if isinstance(attestations, (str, bytes, Mapping)) or not isinstance(attestations, Sequence):
        raise Atlas3Error("ATTESTATIONS_INVALID", "attestations must be a list of attestations")
    ident = _load_identity(identity)
    if ident.project_id != pid:
        raise Atlas3Error(
            "IDENTITY_PROJECT_MISMATCH", "execution identity belongs to another project"
        )
    candidate = ident.candidate_object()
    if candidate is None:
        raise Atlas3Error(
            "CANDIDATE_OBJECT_REQUIRED", "proof v2 requires candidate_head and candidate_tree"
        )
    head, tree = candidate
    _scan_for_secrets({"task_id": tid})
    _scan_for_secrets(ident.to_record())

    loaded: list[EvidenceAttestation] = []
    seen_ids: set[str] = set()
    for raw in attestations:
        att = _load_attestation(raw)
        if att.project_id != pid:
            raise Atlas3Error(
                "ATTESTATION_PROJECT_MISMATCH",
                f"attestation {att.attestation_id} belongs to another project",
            )
        if att.execution_identity_digest != ident.identity_digest:
            raise Atlas3Error(
                "ATTESTATION_IDENTITY_MISMATCH",
                f"attestation {att.attestation_id} is bound to another execution identity",
            )
        if att.object_binding.head != head or att.object_binding.tree != tree:
            raise Atlas3Error(
                "PROOF_OBJECT_MISMATCH",
                f"attestation {att.attestation_id} is bound to another candidate object",
            )
        if att.attestation_id in seen_ids:
            raise Atlas3Error(
                "ATTESTATION_DUPLICATE", f"attestation {att.attestation_id} supplied twice"
            )
        seen_ids.add(att.attestation_id)
        _scan_for_secrets(att.to_record())
        loaded.append(att)

    stages: dict[str, Any] = {}
    present = 0
    failed = 0
    for name in PROOF_STAGES:
        matching = [att for att in loaded if att.stage == name]
        passes = [att for att in matching if att.result.status == "PASS"]
        fails = [att for att in matching if att.result.status == "FAIL"]
        entry: dict[str, Any] = {
            "attestation_ids": [att.attestation_id for att in matching],
            "evidence_types": sorted({att.evidence_type for att in matching}),
            "authority": "derived" if matching else "none",
        }
        if fails:
            entry["status"] = "FAILED"
            entry["reason"] = "an attestation for this stage reports FAIL"
            failed += 1
        elif passes:
            entry["status"] = "PRESENT"
            present += 1
        elif matching:
            entry["status"] = "UNKNOWN"
            entry["reason"] = "attestations present but none reports PASS"
        else:
            entry["status"] = "UNKNOWN"
            entry["reason"] = "no valid attestation"
        stages[name] = entry

    if failed:
        chain_status = "FAILED"
    elif present == len(PROOF_STAGES):
        chain_status = "PROVEN"
    elif present == 0:
        chain_status = "UNKNOWN"
    else:
        chain_status = "PARTIAL"
    if model_claims_complete and chain_status != "PROVEN":
        chain_status = "UNPROVEN_MODEL_CLAIM"

    report: dict[str, Any] = {
        "schema": PROOF_V2_SCHEMA,
        "schema_version": 2,
        "proof_version": 2,
        "package": PROOF_V2_PACKAGE_ID,
        "task_id": tid,
        "project_id": pid,
        "identity_digest": ident.identity_digest,
        "run_id": ident.run_id,
        "object": {"head": head, "tree": tree},
        "bindings": ident.bindings(),
        "stages": stages,
        "present_count": present,
        "failed_count": failed,
        "attestation_count": len(loaded),
        "attestations": [
            {
                "attestation_id": att.attestation_id,
                "stage": att.stage,
                "evidence_type": att.evidence_type,
                "producer": att.producer.kind,
                "status": att.result.status,
                "content_hash": att.content_hash,
                "dependencies": list(att.dependencies),
            }
            for att in loaded
        ],
        "chain_status": chain_status,
        "model_claims_complete": model_claims_complete,
        "model_claim_is_proof": False,
        "attestation_is_owner_authority": False,
        "independence_declared_only": True,
        "independence_verified": False,
        "merge_authorization": "NOT_GRANTED",
        "live_observation_wired": False,
        "authority": "derived",
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
        "generated": {"by": GENERATOR_ID},
    }
    locator = PROOF_V2_RELATIVE / tid / f"{ident.identity_digest[:16]}.json"
    _assert_no_symlink_components(root, locator)
    task_dir = root / PROOF_V2_RELATIVE / tid
    if task_dir.exists() and not task_dir.is_dir():
        raise Atlas3Error("PROOF_LOCATOR_UNSAFE", "proof task path is not a directory")
    target = root / locator
    if target.exists() and not target.is_file():
        raise Atlas3Error("PROOF_LOCATOR_UNSAFE", "proof locator is not a regular file")
    # Defence in depth after the symlink walk: the resolved locator must still
    # sit under the resolved proof root.
    if not target.resolve().is_relative_to((root / PROOF_V2_RELATIVE).resolve()):
        raise Atlas3Error("UNSAFE_TASK_ID", "proof path escaped the proof root")
    if target.is_file():
        existing = read_json(target)
        if existing is None or existing.get("identity_digest") != ident.identity_digest:
            raise Atlas3Error(
                "PROOF_LOCATOR_COLLISION",
                "proof locator already holds a different or unreadable proof; not overwritten",
            )
    write_json_atomic(target, report)
    return report
