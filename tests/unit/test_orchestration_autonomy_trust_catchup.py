"""AS-ORCH-AUTONOMY-001 BOUNDED, per-hop-evidenced trust CATCH-UP.

Security/control-plane test matrix for ``TrustCatchupProof`` /
``advance_via_bounded_catchup()`` -- distinct from, and never a substitute
for, ordinary single-hop ``advance_trusted_anchor()`` or the ONE-TIME
``advance_via_checkpoint_recovery()``. Built under owner directive
D-ATLAS-BOUNDED-TRUST-CATCHUP-RECOVERY after PR #653 merged immediately
after PR #665 without an intervening trust advance, leaving the runtime
anchor two ordinary first-parent hops behind live main -- a gap ordinary
single-hop advancement cannot bridge (it requires the target to be the
exact observed live main AND the previous anchor to be its immediate first
parent) and that reusing the already-spent one-time checkpoint mechanism
must never be used to paper over (§15 below proves that invariant survives
this PR unchanged).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    MAX_CATCHUP_HOPS,
    AdvancementProof,
    AdvancementReason,
    CatchupHopProof,
    TrustCatchupProof,
    TrustCheckpointProof,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import (
    CatchupChecks,
    FixtureGitObserver,
    TrustError,
    _advancement_evidence_binding,
    _catchup_evidence_binding,
    _catchup_hop_binding,
    _checkpoint_already_used,
    advance_trusted_anchor,
    advance_via_bounded_catchup,
    advance_via_checkpoint_recovery,
    compare_and_advance,
    evaluate_catchup_recovery,
    initialize_store,
    load_runtime_anchor,
    seal_anchor,
    verify_catchup_evidence_integrity,
    verify_catchup_hop_evidence_integrity,
)

OLD_MAIN = "a" * 40
OLD_TREE = "b" * 40
HOP1_CANDIDATE = "1" * 39 + "a"
HOP1_CANDIDATE_TREE = "1" * 39 + "b"
HOP1_MERGE = "2" * 39 + "a"
HOP1_TREE = "2" * 39 + "b"
HOP2_CANDIDATE = "3" * 39 + "a"
HOP2_CANDIDATE_TREE = "3" * 39 + "b"
TARGET_MAIN = "4" * 39 + "a"  # == HOP2_MERGE
TARGET_TREE = "4" * 39 + "b"
OTHER_MAIN = "5" * 39 + "a"
SIDE_ROOT = "6" * 39 + "a"
SIDE_BRANCH = "7" * 39 + "a"
MISSING = "c" * 40
WRONG_TREE = "d" * 40
UNRELATED_ROOT = "9" * 39 + "a"
NEXT_CANDIDATE = "8" * 39 + "a"
NEXT_CANDIDATE_TREE = "8" * 39 + "b"
NEXT_MAIN = "e" * 39 + "a"
NEXT_TREE = "e" * 39 + "b"


def _chain_digest(chain: list[str]) -> str:
    """Independent re-implementation of the expected digest formula (not
    calling any code under test) so the assertion is meaningful."""
    return hashlib.sha256("\n".join(chain).encode("utf-8")).hexdigest()


CHAIN = [TARGET_MAIN, HOP1_MERGE, OLD_MAIN]
HOP_COUNT = len(CHAIN) - 1
CHAIN_DIGEST = _chain_digest(CHAIN)


def _current_anchor(
    *,
    main: str = OLD_MAIN,
    tree: str = OLD_TREE,
    sequence: int = 1,
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
    reason: AdvancementReason = AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=identity,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=UNRELATED_ROOT,
            predecessor_tree=OLD_TREE,
            advancement_reason=reason,
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
            evidence_reference="tests/fixtures/catchup-old-anchor.json",
            evidence_digest="ab" * 32,
            sequence=sequence,
            record_digest="00" * 32,
        )
    )


def _hop(
    *,
    merge_commit: str = HOP1_MERGE,
    merge_tree: str = HOP1_TREE,
    merge_parent_1: str = OLD_MAIN,
    merge_parent_2: str = HOP1_CANDIDATE,
    candidate_head: str = HOP1_CANDIDATE,
    candidate_tree: str = HOP1_CANDIDATE_TREE,
    source_pr: int = 665,
    basis: str = "OWNER_AUTHORIZED_AT_MERGE",
    iv: str = "PASS",
    ci: str = "PASS",
    seal: str = "PASS",
    payload: dict[str, object] | None = None,
    digest: str | None = None,
) -> CatchupHopProof:
    evidence = payload if payload is not None else {"kind": "HOP_EVIDENCE", "pr": source_pr}
    draft = CatchupHopProof(
        merge_commit=merge_commit,
        merge_tree=merge_tree,
        merge_parent_1=merge_parent_1,
        merge_parent_2=merge_parent_2,
        certified_candidate_head=candidate_head,
        certified_candidate_tree=candidate_tree,
        source_pr=source_pr,
        source_package="AS-ORCH-AUTONOMY-001-DISCOVERY-TOPOLOGY",
        source_directive="D-ATLAS-BOUNDED-TRUST-CATCHUP-RECOVERY",
        authorization_basis=basis,  # type: ignore[arg-type]
        independent_verification=iv,  # type: ignore[arg-type]
        post_merge_ci=ci,  # type: ignore[arg-type]
        post_merge_seal=seal,  # type: ignore[arg-type]
        evidence_reference="tests/fixtures/catchup-hop.json",
        evidence_digest=digest or "0" * 64,
        evidence_payload=evidence,
    )
    if digest is not None:
        return draft
    return draft.model_copy(update={"evidence_digest": hash_payload(_catchup_hop_binding(draft))})


def _hop1(**overrides: object) -> CatchupHopProof:
    return _hop(**overrides)  # type: ignore[arg-type]


def _hop2(**overrides: object) -> CatchupHopProof:
    base: dict[str, object] = {
        "merge_commit": TARGET_MAIN,
        "merge_tree": TARGET_TREE,
        "merge_parent_1": HOP1_MERGE,
        "merge_parent_2": HOP2_CANDIDATE,
        "candidate_head": HOP2_CANDIDATE,
        "candidate_tree": HOP2_CANDIDATE_TREE,
        "source_pr": 653,
        "basis": "OWNER_RATIFIED_EXISTING_MERGE",
    }
    base.update(overrides)
    return _hop(**base)  # type: ignore[arg-type]


def _proof(
    current: TrustedAnchorRecord,
    *,
    hops: tuple[CatchupHopProof, ...] | None = None,
    target_main: str = TARGET_MAIN,
    target_tree: str = TARGET_TREE,
    hop_count: int | None = None,
    chain_digest: str = CHAIN_DIGEST,
    owner: str = "OWNER_AUTHORIZED",
    reason: str = "BOUNDED_VERIFIED_TRUST_CATCHUP",
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
    expected_previous_main: str | None = None,
    expected_previous_tree: str | None = None,
    payload: dict[str, object] | None = None,
    digest: str | None = None,
) -> TrustCatchupProof:
    the_hops = hops if hops is not None else (_hop1(), _hop2())
    evidence = payload if payload is not None else {"kind": "OWNER_CATCHUP_RECOVERY"}
    draft = TrustCatchupProof(
        repository_identity=identity,
        owner_authorization=owner,  # type: ignore[arg-type]
        catchup_reason=reason,  # type: ignore[arg-type]
        expected_previous_main=expected_previous_main or current.trusted_main,
        expected_previous_tree=expected_previous_tree or current.trusted_tree,
        target_main=target_main,
        target_tree=target_tree,
        hops=the_hops,
        hop_count=hop_count if hop_count is not None else len(the_hops),
        first_parent_chain_digest=chain_digest,
        evidence_reference="tests/fixtures/catchup-proof.json",
        evidence_digest=digest or "0" * 64,
        source_package="AS-ORCH-AUTONOMY-001-DISCOVERY-TOPOLOGY",
        source_directive="D-ATLAS-BOUNDED-TRUST-CATCHUP-RECOVERY",
        source_pr=665,
        evidence_payload=evidence,
    )
    if digest is not None:
        return draft
    bound_digest = hash_payload(_catchup_evidence_binding(draft))
    return draft.model_copy(update={"evidence_digest": bound_digest})


def _topology(
    *,
    observed_main: str = TARGET_MAIN,
    observed_tree: str = TARGET_TREE,
    observe_sequence: tuple[tuple[str, str], ...] | None = None,
    with_side_branch_trap: bool = False,
    with_octopus: bool = False,
    with_next_hop: bool = False,
) -> FixtureGitObserver:
    objects: dict[str, tuple[str, tuple[str, ...]]] = {
        OLD_MAIN: (OLD_TREE, ()),
        HOP1_CANDIDATE: (HOP1_CANDIDATE_TREE, ()),
        HOP1_MERGE: (HOP1_TREE, (OLD_MAIN, HOP1_CANDIDATE)),
        HOP2_CANDIDATE: (HOP2_CANDIDATE_TREE, ()),
        TARGET_MAIN: (TARGET_TREE, (HOP1_MERGE, HOP2_CANDIDATE)),
    }
    if with_next_hop:
        # A real third hop past TARGET_MAIN, for tests that need a
        # different, genuinely-existing target commit (e.g. proving a
        # proof's evidence cannot be lifted onto a target it doesn't
        # actually cover).
        objects[NEXT_CANDIDATE] = (NEXT_CANDIDATE_TREE, ())
        objects[NEXT_MAIN] = (NEXT_TREE, (TARGET_MAIN, NEXT_CANDIDATE))
    if with_side_branch_trap:
        # OLD_MAIN reachable from TARGET_MAIN via SOME path (through a side
        # branch merged as HOP1_MERGE's parent[1]), but NOT via a pure
        # first-parent walk -- HOP1_MERGE's real first parent becomes
        # SIDE_ROOT, a dead end. A per-hop proof claiming merge_parent_1 ==
        # OLD_MAIN must be rejected against this topology.
        objects[SIDE_ROOT] = (OLD_TREE, ())
        objects[SIDE_BRANCH] = (OLD_TREE, (OLD_MAIN,))
        objects[HOP1_MERGE] = (HOP1_TREE, (SIDE_ROOT, SIDE_BRANCH))
    if with_octopus:
        objects[TARGET_MAIN] = (TARGET_TREE, (HOP1_MERGE, HOP2_CANDIDATE, UNRELATED_ROOT))
        objects[UNRELATED_ROOT] = (OLD_TREE, ())
    return FixtureGitObserver(
        observed_main=observed_main,
        observed_tree=observed_tree,
        objects=objects,
        observe_sequence=observe_sequence,
    )


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_positive_bounded_catchup_advances_and_preserves_history(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology()
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_bounded_catchup(current, proof, topology, store=store)
    assert new_record.trusted_main == TARGET_MAIN
    assert new_record.trusted_tree == TARGET_TREE
    assert new_record.predecessor_main == OLD_MAIN
    assert new_record.predecessor_tree == OLD_TREE
    assert new_record.sequence == current.sequence + 1
    assert new_record.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CATCHUP
    # Truthfulness: merge_parent_1/2 are the final hop's ACTUAL git parents,
    # never forged to look like ordinary single-hop advancement.
    assert new_record.merge_parent_1 == HOP1_MERGE
    assert new_record.merge_parent_2 == HOP2_CANDIDATE
    history = (store / "history" / f"{current.sequence:08d}.json").read_text(encoding="utf-8")
    assert current.trusted_main in history
    current_on_disk = (store / "current.json").read_text(encoding="utf-8")
    assert TARGET_MAIN in current_on_disk


def test_cross_process_trust_reuse(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_bounded_catchup(current, proof, _topology(), store=store)
    reloaded = load_runtime_anchor(store=store)
    assert reloaded.model_dump(mode="json") == new_record.model_dump(mode="json")


def test_positive_hop_count_4_upper_boundary_succeeds(tmp_path: Path) -> None:
    """A real, full MAX_CATCHUP_HOPS (4) chain must succeed end-to-end
    through ``advance_via_bounded_catchup()`` -- the PR's original suite
    only exercised the 5-hop schema-rejection boundary and 2-hop positive
    paths, leaving the upper accepted boundary itself unproven (IV
    finding: independent review of this PR)."""
    current = _current_anchor()
    hop3 = _hop(
        merge_commit=NEXT_MAIN,
        merge_tree=NEXT_TREE,
        merge_parent_1=TARGET_MAIN,
        merge_parent_2=NEXT_CANDIDATE,
        candidate_head=NEXT_CANDIDATE,
        candidate_tree=NEXT_CANDIDATE_TREE,
        source_pr=700,
    )
    fourth_main = "9" * 39 + "b"
    fourth_tree = "9" * 39 + "c"
    fourth_candidate = "9" * 39 + "d"
    fourth_candidate_tree = "9" * 39 + "e"
    hop4 = _hop(
        merge_commit=fourth_main,
        merge_tree=fourth_tree,
        merge_parent_1=NEXT_MAIN,
        merge_parent_2=fourth_candidate,
        candidate_head=fourth_candidate,
        candidate_tree=fourth_candidate_tree,
        source_pr=701,
    )
    chain = [fourth_main, NEXT_MAIN, TARGET_MAIN, HOP1_MERGE, OLD_MAIN]
    topology = FixtureGitObserver(
        observed_main=fourth_main,
        observed_tree=fourth_tree,
        objects={
            OLD_MAIN: (OLD_TREE, ()),
            HOP1_CANDIDATE: (HOP1_CANDIDATE_TREE, ()),
            HOP1_MERGE: (HOP1_TREE, (OLD_MAIN, HOP1_CANDIDATE)),
            HOP2_CANDIDATE: (HOP2_CANDIDATE_TREE, ()),
            TARGET_MAIN: (TARGET_TREE, (HOP1_MERGE, HOP2_CANDIDATE)),
            NEXT_CANDIDATE: (NEXT_CANDIDATE_TREE, ()),
            NEXT_MAIN: (NEXT_TREE, (TARGET_MAIN, NEXT_CANDIDATE)),
            fourth_candidate: (fourth_candidate_tree, ()),
            fourth_main: (fourth_tree, (NEXT_MAIN, fourth_candidate)),
        },
    )
    proof = _proof(
        current,
        hops=(_hop1(), _hop2(), hop3, hop4),
        hop_count=4,
        target_main=fourth_main,
        target_tree=fourth_tree,
        chain_digest=_chain_digest(chain),
    )
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_bounded_catchup(current, proof, topology, store=store)
    assert new_record.trusted_main == fourth_main
    assert new_record.sequence == current.sequence + 1


def test_wrong_hop_merge_tree_denied(tmp_path: Path) -> None:
    """A hop's own ``merge_tree`` lying about what live topology actually
    reports for its ``merge_commit`` must be denied -- the PR's original
    suite only exercised the analogous lie on ``certified_candidate_tree``
    (IV finding: independent review of this PR)."""
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(merge_tree=WRONG_TREE), _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_evaluate_catchup_recovery_all_required_true_on_positive_path() -> None:
    current = _current_anchor()
    proof = _proof(current)
    checks = evaluate_catchup_recovery(
        current, proof, _topology(), observed_main=TARGET_MAIN, observed_tree=TARGET_TREE
    )
    assert isinstance(checks, CatchupChecks)
    assert checks.all_required is True


# ---------------------------------------------------------------------------
# A-Z: adversarial denial matrix
# ---------------------------------------------------------------------------


def test_a_no_owner_authorized_denied() -> None:
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, owner="NOT_AUTHORIZED")


def test_b_wrong_catchup_reason_denied() -> None:
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, reason="SOMETHING_ELSE")


def test_c_repository_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, identity="github.com/someone-else/other-repo")
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_d_expected_repository_identity_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(
            current,
            proof,
            _topology(),
            store=tmp_path / "store",
            expected_repository_identity="github.com/other/repo",
        )
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_e_expected_previous_main_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, expected_previous_main=OTHER_MAIN)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "PREDECESSOR_MISMATCH"


def test_f_expected_previous_tree_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, expected_previous_tree=WRONG_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_g_target_not_observed_main_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(observed_main=OTHER_MAIN, observed_tree=TARGET_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_h_target_tree_mismatch_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(observed_main=TARGET_MAIN, observed_tree=WRONG_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_i_single_hop_count_schema_rejected() -> None:
    """hop_count == 1 is exactly ordinary advance_trusted_anchor()'s job --
    catchup must never be usable as a routine substitute for it."""
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, hops=(_hop1(merge_commit=TARGET_MAIN, merge_tree=TARGET_TREE),))


def test_j_excessive_hop_count_schema_rejected() -> None:
    current = _current_anchor()
    too_many = tuple(
        _hop(
            merge_commit=str(index) * 40,
            merge_tree=str(index) * 40,
            merge_parent_1=OLD_MAIN,
            merge_parent_2=HOP1_CANDIDATE,
        )
        for index in range(2, 2 + MAX_CATCHUP_HOPS + 1)
    )
    with pytest.raises(ValidationError):
        TrustCatchupProof(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            owner_authorization="OWNER_AUTHORIZED",
            catchup_reason="BOUNDED_VERIFIED_TRUST_CATCHUP",
            expected_previous_main=current.trusted_main,
            expected_previous_tree=current.trusted_tree,
            target_main=TARGET_MAIN,
            target_tree=TARGET_TREE,
            hops=too_many,
            hop_count=len(too_many),
            first_parent_chain_digest="0" * 64,
            evidence_reference="tests/fixtures/catchup-proof.json",
            evidence_digest="0" * 64,
            source_package="AS-ORCH-AUTONOMY-001-DISCOVERY-TOPOLOGY",
            source_directive="D-ATLAS-BOUNDED-TRUST-CATCHUP-RECOVERY",
            source_pr=665,
            evidence_payload={},
        )


def test_k_hop_count_mismatch_with_hops_list_schema_rejected() -> None:
    current = _current_anchor()
    with pytest.raises(ValidationError):
        _proof(current, hop_count=3)


def test_l_non_first_parent_chain_denied(tmp_path: Path) -> None:
    """`git merge-base --is-ancestor` would say OLD_MAIN is reachable; a
    genuine first-parent walk must say no, so the independent-walk
    cross-check must deny even though every individual hop's OWN claimed
    parents match what the (side-branch-trapped) topology reports for it."""
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(with_side_branch_trap=True)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_m_missing_intermediate_hop_denied(tmp_path: Path) -> None:
    """A proof describing only the FIRST hop, then jumping straight to
    TARGET_MAIN, must be denied -- the second hop's real merge_parent_1
    (HOP1_MERGE) never matches what a single-hop chain would claim."""
    current = _current_anchor()
    # claims TARGET_MAIN's parent[0] is OLD_MAIN, not HOP1_MERGE
    bad_hop2 = _hop2(merge_parent_1=OLD_MAIN)
    proof = _proof(current, hops=(_hop1(), bad_hop2))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_n_reordered_hops_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop2(), _hop1()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_o_duplicate_hop_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(), _hop1()), hop_count=2)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_p_wrong_parent_0_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(merge_parent_1=OTHER_MAIN), _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_q_wrong_parent_1_denied(tmp_path: Path) -> None:
    # OLD_MAIN already exists in the topology, so this exercises the real
    # parents[1]-mismatch path rather than tripping GIT_OBJECT_MISSING on a
    # made-up candidate that was never a real commit.
    current = _current_anchor()
    decoy_hop1 = _hop1(merge_parent_2=OLD_MAIN, candidate_head=OLD_MAIN, candidate_tree=OLD_TREE)
    proof = _proof(current, hops=(decoy_hop1, _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_r_octopus_merge_denied(tmp_path: Path) -> None:
    """Exactly 2 parents required, not >= 2 -- same octopus-merge rationale
    as checkpoint recovery (PR #664 IV finding)."""
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(with_octopus=True)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_s_nonexistent_hop_merge_commit_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(merge_commit=MISSING), _hop2(merge_parent_1=MISSING)))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "GIT_OBJECT_MISSING"


