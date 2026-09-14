"""AS-EXECUTION-SEAM-CLOSURE-003 — render seam, identity chain, incompleteness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from tests.unit.test_taskcontract_preparation import PROFILE, _binding, _contract

from project_atlas.orchestration.origination.identity import origination_identity_from_parts
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramTask
from project_atlas.orchestration.program.store import AttemptRecord
from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    TaskContractError,
    VerificationMode,
    binding_digest,
    contract_digest,
)
from project_atlas.orchestration.taskcontract.render import (
    assert_machine_acceptance_renderable,
    render_program,
)


def test_decision_fields_have_visible_provenance(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    oid = origination_identity_from_parts(
        "proj",
        "docs/backlog.md",
        contract.source.item_id,
        contract.source.item_digest,
        contract.scope,
        tuple(r.statement for r in contract.requirements),
    )
    program = render_program(
        contract,
        binding,
        approved_by="owner",
        approval_reference="docs/backlog.md#TC-001",
        profile=PROFILE,
        origination_identity=oid,
    )
    prov = program["field_provenance"]
    assert prov["instruction"]["origin"] == "RENDER_DERIVED"
    assert prov["acceptance"]["origin"] == "CONTRACT"
    assert prov["profile_ref"]["origin"] == "BINDING"
    assert prov["profile_ref"]["value"] == binding.profile_ref
    assert prov["verifier_profile_ref"]["origin"] == "MISSING"
    assert program["program"]["tasks"][0]["origination_identity"] == oid
    assert program["program"]["tasks"][0]["contract_digest"] == contract_digest(contract)
    assert program["program"]["tasks"][0]["source_item_digest"] == contract.source.item_digest
    # Loader accepts the rendered program without hand-editing decision fields.
    path = tmp_path / "program.json"
    path.write_text(json.dumps(program), encoding="utf-8")
    loaded = load_program(path)
    task = loaded.program.tasks[0]
    assert task.instruction == program["program"]["tasks"][0]["instruction"]
    assert task.profile_ref == binding.profile_ref
    assert task.origination_identity == oid
    assert task.contract_digest == contract_digest(contract)


def test_verifier_profile_comes_from_binding_not_invention(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = DeploymentBinding(
        binding_id="test-binding",
        workspace_root=str(workspace),
        state_root=str(tmp_path / "state"),
        registry_root=str(tmp_path / "registry"),
        interpreter=sys.executable,
        profile_ref="implementer",
        agent_role="implementer",
        verifier_profile_ref="verifier",
    )
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "registry").mkdir(exist_ok=True)
    verifier = {
        "profile_id": "verifier",
        "agent_id": "test-verifier",
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["VERIFY"],
        "adapter_options": {"argv": [sys.executable, "-c", "pass"]},
    }
    program = render_program(
        contract,
        binding,
        approved_by="owner",
        approval_reference="ref",
        profile=PROFILE,
        verifier_profile=verifier,
    )
    task = program["program"]["tasks"][0]
    assert task["requires_independent_verification"] is True
    assert task["verifier_profile_ref"] == "verifier"
    assert program["field_provenance"]["verifier_profile_ref"]["origin"] == "BINDING"
    assert "verifier" in program["profiles"]


def test_no_check_available_refuses_invented_command(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    # Rebuild with NO_CHECK_AVAILABLE on a requirement.
    raw = contract.model_dump(mode="json")
    raw["requirements"] = [
        {
            "requirement_id": "R1",
            "statement": "something true",
            "verification": VerificationMode.NO_CHECK_AVAILABLE.value,
            "check_ids": [],
            "review_note": "nobody automated this",
        }
    ]
    broken = TaskContract.model_validate(raw)
    with pytest.raises(TaskContractError) as exc:
        assert_machine_acceptance_renderable(broken)
    assert exc.value.code == "ACCEPTANCE_MACHINE_CHECK_INCOMPLETE"
    with pytest.raises(TaskContractError) as exc2:
        render_program(
            broken,
            _binding(tmp_path, workspace),
            approved_by="o",
            approval_reference="r",
            profile=PROFILE,
        )
    assert exc2.value.code == "ACCEPTANCE_MACHINE_CHECK_INCOMPLETE"


def test_origination_identity_stable_and_changes_with_content() -> None:
    base = dict(
        project_id="e2e-fixture",
        location="docs/backlog.md",
        item_id="E2E-FIX-001",
        item_digest="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        proposed_scope=("E2E-FIX-001.txt",),
        success_criteria=("file exists", "content matches"),
    )
    a = origination_identity_from_parts(**base)
    b = origination_identity_from_parts(**base)
    assert a == b
    mutated = dict(base)
    mutated["item_digest"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    c = origination_identity_from_parts(**mutated)
    assert c != a
    # work_id shape depends only on project+item_id — same item_id keeps work_id.
    from project_atlas.orchestration.origination.identity import work_id_for

    assert work_id_for(base["project_id"], base["item_id"]) == work_id_for(
        mutated["project_id"], mutated["item_id"]
    )


def test_attempt_copies_identity_and_legacy_reads_unknown() -> None:
    oid = "6" * 64
    digest = "a" * 64
    task = ProgramTask(
        task_id="TASK-001",
        title="t",
        instruction="do the thing",
        profile_ref="implementer",
        mutation_paths=("out.txt",),
        surface_id="TASK-001",
        surface_semantic="TASK_001",
        acceptance=(
            {
                "check_id": "c1",
                "kind": "FILE_EXISTS",
                "description": "out exists",
                "path": "out.txt",
            },
        ),
        contract_digest=digest,
        source_item_digest="itemdigest12345678",
        origination_identity=oid,
    )
    assert task.to_work_node(base_pin="0" * 40).origination_identity == oid
    attempt = AttemptRecord(
        attempt_id="p.TASK-001.run.1.deadbeef",
        task_id=task.task_id,
        attempt_number=1,
        idempotency_key="key",
        profile_id="implementer",
        agent_id="agent",
        adapter="local-command",
        profile_digest="b" * 64,
        base_pin="0" * 40,
        contract_digest=task.contract_digest,
        source_item_digest=task.source_item_digest,
        origination_identity=task.origination_identity,
    )
    assert attempt.origination_identity == oid
    legacy = AttemptRecord(
        attempt_id="legacy.1",
        task_id="OLD",
        attempt_number=1,
        idempotency_key="k",
        profile_id="p",
        agent_id="a",
        adapter="local-command",
        profile_digest="c" * 64,
        base_pin="0" * 40,
    )
    assert legacy.origination_identity is None
    # Never backfill fiction onto historical records.
    dumped = json.loads(legacy.model_dump_json())
    assert dumped.get("origination_identity") is None


def test_binding_digest_stable_when_optional_verifier_absent(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    state = tmp_path / "state"
    registry = tmp_path / "registry"
    state.mkdir()
    registry.mkdir()
    without = DeploymentBinding(
        binding_id="b",
        workspace_root=str(workspace),
        state_root=str(state),
        registry_root=str(registry),
        interpreter=sys.executable,
        profile_ref="implementer",
        agent_role="implementer",
    )
    with_none = DeploymentBinding(
        binding_id="b",
        workspace_root=str(workspace),
        state_root=str(state),
        registry_root=str(registry),
        interpreter=sys.executable,
        profile_ref="implementer",
        agent_role="implementer",
        verifier_profile_ref=None,
    )
    assert binding_digest(without) == binding_digest(with_none)
