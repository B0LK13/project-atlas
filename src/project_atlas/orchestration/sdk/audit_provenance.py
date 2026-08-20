"""ORCH-INDEPENDENT-AUDIT-PROVENANCE-001 — fail-closed cloud audit authority.

Repository evidence files are data, never gate authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRole,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.result_plane import ResultEnvelope, result_plane_path
from project_atlas.orchestration.sdk.security_gates import BoundWorkerResult

ASSIGNMENT_NAME = "cloud-audit-assignment.json"
CONSUMED_NAME = "cloud-audit-consumed.json"
REPO_EVIDENCE_REL = (
    "docs/evidence/AS-ORCH-CONTINUATION-BROKER-001-d092-runtime-wiring-audit.json"
)
TRUSTED_MAIN = "7e797468a2eca37c959920912b1fa264df4be638"
CANONICAL_PR = 429


class CloudAuditAssignment(BaseModel):
    """Governor-minted independent audit assignment. Not a PASS grant."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: str = Field(min_length=1, max_length=160)
    package_id: str = PACKAGE_ID
    role: Literal["CLOUD_RUNTIME_AUDITOR"] = "CLOUD_RUNTIME_AUDITOR"
    dag_generation: int = Field(ge=0, le=1_000_000)
    canonical_pr: int = CANONICAL_PR
    candidate_head: str = Field(min_length=40, max_length=40)
    candidate_tree: str = Field(min_length=40, max_length=40)
    base_main: str = TRUSTED_MAIN
    worker_id: str = Field(min_length=1, max_length=160)
    run_id: str = Field(min_length=1, max_length=160)
    attempt: int = Field(ge=1, le=10_000)
    read_only: Literal[True] = True
    mutation_authorized: Literal[False] = False
    created_by_primary_governor: Literal[True] = True
    implementer_worker_id: str | None = None
    stale: bool = False


class CloudAuditDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    gate: Literal["PASS", "FAIL", "NOT_PASS"]
    reason: str
    consume_identity: str | None = None
    remediation_ready: bool = False
    gate_transition: bool = False


def assignment_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / ASSIGNMENT_NAME


def consumed_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / CONSUMED_NAME


