"""AS-ORCH-AUTONOMY-001 stale-runtime-anchor CHECKPOINT RECOVERY.

Security/control-plane test matrix (A-T per the owner's directive) for
``TrustCheckpointProof`` / ``advance_via_checkpoint_recovery()`` --
distinct from, and never a substitute for, ordinary single-hop
``advance_trusted_anchor()`` (that mechanism's own matrix lives in
``test_orchestration_autonomy_pin_retarget.py`` and is untouched by this
PR; a few tests here re-confirm it stays byte-for-byte strict, item R).
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.autonomy import governor as governor_module
from project_atlas.orchestration.autonomy import loop as loop_module
from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementProof,
    AdvancementReason,
    TrustCheckpointProof,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import (
    CheckpointChecks,
    FixtureGitObserver,
    TrustError,
    _checkpoint_evidence_binding,
    advance_trusted_anchor,
    advance_via_checkpoint_recovery,
    classify_observation,
    evaluate_checkpoint_recovery,
    evaluate_target_moved,
    initialize_store,
    seal_anchor,
    verify_checkpoint_evidence_integrity,
)

OLD_MAIN = "a" * 40
OLD_TREE = "b" * 40
MID_1 = "1" * 39 + "a"
MID_2 = "2" * 39 + "a"
CANDIDATE_HEAD = "3" * 39 + "a"
CANDIDATE_TREE = "4" * 39 + "a"
TARGET_MAIN = "5" * 39 + "a"
TARGET_TREE = "6" * 39 + "a"
SIDE_BRANCH = "7" * 39 + "a"
SIDE_ROOT = "8" * 39 + "a"
OTHER_MAIN = "9" * 39 + "a"
UNRELATED_ROOT = "0" * 39 + "a"
MISSING = "c" * 40
NEXT_CANDIDATE = "d" * 39 + "a"
NEXT_CANDIDATE_TREE = "e" * 39 + "a"
NEXT_MAIN = "f" * 39 + "a"


def _chain_digest(chain: list[str]) -> str:
    """Independent re-implementation of the expected digest formula (not
    calling any code under test) so the assertion is meaningful."""
    return hashlib.sha256("\n".join(chain).encode("utf-8")).hexdigest()


CHAIN = [TARGET_MAIN, MID_2, MID_1, OLD_MAIN]
HOP_COUNT = len(CHAIN) - 1
CHAIN_DIGEST = _chain_digest(CHAIN)


def _current_anchor(
    *,
    main: str = OLD_MAIN,
    tree: str = OLD_TREE,
    sequence: int = 1,
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=identity,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=UNRELATED_ROOT,
            predecessor_tree=OLD_TREE,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-AUTONOMY-PIN-RETARGET-003",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=UNRELATED_ROOT,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/checkpoint-old-anchor.json",
            evidence_digest="ab" * 32,
            sequence=sequence,
            record_digest="00" * 32,
        )
    )


def _payload() -> dict[str, object]:
    return {"kind": "OWNER_CHECKPOINT_RECERTIFICATION", "target": TARGET_MAIN}


def _proof(
    current: TrustedAnchorRecord,
    *,
    target_main: str = TARGET_MAIN,
    target_tree: str = TARGET_TREE,
    parent_1: str = MID_2,
    parent_2: str = CANDIDATE_HEAD,
    candidate_head: str = CANDIDATE_HEAD,
    candidate_tree: str = CANDIDATE_TREE,
    hop_count: int = HOP_COUNT,
    chain_digest: str = CHAIN_DIGEST,
    seal: str = "PASS",
    ci: str = "PASS",
    iv: str = "PASS",
    owner: str = "OWNER_AUTHORIZED",
    reason: str = "STALE_RUNTIME_ANCHOR_RECOVERY",
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
    payload: dict[str, object] | None = None,
    digest: str | None = None,
) -> TrustCheckpointProof:
    evidence = payload if payload is not None else _payload()
    # evidence_digest must bind to the whole proof (not just the free-
    # form payload) -- construct with a placeholder first, then compute
    # the real digest via the same binding trust.py's own
    # verify_checkpoint_evidence_integrity() uses, unless the caller
    # passed an explicit (possibly deliberately wrong, for a denial
    # test) `digest`.
    draft = TrustCheckpointProof(
        repository_identity=identity,
        owner_authorization=owner,  # type: ignore[arg-type]
        checkpoint_reason=reason,  # type: ignore[arg-type]
        expected_previous_main=current.trusted_main,
        expected_previous_tree=current.trusted_tree,
        target_main=target_main,
        target_tree=target_tree,
        target_merge_parent_1=parent_1,
        target_merge_parent_2=parent_2,
        certified_candidate_head=candidate_head,
        certified_candidate_tree=candidate_tree,
        first_parent_hop_count=hop_count,
        first_parent_chain_digest=chain_digest,
        post_merge_seal=seal,  # type: ignore[arg-type]
        post_merge_ci=ci,  # type: ignore[arg-type]
        independent_verification=iv,  # type: ignore[arg-type]
        evidence_reference="tests/fixtures/checkpoint-proof.json",
        evidence_digest=digest or "0" * 64,
        source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
        source_directive="D-AUTONOMY-PIN-RETARGET-003",
        source_pr=2,
        evidence_payload=evidence,
    )
    if digest is not None:
        return draft
    bound_digest = hash_payload(_checkpoint_evidence_binding(draft))
    return draft.model_copy(update={"evidence_digest": bound_digest})


def _topology(
    *,
    observed_main: str = TARGET_MAIN,
    observed_tree: str = TARGET_TREE,
    observe_sequence: tuple[tuple[str, str], ...] | None = None,
    with_side_branch_trap: bool = False,
) -> FixtureGitObserver:
    objects: dict[str, tuple[str, tuple[str, ...]]] = {
        OLD_MAIN: (OLD_TREE, ()),
        MID_1: (OLD_TREE, (OLD_MAIN,)),
        MID_2: (OLD_TREE, (MID_1,)),
        CANDIDATE_HEAD: (CANDIDATE_TREE, ()),
        TARGET_MAIN: (TARGET_TREE, (MID_2, CANDIDATE_HEAD)),
    }
    if with_side_branch_trap:
        # OLD_MAIN is reachable from TARGET_MAIN via SOME path (through
        # the side branch merged in as parent[1] of MID_2), but NOT via a
        # pure first-parent walk -- MID_2's own first parent is SIDE_ROOT,
        # a dead end that never reaches OLD_MAIN. `git merge-base
        # --is-ancestor` would say YES; a genuine first-parent walk must
        # say NO.
        objects[SIDE_ROOT] = (OLD_TREE, ())
        objects[SIDE_BRANCH] = (OLD_TREE, (OLD_MAIN,))
        objects[MID_2] = (OLD_TREE, (SIDE_ROOT, SIDE_BRANCH))
    return FixtureGitObserver(
        observed_main=observed_main,
        observed_tree=observed_tree,
        objects=objects,
        observe_sequence=observe_sequence,
    )


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_positive_checkpoint_recovery_advances_and_preserves_history(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology()
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_checkpoint_recovery(current, proof, topology, store=store)
    assert new_record.trusted_main == TARGET_MAIN
    assert new_record.trusted_tree == TARGET_TREE
    assert new_record.predecessor_main == OLD_MAIN
    assert new_record.predecessor_tree == OLD_TREE
    assert new_record.sequence == current.sequence + 1
    assert new_record.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CHECKPOINT
    # Truthfulness (owner intent §4): merge_parent_1/2 are the ACTUAL git
    # parents of target_main, never forged to look like an ordinary
    # single-hop record (predecessor_main != merge_parent_1 here, by
    # design -- that is exactly how a reader tells checkpoint recovery
    # apart from ordinary advancement even without reading the reason).
    assert new_record.merge_parent_1 == MID_2
    assert new_record.merge_parent_2 == CANDIDATE_HEAD
    assert new_record.merge_parent_1 != new_record.predecessor_main
    # History preserved: old anchor retained at sequence 1.
    history = (tmp_path / "store" / "history" / f"{current.sequence:08d}.json").read_text(
        encoding="utf-8"
    )
    assert current.trusted_main in history
    current_on_disk = (tmp_path / "store" / "current.json").read_text(encoding="utf-8")
    assert TARGET_MAIN in current_on_disk


def test_cross_process_trust_reuse(tmp_path: Path) -> None:
    """The checkpoint record, once persisted, must reload identically in
    a fresh process/load (§17's CROSS_PROCESS_TRUST_REUSE)."""
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    current = _current_anchor()
    proof = _proof(current)
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_checkpoint_recovery(current, proof, _topology(), store=store)
    reloaded = load_runtime_anchor(store=store)
    assert reloaded.model_dump(mode="json") == new_record.model_dump(mode="json")
    trust_state = classify_observation(TARGET_MAIN, TARGET_TREE, reloaded)
    assert trust_state.value == "TRUSTED"
    assert evaluate_target_moved(TARGET_MAIN, TARGET_TREE, reloaded) is False


# ---------------------------------------------------------------------------
# A-Q: adversarial denial matrix
# ---------------------------------------------------------------------------


def test_a_no_owner_authorized_denied() -> None:
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, owner="NOT_AUTHORIZED")


