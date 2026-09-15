from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

# ---------------------------------------------------------------------------
# Content contract (explicit choice for ATLAS-AGY-LAB-HARDENING P1)
#
# CONTRACT B — Accept any collections.abc.Mapping, then immediately
# materialize a plain local ``dict`` snapshot via ``dict(mapping)``.
#
# After validation / snapshot, verdict and claim_integrity MUST be read only
# from that local snapshot. Do not re-read a caller-held mutable
# ``verifier_report.content`` (or other Mapping) for gate fields.
#
# Honesty bounds (non-claims):
# - ``isinstance(content, dict)`` is NOT used and does NOT exclude dynamic
#   mappings, dict subclasses, or TOCTOU on a live shared object.
# - Snapshotting closes the TOCTOU window only for subsequent reads that use
#   the returned local dict; it does not freeze the caller's original object.
# - Existing ``Governor.run(owner_request)`` call-sites remain source-
#   compatible (single positional/kwarg request string; no new required
#   parameters). This is not a claim of binary or 100% cross-version
#   compatibility.
# ---------------------------------------------------------------------------

CONTENT_CONTRACT: Final = "B"  # Mapping accepted; materialize local dict snapshot


class GuardrailViolation(RuntimeError):
    """Raised when role boundaries are violated in the lab flow."""


@dataclass(frozen=True)
class LaneState:
    lane: str
    state: str


@dataclass(frozen=True)
class AgentEnvelope:
    producer_role: str | None
    kind: str
    content: Mapping[str, Any]


@dataclass(frozen=True)
class DecisionInput:
    remote_head_match: bool
    exact_head_ci: bool
    exact_head_iv: bool
    claim_integrity: bool
    p0_count: int
    p1_count: int
    current_main_compatibility: bool
    mergeable: bool
    owner_gate_resolved: bool
    stale_head: bool
    implementer_self_certification_attempt: bool
    verifier_repo_write_attempt: bool
    lane_states: list[LaneState]
    head_moved_after_decision: bool


@dataclass(frozen=True)
class GateResult:
    verdict: str
    reasons: list[str]
    runnable_lanes: list[str]


@dataclass(frozen=True)
class GovernorDecision:
    owner_request: str
    implementer_output: AgentEnvelope
    verifier_report: AgentEnvelope
    verdict: str
    reasons: list[str]


def snapshot_content(content: Any, *, field: str = "content") -> dict[str, Any]:
    """Materialize ``content`` to a plain local ``dict`` (Contract B).

    Accepts any ``Mapping``. Rejects non-mappings. The returned object is a
    newly constructed built-in ``dict``; later mutation of ``content`` must
    not affect the snapshot.
    """
    if not isinstance(content, Mapping):
        raise GuardrailViolation(f"{field}_not_mapping")
    return dict(content)


def gate_fields_from_verifier_snapshot(
    content_snapshot: Mapping[str, Any],
) -> tuple[bool, bool]:
    """Derive exact_head_iv / claim_integrity from a local snapshot only."""
    exact_head_iv = content_snapshot.get("verdict") == "APPROVE"
    claim_integrity = content_snapshot.get("claim_integrity") == "PASS"
    return exact_head_iv, claim_integrity


class Implementer:
    role = "implementer"

    def execute(self, owner_request: str) -> AgentEnvelope:
        return AgentEnvelope(
            producer_role=self.role,
            kind="implementation_patch",
            content={"summary": f"Proposed implementation for: {owner_request}"},
        )


class Verifier:
    role = "verifier"

    def review(self, implementer_output: AgentEnvelope) -> AgentEnvelope:
        if implementer_output.producer_role != "implementer":
            raise GuardrailViolation("verifier_requires_implementer_input")
        return AgentEnvelope(
            producer_role=self.role,
            kind="verifier_verdict",
            content={"verdict": "APPROVE", "claim_integrity": "PASS"},
        )