def test_t_nonexistent_target_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, target_main=MISSING)
    topology = _topology(observed_main=MISSING, observed_tree=TARGET_TREE)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "GIT_OBJECT_MISSING"


def test_u_wrong_certified_candidate_schema_rejected() -> None:
    """``certified_candidate_head`` must equal ``merge_parent_2`` --
    enforced by ``CatchupHopProof``'s own model_validator, so a mismatch
    never even reaches ``advance_via_bounded_catchup``."""
    with pytest.raises(ValidationError):
        _hop1(candidate_head=OTHER_MAIN)


def test_v_wrong_candidate_tree_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(candidate_tree=WRONG_TREE), _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_w_tampered_chain_digest_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, chain_digest="f" * 64)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_x_tampered_overall_evidence_digest_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, digest="f" * 64)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_y_tampered_hop_evidence_digest_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    tampered_hop1 = _hop1(digest="f" * 64)
    proof = _proof(current, hops=(tampered_hop1, _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_z_proof_not_reusable_against_a_different_target_denied(tmp_path: Path) -> None:
    """Defense in depth: a legitimately-authorized proof for one target
    cannot simply have its ``target_main``/``target_tree`` swapped for a
    different one and still pass. In THIS scenario the independent hop-
    chain-to-target structural check (the hops still terminate at the OLD
    target) is what denies it, not evidence-digest binding specifically --
    ``test_x_tampered_overall_evidence_digest_denied`` is the test that
    isolates evidence-digest binding on its own (same target, same
    topology-valid chain, only the digest wrong). Both properties hold;
    each test proves a different one of them (IV finding: independent
    review of this PR sharpened this docstring after confirming the
    original "evidence-digest reuse" framing wasn't what was actually
    deciding this particular case)."""
    current = _current_anchor()
    legit = _proof(current)
    forged = legit.model_copy(update={"target_main": NEXT_MAIN, "target_tree": NEXT_TREE})
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE, with_next_hop=True)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, forged, topology, store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_hop_certified_candidate_bypassing_schema_validator_denied(tmp_path: Path) -> None:
    """``CatchupHopProof``'s own model_validator makes ``certified_candidate_
    head != merge_parent_2`` unconstructible through normal construction --
    but ``model_copy(update=...)`` does NOT re-run validators, so a hop
    built that way could slip an inconsistent value past the schema layer.
    ``_evaluate_catchup_chain`` must catch it anyway at runtime (reviewer
    finding, PR #666: relying on the schema validator alone is not
    load-bearing against every construction path)."""
    # Constructing TrustCatchupProof(hops=(bypassed_hop, ...)) normally
    # would actually re-validate the nested CatchupHopProof and reject it
    # right there -- Pydantic v2 revalidates nested BaseModel instances
    # embedded in a new model by default. The realistic bypass is
    # model_copy(update=...) on the OUTER proof itself (also skips all
    # validation, at every level, for the replaced field), so that's what
    # this test exercises to reach `_evaluate_catchup_chain` with a
    # genuinely inconsistent hop in hand.
    current = _current_anchor()
    legit = _proof(current)
    # OLD_MAIN (not OTHER_MAIN) so the pre-check `commit_exists` in
    # advance_via_bounded_catchup passes and this genuinely exercises the
    # `_evaluate_catchup_chain` runtime check, not an earlier existence gate.
    bypassed_hop1 = legit.hops[0].model_copy(update={"certified_candidate_head": OLD_MAIN})
    assert bypassed_hop1.certified_candidate_head != bypassed_hop1.merge_parent_2
    proof = legit.model_copy(update={"hops": (bypassed_hop1, legit.hops[1])})
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_hop_provenance_swap_invalidates_hop_digest(tmp_path: Path) -> None:
    """A hop's ``source_pr``/``source_package``/``source_directive``/
    ``evidence_reference`` -- persisted verbatim into the sealed trust
    record -- must be bound into its evidence_digest, so swapping which
    PR/directive/evidence a hop claims to be authorized by (while leaving
    every topology field untouched) invalidates the digest (P1 reviewer
    finding, PR #666)."""
    current = _current_anchor()
    legit_hop1 = _hop1()
    swapped = legit_hop1.model_copy(update={"source_pr": 999})
    assert verify_catchup_hop_evidence_integrity(swapped) is False
    proof = _proof(current, hops=(swapped, _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_proof_provenance_swap_invalidates_overall_digest(tmp_path: Path) -> None:
    """Same provenance-binding property at the whole-proof level (P1
    reviewer finding, PR #666)."""
    current = _current_anchor()
    legit = _proof(current)
    swapped = legit.model_copy(update={"source_directive": "D-SOMETHING-ELSE"})
    assert verify_catchup_evidence_integrity(swapped) is False
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, swapped, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_aa_hop_iv_fail_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(iv="FAIL"), _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_ab_hop_ci_fail_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(), _hop2(ci="FAIL")))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_ac_hop_seal_fail_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, hops=(_hop1(seal="FAIL"), _hop2()))
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=tmp_path / "store")
    assert exc.value.code == "CATCHUP_DENIED"