def test_b_repository_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, identity="github.com/someone-else/other-repo")
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_c_target_not_observed_main_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(observed_main=OTHER_MAIN, observed_tree=TARGET_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_d_target_tree_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(observed_tree=OTHER_MAIN)  # wrong tree, still 40 chars
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_e_old_anchor_not_ancestor_at_all_denied(tmp_path: Path) -> None:
    current = _current_anchor(main=OTHER_MAIN, tree=TARGET_TREE)
    proof = _proof(current)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_f_old_anchor_only_reachable_via_non_first_parent_denied(tmp_path: Path) -> None:
    """The load-bearing test (owner directive §5): merge-base would say
    YES here, but the mechanism must say NO -- OLD_MAIN is only reachable
    through the side branch, never through a pure first-parent walk."""
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(with_side_branch_trap=True)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"
    # Sanity: confirm the trap is real -- merge-base WOULD say ancestor.
    assert topology.is_descendant(TARGET_MAIN, OLD_MAIN) is True


def test_g_first_parent_hop_count_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hop_count=HOP_COUNT + 1)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_h_first_parent_chain_digest_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, chain_digest="ff" * 32)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_i_target_moves_during_verification_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    # First observe() call sees TARGET_MAIN (matches proof); the
    # REOBSERVE call sees something else -- must fail closed, not silently
    # proceed on the first (now-stale) observation.
    topology = _topology(
        observe_sequence=(
            (TARGET_MAIN, TARGET_TREE),
            (OTHER_MAIN, TARGET_TREE),
        )
    )
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "TARGET_MOVED_DURING_VERIFICATION"


