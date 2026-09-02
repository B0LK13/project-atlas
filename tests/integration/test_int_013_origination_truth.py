"""INT-013 origination-truth reconciliation -- real-repo empirical proof.

Owner review (2026-09-02): the real M3/INT-013 incident was that
`docs/product/CODER-ALPHA-NORTH-STAR.md` (the current, authoritative
priority document) classifies INT-013 `EXTERNAL_BLOCKED`, but
`docs/backlog.md`'s own task-list line -- the only text the origination
pipeline's blocker detection reads -- carried no blocker language, so a
real, valid acceptance contract (`docs/origination-acceptance-
contracts.yaml`) legitimately supplied evidence and the existing,
unmodified policy gates correctly marked INT-013 `execution_ready =
True`.

`tests/unit/test_orchestration_acceptance_contracts.py::
test_external_blocked_item_stays_blocked_even_with_a_valid_contract`
already proves the underlying invariant generically (synthetic fixture,
this repository's own established convention for that test file). This
is the OTHER half owner review asked for: real, empirical proof against
THIS repository's own actual `docs/backlog.md` and
`docs/origination-acceptance-contracts.yaml` -- not a synthetic stand-in
-- so a later, unrelated edit to either real file that silently drops
the blocker annotation is caught here, not just in the synthetic case.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.orchestration.origination.pipeline import originate_all

REPO_ROOT = Path(__file__).resolve().parents[2]


def _int013_outcome() -> object:
    outcomes = originate_all(REPO_ROOT, "project-atlas")
    matches = [
        outcome
        for outcome in outcomes
        if outcome.proposal.authoritative_source.subject_id == "INT-013"
    ]
    assert len(matches) == 1, (
        f"expected exactly one INT-013 origination outcome, found {len(matches)} "
        "-- docs/backlog.md's INT-013 line or its origination source "
        "configuration may have changed shape"
    )
    return matches[0]


def test_int013_is_discovered() -> None:
    """INT013_PRESENT = YES."""
    outcome = _int013_outcome()
    assert outcome.proposal.authoritative_source.subject_id == "INT-013"


def test_int013_declares_the_external_blocked_keyword() -> None:
    """INT013_BLOCKER_CONTAINS_EXTERNAL_BLOCKED = YES."""
    outcome = _int013_outcome()
    assert outcome.proposal.blockers
    assert any("external_blocked" in b.lower() for b in outcome.proposal.blockers)


def test_int013_execution_ready_is_false() -> None:
    """INT013_EXECUTION_READY = FALSE -- even though a real, valid
    acceptance contract with genuine evidence exists for it (see the
    next two assertions): ACCEPTANCE_CONTRACT_CAN_WIDEN_EVIDENCE = YES,
    ACCEPTANCE_CONTRACT_CAN_CLEAR_BLOCKER = NO, proven here against the
    real production configuration, not a synthetic stand-in."""
    outcome = _int013_outcome()
    assert outcome.policy.execution_ready is False


def test_int013_fixture_contract_is_present_and_widens_evidence() -> None:
    """FIXTURE_CONTRACT_PRESENT = YES: the real acceptance contract's
    evidence genuinely reaches the proposal (contract widens evidence)."""
    outcome = _int013_outcome()
    assert (
        "tests/integration/test_int_013_bounded_multi_project_pilot.py"
        in outcome.proposal.proposed_scope
    )


def test_int013_fixture_contract_does_not_clear_the_blocker() -> None:
    """FIXTURE_CONTRACT_DOES_NOT_CLEAR_BLOCKER = YES: the same outcome
    that has real, widened evidence (previous test) still carries the
    real blocker and is still not execution_ready (contract cannot
    clear authority)."""
    outcome = _int013_outcome()
    assert outcome.proposal.blockers
    assert outcome.policy.execution_ready is False


def test_int013_backlog_checkbox_is_unchecked() -> None:
    """INT013_CHECKBOX = UNCHECKED."""
    backlog_text = (REPO_ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    assert "- [ ] INT-013 Run the bounded multi-project integration pilot" in backlog_text
    assert "- [x] INT-013" not in backlog_text
