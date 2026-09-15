from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from experiments.agents_sdk.lab import (
    CONTENT_CONTRACT,
    AgentEnvelope,
    DecisionInput,
    Governor,
    GuardrailViolation,
    LaneState,
    Verifier,
    evaluate_gate,
    gate_fields_from_verifier_snapshot,
    snapshot_content,
)


def test_content_contract_is_b_mapping_snapshot() -> None:
    assert CONTENT_CONTRACT == "B"


def test_demo_flow_enforces_verifier_identity() -> None:
    governor = Governor()
    decision = governor.run(owner_request="Normalize path guards in ingest.")
    assert decision.verifier_report.producer_role == "verifier"
    assert decision.implementer_output.producer_role == "implementer"
    assert decision.verdict in {"BLOCK", "APPROVE"}


def test_governor_run_call_site_source_compatible_without_injection() -> None:
    """Existing governor.run(request) call-sites remain source-compatible."""
    governor = Governor()
    decision = governor.run("Harden merge-gate evidence refresh checks.")
    assert isinstance(decision.verdict, str)
    assert decision.owner_request == "Harden merge-gate evidence refresh checks."
    assert decision.verifier_report.producer_role == "verifier"


def test_implementer_output_cannot_masquerade_as_verifier() -> None:
    governor = Governor()
    with_violating_patch = {
        "producer_role": "implementer",
        "kind": "verifier_verdict",
        "content": {"verdict": "APPROVE"},
    }
    with pytest.raises(GuardrailViolation, match="implementer_masquerade_as_verifier"):
        governor.validate_implementer_output(with_violating_patch)


def test_implementer_flat_dict_missing_producer_role_allowed_compat_only() -> None:
    """Missing implementer role on flat dicts is compatibility, not identity."""
    governor = Governor()
    governor.validate_implementer_output(
        {
            "kind": "implementation_patch",
            "content": {"summary": "flat dict without producer_role"},
        }
    )


def test_verifier_mapping_missing_producer_role_rejected() -> None:
    governor = Governor()
    with pytest.raises(GuardrailViolation, match="verifier_identity_invalid"):
        governor.validate_verifier_report(
            {
                "kind": "verifier_verdict",
                "content": {"verdict": "APPROVE", "claim_integrity": "PASS"},
            }
        )


def test_verifier_envelope_producer_role_none_rejected() -> None:
    governor = Governor()
    report = AgentEnvelope(
        producer_role=None,
        kind="verifier_verdict",
        content={"verdict": "APPROVE", "claim_integrity": "PASS"},
    )
    with pytest.raises(GuardrailViolation, match="verifier_identity_invalid"):
        governor.validate_verifier_report(report)


def test_verifier_envelope_producer_role_empty_rejected() -> None:
    governor = Governor()
    report = AgentEnvelope(
        producer_role="",
        kind="verifier_verdict",
        content={"verdict": "APPROVE", "claim_integrity": "PASS"},
    )
    with pytest.raises(GuardrailViolation, match="verifier_identity_invalid"):
        governor.validate_verifier_report(report)


def test_implementer_envelope_producer_role_none_rejected_by_verifier() -> None:
    verifier = Verifier()
    output = AgentEnvelope(
        producer_role=None,
        kind="implementation_patch",
        content={"summary": "x"},
    )
    with pytest.raises(GuardrailViolation, match="verifier_requires_implementer_input"):
        verifier.review(output)


def test_implementer_envelope_producer_role_empty_rejected_by_verifier() -> None:
    verifier = Verifier()
    output = AgentEnvelope(
        producer_role="",
        kind="implementation_patch",
        content={"summary": "x"},
    )
    with pytest.raises(GuardrailViolation, match="verifier_requires_implementer_input"):
        verifier.review(output)


class _CustomMapping(Mapping[str, Any]):
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def test_custom_mapping_is_accepted_via_contract_b_snapshot() -> None:
    source = _CustomMapping({"verdict": "APPROVE", "claim_integrity": "PASS"})
    snap = snapshot_content(source)
    assert type(snap) is dict
    assert snap == {"verdict": "APPROVE", "claim_integrity": "PASS"}
    exact_iv, claim_ok = gate_fields_from_verifier_snapshot(snap)
    assert exact_iv is True
    assert claim_ok is True