def test_j_post_merge_ci_not_pass_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, ci="FAIL")
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_k_post_merge_seal_not_pass_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, seal="FAIL")
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_l_independent_verification_not_pass_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, iv="FAIL")
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_m_evidence_digest_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, digest="ff" * 32)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_n_stale_or_concurrent_writer_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    store = tmp_path / "store"
    initialize_store(store, current)
    advance_via_checkpoint_recovery(current, proof, _topology(), store=store)
    # A second attempt using the SAME (now-stale) `current` snapshot must
    # be rejected -- the store has already moved on. In practice this now
    # fires as CHECKPOINT_ALREADY_USED (item's own one-time-use gate,
    # checked earliest) rather than reaching the deeper CAS check -- but
    # either denial reason is acceptable defense-in-depth for this
    # scenario; what matters is that SOME denial happens.
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, _proof(current), _topology(), store=store)
    assert exc.value.code in {
        "PREDECESSOR_MISMATCH",
        "ANCHOR_CAS_MISMATCH",
        "CHECKPOINT_ALREADY_USED",
    }


def test_o_rollback_target_denied(tmp_path: Path) -> None:
    """A checkpoint whose target is not strictly ahead (e.g. equal to the
    current anchor) must be denied -- covered structurally by the
    first-parent-ancestry requirement (hop_count must be >= 1, walking
    parent links only ever goes toward older commits)."""
    current = _current_anchor(main=TARGET_MAIN, tree=TARGET_TREE)
    with pytest.raises(ValueError):
        # target_main == expected_previous_main == current.trusted_main:
        # the proof model itself doesn't forbid this shape, but the walk
        # must reject it (hop_count 0 is not representable >= 1 anyway).
        _proof(current, target_main=TARGET_MAIN, hop_count=0)