def test_ad_unauthorized_hop_basis_schema_rejected() -> None:
    with pytest.raises(ValidationError):
        _hop1(basis="MERGED_ONLY")


def test_ae_corrupt_store_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    store = tmp_path / "store"
    initialize_store(store, current)
    (store / "current.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(TrustError):
        advance_via_bounded_catchup(current, proof, _topology(), store=store)


def test_af_stale_concurrent_store_denied(tmp_path: Path) -> None:
    """A store whose persisted current record no longer matches the
    in-memory ``current`` passed in (someone else advanced it first) must
    fail closed, same CAS guarantee ordinary advancement already has."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)
    other_proof = _proof(current)
    concurrent_advance = advance_via_bounded_catchup(current, other_proof, _topology(), store=store)
    assert concurrent_advance.trusted_main == TARGET_MAIN
    # `current` (the stale, pre-advance snapshot) tries again with a fully
    # topology-VALID 3-hop proof reaching a further real target -- every
    # per-hop and chain check would pass; only the store-level CAS guard
    # (the store has already moved out from under this stale `current`)
    # must be what denies it.
    hop3 = _hop(
        merge_commit=NEXT_MAIN,
        merge_tree=NEXT_TREE,
        merge_parent_1=TARGET_MAIN,
        merge_parent_2=NEXT_CANDIDATE,
        candidate_head=NEXT_CANDIDATE,
        candidate_tree=NEXT_CANDIDATE_TREE,
        source_pr=700,
    )
    three_hop_chain = [NEXT_MAIN, TARGET_MAIN, HOP1_MERGE, OLD_MAIN]
    stale_retry_proof = _proof(
        current,
        hops=(_hop1(), _hop2(), hop3),
        hop_count=3,
        target_main=NEXT_MAIN,
        target_tree=NEXT_TREE,
        chain_digest=_chain_digest(three_hop_chain),
    )
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE, with_next_hop=True)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, stale_retry_proof, topology, store=store)
    assert exc.value.code == "ANCHOR_CAS_MISMATCH"


def test_ag_rollback_denied(tmp_path: Path) -> None:
    """Advancing back to the OLD predecessor's own predecessor must still
    be denied by ``compare_and_advance()``'s existing rollback guard --
    unchanged by this PR. Exercised directly against ``compare_and_advance``
    (shared, unmodified machinery both ordinary advancement and catch-up
    route through) rather than via a full catch-up chain, since
    constructing a genuinely topology-valid rollback chain is not the point
    of this test -- the guard itself is."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)
    forged = seal_anchor(
        current.model_copy(
            update={
                "trusted_main": current.predecessor_main,
                "trusted_tree": current.predecessor_tree,
                "predecessor_main": current.trusted_main,
                "predecessor_tree": current.trusted_tree,
                "merge_commit": current.predecessor_main,
                "merge_tree": current.predecessor_tree,
                "advancement_reason": AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CATCHUP,
                "sequence": current.sequence + 1,
                "record_digest": "00" * 32,
            }
        )
    )
    with pytest.raises(TrustError) as exc:
        compare_and_advance(store, current, forged)
    assert exc.value.code == "ROLLBACK_FORBIDDEN"


def test_ah_cross_process_replay_of_same_proof_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    store = tmp_path / "store"
    initialize_store(store, current)
    advance_via_bounded_catchup(current, proof, _topology(), store=store)
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, _topology(), store=store)
    assert exc.value.code == "ANCHOR_CAS_MISMATCH"