def load_cloud_audit_assignment(root: Path) -> CloudAuditAssignment | None:
    path = assignment_path(root)
    if not path.is_file():
        return None
    try:
        return CloudAuditAssignment.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def persist_cloud_audit_assignment(root: Path, assignment: CloudAuditAssignment) -> Path:
    path = assignment_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(assignment.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_consumed_identities(root: Path) -> set[str]:
    path = consumed_path(root)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = data.get("identities") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return set()
    return {str(x) for x in ids}


def persist_consumed_identities(root: Path, identities: set[str]) -> Path:
    path = consumed_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"identities": sorted(identities)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def mint_cloud_audit_assignment(
    root: Path,
    *,
    assignment_id: str,
    dag_generation: int,
    candidate_head: str,
    candidate_tree: str,
    worker_id: str,
    run_id: str,
    attempt: int = 1,
    implementer_worker_id: str | None = None,
    base_main: str = TRUSTED_MAIN,
) -> CloudAuditAssignment:
    if implementer_worker_id and worker_id == implementer_worker_id:
        raise SdkRuntimeError(
            "auditor identity matches implementer",
            code="REJECT_INDEPENDENCE",
        )
    if worker_id.startswith("impl-") or "IMPLEMENTER" in worker_id:
        raise SdkRuntimeError(
            "auditor identity is implementer-shaped",
            code="REJECT_INDEPENDENCE",
        )
    assignment = CloudAuditAssignment(
        assignment_id=assignment_id,
        dag_generation=dag_generation,
        candidate_head=candidate_head,
        candidate_tree=candidate_tree,
        base_main=base_main,
        worker_id=worker_id,
        run_id=run_id,
        attempt=attempt,
        implementer_worker_id=implementer_worker_id,
    )
    persist_cloud_audit_assignment(root, assignment)
    return assignment


def invalidate_cloud_audit_assignment(root: Path) -> None:
    current = load_cloud_audit_assignment(root)
    if current is None:
        return
    persist_cloud_audit_assignment(root, current.model_copy(update={"stale": True}))


def rebind_cloud_audit_assignment(
    root: Path,
    *,
    worker_id: str,
    run_id: str,
) -> CloudAuditAssignment | None:
    """Bind governor assignment to the authentic launched auditor identity."""
    current = load_cloud_audit_assignment(root)
    if current is None or current.stale:
        return None
    if current.implementer_worker_id and worker_id == current.implementer_worker_id:
        raise SdkRuntimeError(
            "auditor identity matches implementer",
            code="REJECT_INDEPENDENCE",
        )
    updated = current.model_copy(update={"worker_id": worker_id, "run_id": run_id})
    persist_cloud_audit_assignment(root, updated)
    return updated


def consume_identity(assignment_id: str, run_id: str, result_digest: str) -> str:
    return f"{assignment_id}+{run_id}+{result_digest}"


def _wiring_all_pass(wiring: object) -> bool:
    if not isinstance(wiring, dict) or not wiring:
        return False
    for value in wiring.values():
        if value in (True, "PASS", "YES", "CLOSED"):
            continue
        return False
    return True


def evaluate_cloud_audit(
    *,
    assignment: CloudAuditAssignment | None,
    binding: BoundWorkerResult | None,
    payload: dict[str, Any] | None,
    live_head: str,
    live_tree: str | None,
    live_generation: int,
    already_consumed: frozenset[str],
    repo_json: dict[str, Any] | None = None,
    source: str | None = None,
) -> CloudAuditDecision:
    """Governor validation is authority. ``repo_json`` is ignored on purpose."""
    del repo_json
    if assignment is None:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="NO_ASSIGNMENT"
        )
    if assignment.stale:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="STALE_AUDIT")
    if assignment.canonical_pr != CANONICAL_PR or assignment.package_id != PACKAGE_ID:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="STALE_AUDIT"
        )
    if assignment.candidate_head != live_head:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="STALE_AUDIT")
    if live_tree and assignment.candidate_tree != live_tree:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="STALE_AUDIT")
    if assignment.dag_generation != live_generation:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="STALE_AUDIT")
    if binding is None or payload is None:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="NO_RESULT")
    if source not in {"CLOUD_AUDITOR", "CLOUD_RUNTIME_AUDITOR"}:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="REJECT_INDEPENDENCE"
        )
    if binding.role in {AgentRole.IMPLEMENTER, AgentRole.REMEDIATOR}:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="REJECT_INDEPENDENCE"
        )
    if binding.role != AgentRole.CLOUD_RUNTIME_AUDITOR:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="REJECT_INDEPENDENCE"
        )
    if (
        assignment.implementer_worker_id
        and binding.session_or_agent_id == assignment.implementer_worker_id
    ):
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="REJECT_INDEPENDENCE"
        )
    if binding.session_or_agent_id != assignment.worker_id:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="REJECT_INDEPENDENCE"
        )
    if binding.run_id != assignment.run_id:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="FOREIGN_RUN"
        )
    required = (
        assignment.assignment_id,
        binding.session_or_agent_id,
        binding.run_id,
        binding.result_digest,
        binding.candidate_head,
        binding.candidate_tree,
        payload.get("ASSIGNMENT_ID") or payload.get("assignment_id"),
    )
    if any(not item for item in required):
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="MALFORMED_AUDIT"
        )
    assigned = str(payload.get("ASSIGNMENT_ID") or payload.get("assignment_id") or "")
    if assigned != assignment.assignment_id:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="MALFORMED_AUDIT"
        )
    if binding.candidate_head != live_head:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="WRONG_HEAD")
    if live_tree and binding.candidate_tree != live_tree:
        return CloudAuditDecision(accepted=False, gate="NOT_PASS", reason="WRONG_TREE")
    if binding.dag_generation != live_generation:
        return CloudAuditDecision(
            accepted=False, gate="NOT_PASS", reason="STALE_GENERATION"
        )
    identity = consume_identity(
        assignment.assignment_id, binding.run_id, binding.result_digest
    )
    if identity in already_consumed:
        return CloudAuditDecision(
            accepted=False,
            gate="NOT_PASS",
            reason="REPLAY",
            consume_identity=identity,
        )
    open_count = payload.get("SIX_P1_RUNTIME_OPEN_COUNT", payload.get("six_p1_runtime_open_count"))
    audit_result = str(payload.get("AUDIT_RESULT") or payload.get("audit_result") or "")
    wiring = payload.get("WIRING_VERIFIED", payload.get("wiring_verified"))
    if audit_result == "FAIL":
        return CloudAuditDecision(
            accepted=True,
            gate="FAIL",
            reason="AUDIT_FAIL",
            consume_identity=identity,
            remediation_ready=True,
            gate_transition=True,
        )
    if not isinstance(open_count, int) or open_count > 0:
        return CloudAuditDecision(
            accepted=True,
            gate="FAIL",
            reason="OPEN_COUNT",
            consume_identity=identity,
            gate_transition=True,
        )
    if audit_result == "PASS" and open_count == 0 and _wiring_all_pass(wiring):
        return CloudAuditDecision(
            accepted=True,
            gate="PASS",
            reason="AUDIT_PASS",
            consume_identity=identity,
            gate_transition=True,
        )
    return CloudAuditDecision(
        accepted=False, gate="NOT_PASS", reason="INCOMPLETE_AUDIT"
    )


