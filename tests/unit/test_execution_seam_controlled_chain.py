"""Controlled seam-closure chain: render → load → run → identity in evidence.

ATLAS-EXECUTION-SEAM-CLOSURE-003 §5. Local fixture workers only.
Preserved e2e-proof failed runs are not overwritten by this suite.
REAL_LAUNCH_AUTHORIZED = NO. INDEPENDENT_REVIEW = NO.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from tests.unit.test_orchestration_program_supervisor import (
    _profile,
    _supervisor,
)
from tests.unit.test_taskcontract_preparation import _binding, _contract

from project_atlas.orchestration.origination.identity import origination_identity_from_parts
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramStopReason
from project_atlas.orchestration.program.store import load_state, read_events
from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    contract_digest,
)
from project_atlas.orchestration.taskcontract.render import (
    render_program,
    render_review_package,
)
from project_atlas.orchestration.taskcontract.validate import validate_contract


def _fixture_profile(
    *,
    profile_id: str,
    agent_id: str,
    capabilities: tuple[str, ...] = ("IMPLEMENT",),
) -> dict[str, Any]:
    body = _profile(
        profile_id=profile_id,
        agent_id=agent_id,
        capabilities=capabilities,
        target="SEAM-OUT.txt",
    )
    body["profile_id"] = profile_id
    return body


def _seam_contract(tmp_path: Path) -> tuple[TaskContract, Path, Path, str]:
    contract, _project, workspace = _contract(tmp_path)
    raw = contract.model_dump(mode="json")
    raw["mutation_paths"] = ["SEAM-OUT.txt"]
    raw["expected_output_paths"] = ["SEAM-OUT.txt"]
    raw["acceptance"] = [
        {
            "check_id": "behaviour",
            "kind": "FILE_EXISTS",
            "description": "SEAM-OUT.txt exists",
            "path": "SEAM-OUT.txt",
        },
        {
            "check_id": "content",
            "kind": "FILE_MATCHES",
            "description": "records attempt",
            "path": "SEAM-OUT.txt",
            "pattern": "attempt=",
        },
    ]
    raw["requirements"] = [
        {
            "requirement_id": "R1",
            "statement": "SEAM-OUT.txt exists with attempt marker",
            "verification": "AUTOMATED",
            "check_ids": ["behaviour", "content"],
            "review_note": "",
        }
    ]
    contract = TaskContract.model_validate(raw)
    oid = origination_identity_from_parts(
        "seam-proj",
        contract.source.source_path,
        contract.source.item_id,
        contract.source.item_digest,
        contract.scope,
        tuple(r.statement for r in contract.requirements),
    )
    return contract, workspace, tmp_path, oid


def test_controlled_chain_no_hand_translation_and_identity_in_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, workspace, root, oid = _seam_contract(tmp_path)
    binding = DeploymentBinding(
        binding_id="seam-binding",
        workspace_root=str(workspace),
        state_root=str(root / "state"),
        registry_root=str(root / "registry"),
        interpreter=sys.executable,
        profile_ref="implementer",
        agent_role="implementer",
        verifier_profile_ref="verifier",
    )
    (root / "state").mkdir(exist_ok=True)
    (root / "registry").mkdir(exist_ok=True)

    program = render_program(
        contract,
        binding,
        approved_by="seam-owner",
        approval_reference="tests/unit/test_execution_seam_controlled_chain.py",
        profile=_fixture_profile(
            profile_id="implementer", agent_id="seam-implementer"
        ),
        verifier_profile=_fixture_profile(
            profile_id="verifier",
            agent_id="seam-verifier",
            capabilities=("VERIFY",),
        ),
        origination_identity=oid,
    )
    # No hand edits of decision fields.
    task = program["program"]["tasks"][0]
    assert task["instruction"].startswith("#")
    assert task["acceptance"][0]["kind"] == "FILE_EXISTS"
    assert task["profile_ref"] == "implementer"
    assert task["verifier_profile_ref"] == "verifier"
    assert task["origination_identity"] == oid
    assert program["field_provenance"]["instruction"]["origin"] == "RENDER_DERIVED"
    assert program["field_provenance"]["acceptance"]["origin"] == "CONTRACT"
    assert program["field_provenance"]["profile_ref"]["origin"] == "BINDING"
    assert program["field_provenance"]["verifier_profile_ref"]["origin"] == "BINDING"

    # Supervisor-friendly limits (render emits contract limits only).
    # Implementer + verifier need two launches; leave headroom so a single
    # remediating attempt cannot trip LIMIT_REACHED on the happy path.
    program["program"]["limits"] = {
        **program["program"]["limits"],
        "max_cycles": 20,
        "idle_sleep_seconds": 0.0,
        "max_task_launches": 8,
        "max_attempts_per_task": 4,
    }
    program_path = root / "program.json"
    program_path.write_text(json.dumps(program, indent=2, sort_keys=True), encoding="utf-8")
    loaded = load_program(program_path)
    assert loaded.program.tasks[0].origination_identity == oid
    assert loaded.program.tasks[0].contract_digest == contract_digest(contract)

    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.setenv("ATLAS_FIXTURE_TARGET", "SEAM-OUT.txt")
    report = _supervisor(program_path, root).start()
    assert report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert report.complete is True

    state = load_state(root / "state")
    assert state is not None
    assert state.attempts, "expected durable attempts"
    for attempt in state.attempts.values():
        assert attempt.origination_identity == oid
        assert attempt.contract_digest == contract_digest(contract)
        assert attempt.source_item_digest == contract.source.item_digest

    events = read_events(root / "state")
    verified = [row for row in events if row.get("event") == "TASK_VERIFIED"]
    assert verified, "independent verifier must have run"
    assert verified[0]["implementer_agent_id"] != verified[0]["verifier_agent_id"]

    report_pkg = render_review_package(
        contract,
        binding,
        validate_contract(contract, binding=binding),
        program=program,
    )
    assert report_pkg["identity_chain"]["origination_identity"] == oid
    assert report_pkg["review_is_of"]["contract_digest"] == contract_digest(contract)
    (root / "review-package.json").write_text(
        json.dumps(report_pkg, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_negative_exit_zero_wrong_artifact_fails_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, workspace, root, oid = _seam_contract(tmp_path)
    binding = _binding(root, workspace)
    program = render_program(
        contract,
        binding,
        approved_by="seam-owner",
        approval_reference="negative-control",
        profile=_fixture_profile(
            profile_id="implementer", agent_id="seam-implementer"
        ),
        origination_identity=oid,
    )
    program["program"]["limits"] = {
        **program["program"]["limits"],
        "max_cycles": 12,
        "idle_sleep_seconds": 0.0,
        "max_attempts_per_task": 2,
    }
    program_path = root / "program-neg.json"
    program_path.write_text(json.dumps(program, indent=2, sort_keys=True), encoding="utf-8")

    # Exit 0, change nothing / wrong artifact → acceptance must fail.
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "claim-only")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)
    report = _supervisor(program_path, root).start()
    assert report.complete is False
    assert report.stop_reason is not ProgramStopReason.PROGRAM_COMPLETE
    state = load_state(root / "state")
    assert state is not None
    attempts = list(state.attempts.values())
    assert attempts
    assert any(a.acceptance_passed is False for a in attempts)
    # Identity still present on failed attempts (chain, not success-only).
    assert attempts[0].origination_identity == oid