def test_o_rollback_via_denial_path(tmp_path: Path) -> None:
    current = _current_anchor(main=TARGET_MAIN, tree=TARGET_TREE)
    # hop_count=2 (the schema minimum): target_main == current.trusted_main
    # still makes the walk fail immediately (target == ancestor), regardless
    # of what hop_count/chain_digest claim -- the ancestry check, not the
    # hop-count/digest checks, is what denies this.
    proof = _proof(current, target_main=TARGET_MAIN, hop_count=2, chain_digest="ee" * 32)
    topology = _topology(observed_main=TARGET_MAIN, observed_tree=TARGET_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_p_checkpoint_to_same_anchor_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, target_main=OLD_MAIN, target_tree=OLD_TREE, hop_count=2)
    topology = _topology(observed_main=OLD_MAIN, observed_tree=OLD_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_q_corrupt_runtime_store_denied(tmp_path: Path) -> None:
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    store = tmp_path / "store"
    store.mkdir()
    (store / "current.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(TrustError) as exc:
        load_runtime_anchor(store=store)
    assert exc.value.code == "TRUST_UNVERIFIABLE"


def test_target_and_candidate_head_nonexistent_git_objects_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, target_main=MISSING)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "GIT_OBJECT_MISSING"


def test_candidate_head_not_second_parent_rejected_by_schema() -> None:
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, candidate_head=OTHER_MAIN)


# ---------------------------------------------------------------------------
# R-T: preserve normal advancement, no automatic invocation, descendant
# alone is never authority
# ---------------------------------------------------------------------------


def test_r_evaluate_checkpoint_recovery_is_a_distinct_function_from_advancement() -> None:
    """Sanity that the two mechanisms are genuinely separate call paths
    (not one silently delegating to / weakening the other)."""
    from project_atlas.orchestration.autonomy import trust as trust_module

    assert trust_module.advance_trusted_anchor is not trust_module.advance_via_checkpoint_recovery
    assert trust_module.evaluate_advancement is not trust_module.evaluate_checkpoint_recovery
    # The ordinary AdvancementChecks dataclass is untouched -- still no
    # first-parent-chain fields, still requires exact merge_parent_1 match
    # (that behavior is re-exercised in test_orchestration_autonomy_pin_
    # retarget.py, unmodified by this PR).
    assert "first_parent_hop_count_match" not in {
        f for f in trust_module.AdvancementChecks.__dataclass_fields__
    }


def test_s_checkpoint_recovery_not_reachable_from_governor_or_loop() -> None:
    """Structural guarantee (owner directive §11/§S): nothing in the
    governor's or loop's own observation/tick machinery imports or calls
    the checkpoint-recovery mechanism -- it is only reachable through the
    explicit CLI surface with an explicit --proof file."""
    for module in (governor_module, loop_module):
        source = inspect.getsource(module)
        assert "advance_via_checkpoint_recovery" not in source
        assert "TrustCheckpointProof" not in source


def test_t_observed_descendant_alone_never_becomes_authority() -> None:
    """Re-confirms existing, unmodified behavior: a live main that is a
    genuine (first-parent) descendant of the trusted anchor is STILL
    classified TARGET_MOVED, never TRUSTED, with no proof supplied --
    descendant status alone is never sufficient authority, checkpoint or
    otherwise."""
    current = _current_anchor()
    state = classify_observation(TARGET_MAIN, TARGET_TREE, current, descendant_of_trusted=True)
    assert state.value == "TARGET_MOVED"
    assert evaluate_target_moved(TARGET_MAIN, TARGET_TREE, current) is True


# ---------------------------------------------------------------------------
# CheckpointChecks itself: confirm partial-failure granularity (useful for
# CLI error reporting, and proves no single check silently masks another).
# ---------------------------------------------------------------------------


def test_checkpoint_checks_reports_each_failure_independently() -> None:
    current = _current_anchor()
    proof = _proof(current, ci="FAIL", seal="FAIL")
    topology = _topology()
    observed_main, observed_tree = topology.observe_main()
    checks = evaluate_checkpoint_recovery(
        current, proof, topology, observed_main=observed_main, observed_tree=observed_tree
    )
    assert isinstance(checks, CheckpointChecks)
    assert checks.post_merge_ci is False
    assert checks.post_merge_seal is False
    assert checks.owner_authorization_proven is True
    assert checks.first_parent_ancestry is True
    assert checks.all_required is False