def _read_repo_evidence(root: Path) -> dict[str, Any] | None:
    """Load candidate file as data only. Never used to arm the gate."""
    path = root / REPO_EVIDENCE_REL
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def apply_cloud_audit_from_plane(
    root: Path,
    *,
    live_head: str,
    live_tree: str | None,
    live_generation: int,
) -> CloudAuditDecision:
    """Discover one unconsumed cloud-audit envelope and validate it."""
    assignment = load_cloud_audit_assignment(root)
    repo_json = _read_repo_evidence(root)
    consumed = load_consumed_identities(root)
    path = result_plane_path(root)
    if not path.is_file():
        return evaluate_cloud_audit(
            assignment=assignment,
            binding=None,
            payload=None,
            live_head=live_head,
            live_tree=live_tree,
            live_generation=live_generation,
            already_consumed=frozenset(consumed),
            repo_json=repo_json,
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            envelope = ResultEnvelope.model_validate_json(line)
        except ValueError:
            continue
        if envelope.source not in {"CLOUD_AUDITOR", "CLOUD_RUNTIME_AUDITOR"}:
            continue
        decision = evaluate_cloud_audit(
            assignment=assignment,
            binding=envelope.binding,
            payload=envelope.payload,
            live_head=live_head,
            live_tree=live_tree,
            live_generation=live_generation,
            already_consumed=frozenset(consumed),
            repo_json=repo_json,
            source=envelope.source,
        )
        if decision.accepted and decision.consume_identity:
            consumed.add(decision.consume_identity)
            persist_consumed_identities(root, consumed)
        return decision
    return evaluate_cloud_audit(
        assignment=assignment,
        binding=None,
        payload=None,
        live_head=live_head,
        live_tree=live_tree,
        live_generation=live_generation,
        already_consumed=frozenset(consumed),
        repo_json=repo_json,
    )


def refresh_live_audit_gate(
    root: Path,
    *,
    bound_head: str | None,
    bound_tree: str | None,
    dag_generation: int,
    current_pass: bool,
    current_consume_id: str | None,
    current_transitions: int,
) -> tuple[bool, bool, str | None, int, bool]:
    """Return (pass, fail, consume_id, transitions, remediation_ready).

    Persisted ``current_pass`` is not authority. Repo JSON is not authority.
    """
    if not bound_head:
        return False, False, None, current_transitions, False
    assignment = load_cloud_audit_assignment(root)
    if (
        current_pass
        and current_consume_id
        and assignment is not None
        and not assignment.stale
        and assignment.candidate_head == bound_head
        and assignment.candidate_tree == bound_tree
        and assignment.dag_generation == dag_generation
        and current_consume_id in load_consumed_identities(root)
    ):
        return True, False, current_consume_id, current_transitions, False
    decision = apply_cloud_audit_from_plane(
        root,
        live_head=bound_head,
        live_tree=bound_tree,
        live_generation=dag_generation,
    )
    if decision.gate == "PASS" and decision.consume_identity:
        transitions = current_transitions + (1 if decision.gate_transition else 0)
        return True, False, decision.consume_identity, transitions, False
    if decision.gate == "FAIL" and decision.consume_identity:
        transitions = current_transitions + (1 if decision.gate_transition else 0)
        return False, True, decision.consume_identity, transitions, decision.remediation_ready
    return False, False, current_consume_id, current_transitions, False