def test_ai_target_moved_during_verification_denied(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current)
    topology = _topology(
        observe_sequence=(
            (TARGET_MAIN, TARGET_TREE),
            (NEXT_MAIN, NEXT_TREE),
        )
    )
    with pytest.raises(TrustError) as exc:
        advance_via_bounded_catchup(current, proof, topology, store=tmp_path / "store")
    assert exc.value.code == "TARGET_MOVED_DURING_VERIFICATION"


def test_aj_empty_evidence_payload_still_requires_correct_digest(tmp_path: Path) -> None:
    current = _current_anchor()
    proof = _proof(current, payload={})
    store = tmp_path / "store"
    initialize_store(store, current)
    new_record = advance_via_bounded_catchup(current, proof, _topology(), store=store)
    assert new_record.trusted_main == TARGET_MAIN


# ---------------------------------------------------------------------------
# Invariant regressions: catch-up must never weaken sibling mechanisms
# ---------------------------------------------------------------------------


def test_normal_single_hop_advancement_unchanged(tmp_path: Path) -> None:
    """`advance_trusted_anchor()` still requires proof.merge_commit to be
    the exact observed live main and proof.merge_parent_1 to equal
    current.trusted_main -- byte-for-byte the same strict single-hop
    behavior as before this PR existed."""
    current = _current_anchor(main=OLD_MAIN, tree=OLD_TREE)
    store = tmp_path / "store"
    initialize_store(store, current)
    # A genuine fast-forward-content merge (merge_tree == candidate's own
    # tree), the same shape ordinary advancement's own checks require and
    # the same shape PR #665's real merge had -- distinct from this file's
    # shared `_topology()` fixture, whose HOP1_MERGE intentionally has a
    # tree DIFFERENT from HOP1_CANDIDATE's (so per-hop catch-up evidence is
    # exercised against a realistic non-ff merge shape too).
    ff_topology = FixtureGitObserver(
        observed_main=HOP1_MERGE,
        observed_tree=HOP1_CANDIDATE_TREE,
        objects={
            OLD_MAIN: (OLD_TREE, ()),
            HOP1_CANDIDATE: (HOP1_CANDIDATE_TREE, ()),
            HOP1_MERGE: (HOP1_CANDIDATE_TREE, (OLD_MAIN, HOP1_CANDIDATE)),
        },
    )
    draft_proof = AdvancementProof(
        schema_version=1,
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        owner_authorization="OWNER_AUTHORIZED",
        expected_previous_main=OLD_MAIN,
        expected_previous_tree=OLD_TREE,
        authorized_candidate_head=HOP1_CANDIDATE,
        authorized_candidate_tree=HOP1_CANDIDATE_TREE,
        merge_commit=HOP1_MERGE,
        merge_parent_1=OLD_MAIN,
        merge_parent_2=HOP1_CANDIDATE,
        merge_tree=HOP1_CANDIDATE_TREE,
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        evidence_reference="tests/fixtures/ordinary.json",
        evidence_digest="0" * 64,
        source_package="AS-ORCH-AUTONOMY-001-DISCOVERY-TOPOLOGY",
        source_directive="D-ATLAS-BOUNDED-TRUST-CATCHUP-RECOVERY",
        source_pr=665,
        evidence_payload={"kind": "ORDINARY"},
    )
    ordinary_proof = draft_proof.model_copy(
        update={"evidence_digest": hash_payload(_advancement_evidence_binding(draft_proof))}
    )
    new_record = advance_trusted_anchor(current, ordinary_proof, ff_topology, store=store)
    assert new_record.trusted_main == HOP1_MERGE
    assert new_record.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE
    # And it still correctly REJECTS a proof whose target isn't live main --
    # exactly the failure mode that made this whole PR necessary.
    stale_proof = ordinary_proof.model_copy(
        update={
            "expected_previous_main": HOP1_MERGE,
            "expected_previous_tree": HOP1_CANDIDATE_TREE,
            "merge_parent_1": HOP1_MERGE,
        }
    )
    with pytest.raises(TrustError):
        advance_trusted_anchor(new_record, stale_proof, ff_topology, store=store)