class Governor:
    role = "governor"

    def validate_implementer_output(self, output: Mapping[str, Any]) -> None:
        """Masquerade guard for flat implementer dicts (compatibility path).

        A missing ``producer_role`` key is allowed so historical flat-dict
        callers keep working. That allowance is **not** strong identity
        validation — only ``kind == verifier_verdict`` is rejected here.
        Strong implementer identity is enforced on ``AgentEnvelope`` inputs to
        ``Verifier.review`` (role must be exactly ``\"implementer\"``).
        """
        snap = snapshot_content(output, field="implementer_output")
        if snap.get("kind") == "verifier_verdict":
            raise GuardrailViolation("implementer_masquerade_as_verifier")

    def validate_verifier_report(
        self, report: AgentEnvelope | Mapping[str, Any]
    ) -> dict[str, Any]:
        """Require verifier identity; return a local content snapshot.

        ``producer_role`` must be exactly ``\"verifier\"``. ``None``, ``\"\"``,
        or a missing role on a mapping-shaped report are invalid.
        """
        if isinstance(report, AgentEnvelope):
            role = report.producer_role
            raw_content: Any = report.content
        elif isinstance(report, Mapping):
            env_snap = snapshot_content(report, field="verifier_report")
            if "producer_role" not in env_snap:
                raise GuardrailViolation("verifier_identity_invalid")
            role = env_snap.get("producer_role")
            raw_content = env_snap.get("content")
        else:
            raise GuardrailViolation("verifier_report_unsupported_type")

        if role != "verifier":
            raise GuardrailViolation("verifier_identity_invalid")
        return snapshot_content(raw_content, field="verifier_content")

    def run(self, owner_request: str) -> GovernorDecision:
        """Run the lab flow. Call-site shape: ``run(request)`` only.

        Existing ``governor.run(request)`` call-sites remain source-compatible.
        """
        implementer = Implementer()
        verifier = Verifier()
        implementer_output = implementer.execute(owner_request)
        self.validate_implementer_output(
            {
                "producer_role": implementer_output.producer_role,
                "kind": implementer_output.kind,
                "content": implementer_output.content,
            }
        )
        verifier_report = verifier.review(implementer_output)
        content_snapshot = self.validate_verifier_report(verifier_report)
        exact_head_iv, claim_integrity = gate_fields_from_verifier_snapshot(
            content_snapshot
        )
        gate = evaluate_gate(
            DecisionInput(
                remote_head_match=True,
                exact_head_ci=True,
                exact_head_iv=exact_head_iv,
                claim_integrity=claim_integrity,
                p0_count=0,
                p1_count=0,
                current_main_compatibility=True,
                mergeable=True,
                owner_gate_resolved=True,
                stale_head=False,
                implementer_self_certification_attempt=False,
                verifier_repo_write_attempt=False,
                lane_states=[LaneState("lane-owner-request", "RUNNABLE")],
                head_moved_after_decision=False,
            )
        )
        return GovernorDecision(
            owner_request=owner_request,
            implementer_output=implementer_output,
            verifier_report=verifier_report,
            verdict=gate.verdict,
            reasons=gate.reasons,
        )


def evaluate_gate(inputs: DecisionInput) -> GateResult:
    reasons: list[str] = []
    runnable = [lane.lane for lane in inputs.lane_states if lane.state == "RUNNABLE"]

    if inputs.implementer_self_certification_attempt:
        reasons.append("implementer_self_certification")
    if inputs.verifier_repo_write_attempt:
        reasons.append("verifier_write_attempt")
    if inputs.stale_head:
        reasons.append("stale_head")
    if not inputs.remote_head_match:
        reasons.append("remote_head_mismatch")
    if not inputs.exact_head_ci:
        reasons.append("exact_head_ci_missing")
    if not inputs.exact_head_iv:
        reasons.append("exact_head_iv_missing")
    if not inputs.claim_integrity:
        reasons.append("claim_integrity_fail")
    if inputs.p0_count > 0:
        reasons.append("p0_findings")
    if inputs.p1_count > 0:
        reasons.append("p1_findings")
    if not inputs.current_main_compatibility:
        reasons.append("current_main_compatibility_fail")
    if not inputs.mergeable:
        reasons.append("not_mergeable")
    if not inputs.owner_gate_resolved:
        reasons.append("owner_gate_unresolved")
    if inputs.head_moved_after_decision:
        reasons.append("head_moved_after_decision")
    if runnable and not reasons:
        reasons.append("runnable_lanes_nonempty")

    blockers = [reason for reason in reasons if reason != "runnable_lanes_nonempty"]
    verdict = "APPROVE" if not blockers else "BLOCK"
    return GateResult(verdict=verdict, reasons=reasons, runnable_lanes=runnable)