# ---------------------------------------------------------------------------
# Fresh-IV-round remediation (PR #664 review): evidence-target binding,
# genuine one-time-use enforcement, hop_count>=2, exactly-2-parents, and
# OSError fail-closed in the CLI layer.
# ---------------------------------------------------------------------------


def test_evidence_digest_bound_to_target_not_reusable_across_targets() -> None:
    """Review finding: evidence_digest must be a binding commitment over
    the WHOLE proof, not just the free-form evidence_payload -- otherwise
    a legitimately-authorized evidence payload/digest pair for one target
    could be lifted, unchanged, onto a proof for a completely different
    target/ancestry/authorization and still pass integrity, making the
    resulting owner-authorization claim untraceable to evidence for that
    specific target."""
    current = _current_anchor()
    proof_a = _proof(current, target_main=TARGET_MAIN)
    assert verify_checkpoint_evidence_integrity(proof_a) is True  # sanity: legit proof validates

    # Lift proof_a's evidence_payload/evidence_digest verbatim onto a
    # proof for a DIFFERENT target -- must now fail.
    proof_b = _proof(
        current,
        target_main=OTHER_MAIN,
        payload=proof_a.evidence_payload,
        digest=proof_a.evidence_digest,
    )
    assert verify_checkpoint_evidence_integrity(proof_b) is False


def test_checkpoint_recovery_is_genuinely_one_time_ever(tmp_path: Path) -> None:
    """A SECOND checkpoint recovery must be refused even against the
    store's genuinely CURRENT (non-stale) state -- checkpoint recovery is
    a one-time capability, never a repeatable substitute for ordinary
    single-hop advance_trusted_anchor() on every subsequent merge."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)
    first_proof = _proof(current)
    advanced = advance_via_checkpoint_recovery(current, first_proof, _topology(), store=store)
    assert advanced.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CHECKPOINT

    # A second, well-formed-looking checkpoint FROM THE NEW (correct,
    # non-stale) anchor must still be denied -- fires before topology is
    # even consulted, so the second proof's target need not be real.
    second_proof = _proof(advanced, target_main=OTHER_MAIN, hop_count=2, chain_digest="cc" * 32)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(advanced, second_proof, _topology(), store=store)
    assert exc.value.code == "CHECKPOINT_ALREADY_USED"


def test_checkpoint_already_used_gate_survives_deleted_history_entry(tmp_path: Path) -> None:
    """A second, independent IV round's real finding: deleting exactly
    ONE retained history file (specifically the one holding the
    checkpoint record, after it has been superseded by a later ORDINARY
    advance_trusted_anchor() call -- the expected long-term operational
    flow the checkpoint fix itself recommends) must not silently reset
    the one-time-use gate. Reproduces the attack end-to-end through the
    real advance_via_checkpoint_recovery()/advance_trusted_anchor() calls
    (not just the internal helper in isolation)."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)

    # Checkpoint #1: OLD_MAIN -> TARGET_MAIN (sequence 1 -> 2).
    checkpointed = advance_via_checkpoint_recovery(
        current, _proof(current), _topology(), store=store
    )
    assert checkpointed.sequence == 2
    assert checkpointed.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CHECKPOINT

    # Ordinary single-hop advance: TARGET_MAIN -> NEXT_MAIN (sequence
    # 2 -> 3) -- moves the checkpoint record out of current.json and
    # into history/00000002.json.
    extended_objects: dict[str, tuple[str, tuple[str, ...]]] = {
        OLD_MAIN: (OLD_TREE, ()),
        MID_1: (OLD_TREE, (OLD_MAIN,)),
        MID_2: (OLD_TREE, (MID_1,)),
        CANDIDATE_HEAD: (CANDIDATE_TREE, ()),
        TARGET_MAIN: (TARGET_TREE, (MID_2, CANDIDATE_HEAD)),
        NEXT_CANDIDATE: (NEXT_CANDIDATE_TREE, ()),
        NEXT_MAIN: (NEXT_CANDIDATE_TREE, (TARGET_MAIN, NEXT_CANDIDATE)),
    }
    normal_topology = FixtureGitObserver(
        observed_main=NEXT_MAIN, observed_tree=NEXT_CANDIDATE_TREE, objects=extended_objects
    )
    normal_evidence = {"kind": "normal-advance"}
    normal_proof = AdvancementProof(
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        owner_authorization="OWNER_AUTHORIZED",
        expected_previous_main=checkpointed.trusted_main,
        expected_previous_tree=checkpointed.trusted_tree,
        authorized_candidate_head=NEXT_CANDIDATE,
        authorized_candidate_tree=NEXT_CANDIDATE_TREE,
        merge_commit=NEXT_MAIN,
        merge_parent_1=TARGET_MAIN,
        merge_parent_2=NEXT_CANDIDATE,
        merge_tree=NEXT_CANDIDATE_TREE,
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        evidence_reference="tests/fixtures/checkpoint-next-proof.json",
        evidence_digest=hash_payload(normal_evidence),
        source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
        source_directive="D-AUTONOMY-PIN-RETARGET-003",
        source_pr=3,
        evidence_payload=normal_evidence,
    )
    advanced_normally = advance_trusted_anchor(
        checkpointed, normal_proof, normal_topology, store=store
    )
    assert advanced_normally.sequence == 3
    assert advanced_normally.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE

    # Delete ONLY the history entry that held the checkpoint record --
    # current.json and the other history entry are left untouched and
    # self-consistent.
    checkpoint_history_file = store / "history" / "00000002.json"
    assert checkpoint_history_file.is_file()
    checkpoint_history_file.unlink()

    # A THIRD attempt -- another checkpoint -- must now be denied, even
    # though nothing currently in the store LOOKS like it ever held a
    # checkpoint: the gap itself is what must be caught.
    third_proof = _proof(
        advanced_normally, target_main=OTHER_MAIN, hop_count=2, chain_digest="dd" * 32
    )
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(advanced_normally, third_proof, _topology(), store=store)
    assert exc.value.code == "CHECKPOINT_ALREADY_USED"