def test_one_time_checkpoint_gate_unaffected_by_catchup_module_presence(tmp_path: Path) -> None:
    """Merely having ``advance_via_bounded_catchup`` importable/used in the
    same process must never affect ``_checkpoint_already_used()``'s
    behavior -- it inspects only the store, never any catchup call state."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)
    assert _checkpoint_already_used(store) is False
    # Use catchup once.
    advance_via_bounded_catchup(current, _proof(current), _topology(), store=store)
    # Checkpoint recovery's one-time gate is completely independent of
    # catchup usage: it only ever flips to "used" via an actual checkpoint
    # record, never a catchup one.
    assert _checkpoint_already_used(store) is False


def test_checkpoint_recovery_still_one_time_after_catchup_capability_exists(tmp_path: Path) -> None:
    """A store that HAS already used checkpoint recovery must still reject
    a second one -- verbatim the same regression PR #664 already proved,
    re-run here to prove this PR's additions did not touch it."""
    current = _current_anchor()
    store = tmp_path / "store"
    initialize_store(store, current)
    checkpoint_proof = TrustCheckpointProof(
        schema_version=1,
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        owner_authorization="OWNER_AUTHORIZED",
        checkpoint_reason="STALE_RUNTIME_ANCHOR_RECOVERY",
        expected_previous_main=OLD_MAIN,
        expected_previous_tree=OLD_TREE,
        target_main=TARGET_MAIN,
        target_tree=TARGET_TREE,
        target_merge_parent_1=HOP1_MERGE,
        target_merge_parent_2=HOP2_CANDIDATE,
        certified_candidate_head=HOP2_CANDIDATE,
        certified_candidate_tree=HOP2_CANDIDATE_TREE,
        first_parent_hop_count=HOP_COUNT,
        first_parent_chain_digest=CHAIN_DIGEST,
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        independent_verification="PASS",
        evidence_reference="tests/fixtures/checkpoint.json",
        evidence_digest="0" * 64,
        source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
        source_directive="D-AUTONOMY-PIN-RETARGET-003",
        source_pr=2,
        evidence_payload={"kind": "OWNER_CHECKPOINT_RECERTIFICATION"},
    )
    from project_atlas.orchestration.autonomy.trust import _checkpoint_evidence_binding

    checkpoint_proof = checkpoint_proof.model_copy(
        update={"evidence_digest": hash_payload(_checkpoint_evidence_binding(checkpoint_proof))}
    )
    first = advance_via_checkpoint_recovery(current, checkpoint_proof, _topology(), store=store)
    assert first.advancement_reason == AdvancementReason.VERIFIED_OWNER_AUTHORIZED_CHECKPOINT
    assert _checkpoint_already_used(store) is True
    second_attempt_proof = checkpoint_proof.model_copy(
        update={
            "expected_previous_main": first.trusted_main,
            "expected_previous_tree": first.trusted_tree,
            "target_main": NEXT_MAIN,
            "target_tree": NEXT_TREE,
            "target_merge_parent_1": TARGET_MAIN,
            "target_merge_parent_2": NEXT_CANDIDATE,
            "certified_candidate_head": NEXT_CANDIDATE,
        }
    )
    with pytest.raises(TrustError) as exc:
        advance_via_checkpoint_recovery(first, second_attempt_proof, _topology(), store=store)
    assert exc.value.code == "CHECKPOINT_ALREADY_USED"


def test_catchup_never_calls_checkpoint_gate() -> None:
    """Bytecode-level guarantee: ``advance_via_bounded_catchup`` never
    NAME-REFERENCES ``_checkpoint_already_used`` -- checked via
    ``__code__.co_names`` (compiled name lookups only, immune to the
    function's own docstring prose about the gate), so a future edit that
    added a real call would fail this test immediately."""
    from project_atlas.orchestration.autonomy import trust as trust_module

    names = trust_module.advance_via_bounded_catchup.__code__.co_names
    assert "_checkpoint_already_used" not in names


def test_evidence_bindings_are_distinct_between_hop_and_overall() -> None:
    """A hop's own evidence_digest and the proof's overall evidence_digest
    must bind to different structures -- lifting one onto the other's slot
    must not accidentally verify."""
    current = _current_anchor()
    proof = _proof(current)
    hop = proof.hops[0]
    assert verify_catchup_hop_evidence_integrity(hop) is True
    assert verify_catchup_evidence_integrity(proof) is True
    swapped_hop = hop.model_copy(update={"evidence_digest": proof.evidence_digest})
    assert verify_catchup_hop_evidence_integrity(swapped_hop) is False