def test_custom_mapping_verifier_report_materialized() -> None:
    governor = Governor()
    report = _CustomMapping(
        {
            "producer_role": "verifier",
            "kind": "verifier_verdict",
            "content": _CustomMapping(
                {"verdict": "APPROVE", "claim_integrity": "PASS"}
            ),
        }
    )
    snap = governor.validate_verifier_report(report)
    assert type(snap) is dict
    assert snap["verdict"] == "APPROVE"


class _GetOverrideDict(dict[str, Any]):
    def get(self, key: Any, default: Any = None) -> Any:
        if key == "verdict":
            return "LIE_VIA_GET"
        if key == "claim_integrity":
            return "LIE_VIA_GET"
        return super().get(key, default)


def test_dict_subclass_overridden_get_does_not_poison_snapshot_gate_fields() -> None:
    lying = _GetOverrideDict(verdict="APPROVE", claim_integrity="PASS")
    assert lying.get("verdict") == "LIE_VIA_GET"
    snap = snapshot_content(lying)
    assert type(snap) is dict
    # Snapshot must not be the subclass (avoids overridden get on later reads).
    assert type(snap) is not _GetOverrideDict
    exact_iv, claim_ok = gate_fields_from_verifier_snapshot(snap)
    assert exact_iv is True
    assert claim_ok is True
    assert snap.get("verdict") == "APPROVE"
    assert snap.get("claim_integrity") == "PASS"


def test_source_mutation_after_snapshot_does_not_affect_gate_fields() -> None:
    governor = Governor()
    mutable_content: dict[str, Any] = {
        "verdict": "APPROVE",
        "claim_integrity": "PASS",
    }
    report = AgentEnvelope(
        producer_role="verifier",
        kind="verifier_verdict",
        content=mutable_content,
    )
    snap = governor.validate_verifier_report(report)
    mutable_content["verdict"] = "BLOCK"
    mutable_content["claim_integrity"] = "FAIL"
    exact_iv, claim_ok = gate_fields_from_verifier_snapshot(snap)
    assert exact_iv is True
    assert claim_ok is True
    assert snap["verdict"] == "APPROVE"
    assert snap["claim_integrity"] == "PASS"


def test_eval_implementer_self_certification_is_blocked() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=True,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE"), LaneState("lane-b", "WAITING_CI")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "implementer_self_certification" in result.reasons


def test_eval_verifier_write_attempt_is_blocked() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=True,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "verifier_write_attempt" in result.reasons


def test_eval_stale_head_is_rejected() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=True,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "stale_head" in result.reasons


def test_eval_ci_pass_iv_missing_is_blocked() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=False,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "exact_head_iv_missing" in result.reasons


def test_eval_iv_fail_ci_pass_is_blocked() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=False,
            claim_integrity=True,
            p0_count=0,
            p1_count=1,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "p1_findings" in result.reasons


def test_eval_owner_gate_unresolved_is_blocked() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=False,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.verdict == "BLOCK"
    assert "owner_gate_unresolved" in result.reasons


def test_lane_waiting_does_not_block_runnable_lane() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "WAITING_CI"), LaneState("lane-b", "RUNNABLE")],
            head_moved_after_decision=False,
        )
    )
    assert result.runnable_lanes == ["lane-b"]
    assert "runnable_lanes_nonempty" in result.reasons


def test_head_moves_after_decision_invalidates_authorization() -> None:
    result = evaluate_gate(
        DecisionInput(
            remote_head_match=True,
            exact_head_ci=True,
            exact_head_iv=True,
            claim_integrity=True,
            p0_count=0,
            p1_count=0,
            current_main_compatibility=True,
            mergeable=True,
            owner_gate_resolved=True,
            stale_head=False,
            implementer_self_certification_attempt=False,
            verifier_repo_write_attempt=False,
            lane_states=[LaneState("lane-a", "RUNNABLE")],
            head_moved_after_decision=True,
        )
    )
    assert result.verdict == "BLOCK"
    assert "head_moved_after_decision" in result.reasons