def test_hop_count_of_one_is_schema_rejected() -> None:
    """A checkpoint proof claiming exactly 1 hop -- i.e. current.
    trusted_main IS target_main's direct first parent -- is exactly the
    case ordinary single-hop advance_trusted_anchor() already handles
    strictly; the schema itself forbids using checkpoint recovery as a
    substitute for that."""
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, hop_count=1)


def test_octopus_merge_target_rejected(tmp_path: Path) -> None:
    """A checkpoint target with 3+ parents (an octopus merge) must be
    rejected even if the first two happen to match the proof -- the
    proof would otherwise describe an incomplete parent set while being
    accepted as though it fully described the target."""
    objects: dict[str, tuple[str, tuple[str, ...]]] = {
        OLD_MAIN: (OLD_TREE, ()),
        MID_1: (OLD_TREE, (OLD_MAIN,)),
        MID_2: (OLD_TREE, (MID_1,)),
        CANDIDATE_HEAD: (CANDIDATE_TREE, ()),
        SIDE_BRANCH: (OLD_TREE, (OLD_MAIN,)),
        TARGET_MAIN: (TARGET_TREE, (MID_2, CANDIDATE_HEAD, SIDE_BRANCH)),
    }
    topology = FixtureGitObserver(
        observed_main=TARGET_MAIN, observed_tree=TARGET_TREE, objects=objects
    )
    current = _current_anchor()
    proof = _proof(current)
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CHECKPOINT_DENIED"


def test_run_trust_checkpoint_catches_store_io_error(tmp_path: Path) -> None:
    """An OSError from store I/O (e.g. an obstructed trust-store path)
    must produce the same clean, fail-closed JSON report as every other
    genuine problem here -- never an unhandled exception escaping the
    CLI entrypoint."""
    from project_atlas.orchestration.autonomy.cli import EXIT_ERROR, run_trust_checkpoint

    obstruction = tmp_path / "not_a_directory"
    obstruction.write_text("i am a file", encoding="utf-8")
    trust_store = obstruction / "trust"  # parent is a file -- mkdir must fail

    report, exit_code = run_trust_checkpoint(
        root=tmp_path,
        trust_store=trust_store,
        proof_path=tmp_path / "does-not-matter.json",
        bootstrap_from_shipped=True,
    )
    assert exit_code == EXIT_ERROR
    assert report["checkpoint_advanced"] is False
    assert report["blocker"] == "CHECKPOINT_STORE_IO_ERROR"
