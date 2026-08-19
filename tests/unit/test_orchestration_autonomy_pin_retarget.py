"""AS-ORCH-AUTONOMY-001-PIN-RETARGET trusted-anchor matrices and adversarial cases."""

from __future__ import annotations

import inspect
import json
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.autonomy.discovery import discover
from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor, GovernorError
from project_atlas.orchestration.autonomy.models import (
    BOOTSTRAP_MAIN,
    BOOTSTRAP_TREE,
    CANONICAL_REPOSITORY_IDENTITY,
    INITIAL_RETARGET_CERTIFIED_HEAD,
    INITIAL_RETARGET_MAIN,
    INITIAL_RETARGET_TREE,
    AdvancementProof,
    AdvancementReason,
    LiveInventory,
    TrustedAnchorRecord,
    TrustState,
)
from project_atlas.orchestration.autonomy.trust import (
    FixtureGitObserver,
    TrustError,
    advance_trusted_anchor,
    build_initial_retarget_record,
    classify_observation,
    compare_and_advance,
    evaluate_target_moved,
    initialize_store,
    load_runtime_anchor,
    load_shipped_initial_anchor,
    normalize_repository_identity,
    require_full_pin,
    seal_anchor,
    verify_anchor_integrity,
)
from project_atlas.schema import validate_record

OLD_MAIN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OLD_TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
NEW_HEAD = "cccccccccccccccccccccccccccccccccccccccc"
NEW_TREE = "dddddddddddddddddddddddddddddddddddddddd"
NEW_MERGE = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
OTHER_MAIN = "ffffffffffffffffffffffffffffffffffffffff"
OTHER_TREE = "1234567890abcdef1234567890abcdef12345678"
MISSING = "9999999999999999999999999999999999999999"


def _inventory(main: str, tree: str) -> LiveInventory:
    return LiveInventory(
        current_main=main,
        current_tree=tree,
        worktree_status="CLEAN",
        open_relevant_prs=(),
        active_successor_packages=(),
        r2_created="NO",
        r7_created="NO",
        authentic_r6_resumed="NO",
        as_orch_001e_started="NO",
        pr396_mutated="NO",
    )


def _anchor(
    *,
    main: str,
    tree: str,
    predecessor_main: str = OLD_MAIN,
    predecessor_tree: str = OLD_TREE,
    certified_head: str = NEW_HEAD,
    certified_tree: str | None = None,
    sequence: int = 1,
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
) -> TrustedAnchorRecord:
    certified = certified_tree if certified_tree is not None else tree
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=identity,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=predecessor_main,
            predecessor_tree=predecessor_tree,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-AUTONOMY-PIN-RETARGET-003",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=predecessor_main,
            merge_parent_2=certified_head,
            merge_tree=tree,
            certified_head=certified_head,
            certified_tree=certified,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/pin-retarget.json",
            evidence_digest="ab" * 32,
            sequence=sequence,
            record_digest="00" * 32,
        )
    )


def _payload() -> dict[str, object]:
    return {"kind": "OWNER_MERGE_EVIDENCE", "pr": 1, "seal": "PASS"}


def _proof(
    current: TrustedAnchorRecord,
    *,
    merge_commit: str = NEW_MERGE,
    merge_tree: str = NEW_TREE,
    head: str = NEW_HEAD,
    head_tree: str = NEW_TREE,
    parent_1: str | None = None,
    parent_2: str | None = None,
    seal: str = "PASS",
    ci: str = "PASS",
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
    payload: dict[str, object] | None = None,
    digest: str | None = None,
) -> AdvancementProof:
    evidence = payload if payload is not None else _payload()
    return AdvancementProof(
        repository_identity=identity,
        owner_authorization="OWNER_AUTHORIZED",
        expected_previous_main=current.trusted_main,
        expected_previous_tree=current.trusted_tree,
        authorized_candidate_head=head,
        authorized_candidate_tree=head_tree,
        merge_commit=merge_commit,
        merge_parent_1=parent_1 or current.trusted_main,
        merge_parent_2=parent_2 or head,
        merge_tree=merge_tree,
        post_merge_seal=seal,  # type: ignore[arg-type]
        post_merge_ci=ci,  # type: ignore[arg-type]
        evidence_reference="tests/fixtures/pin-retarget-proof.json",
        evidence_digest=digest or hash_payload(evidence),
        source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
        source_directive="D-AUTONOMY-PIN-RETARGET-003",
        source_pr=2,
        evidence_payload=evidence,
    )


def _future_topology(
    *,
    observed_main: str = NEW_MERGE,
    observed_tree: str = NEW_TREE,
    observe_sequence: tuple[tuple[str, str], ...] | None = None,
    include_merge: bool = True,
) -> FixtureGitObserver:
    objects: dict[str, tuple[str, tuple[str, ...]]] = {
        OLD_MAIN: (OLD_TREE, ()),
        NEW_HEAD: (NEW_TREE, ()),
    }
    if include_merge:
        objects[NEW_MERGE] = (NEW_TREE, (OLD_MAIN, NEW_HEAD))
    return FixtureGitObserver(
        observed_main=observed_main,
        observed_tree=observed_tree,
        objects=objects,
        observe_sequence=observe_sequence,
    )


def test_cold_start_without_authority_fails_closed() -> None:
    with pytest.raises(TrustError, match="no trust record") as exc:
        load_runtime_anchor()
    assert exc.value.code == "TRUST_UNVERIFIABLE"


def test_missing_store_does_not_fall_back_to_compile_time_or_main(tmp_path: Path) -> None:
    with pytest.raises(TrustError) as exc:
        load_runtime_anchor(store=tmp_path / "empty-store")
    assert exc.value.code == "TRUST_UNVERIFIABLE"
    with pytest.raises(TrustError):
        load_runtime_anchor(store=tmp_path / "empty-store", allow_shipped=True)


def test_malformed_store_record_is_unverifiable(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    (store / "current.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(TrustError) as exc:
        load_runtime_anchor(store=store)
    assert exc.value.code == "TRUST_UNVERIFIABLE"


def test_case_1_origin_main_changed_without_authorization() -> None:
    trusted = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    observed = OTHER_MAIN
    assert evaluate_target_moved(observed, OTHER_TREE, trusted) is True
    assert classify_observation(observed, OTHER_TREE, trusted, descendant_of_trusted=True) is (
        TrustState.TARGET_MOVED
    )
    report = discover(_inventory(observed, OTHER_TREE), trusted=trusted)
    assert report.case == "A-B"
    assert report.blocker == "TARGET_MOVED"
    gov = AutonomousGovernor(
        current_main=observed,
        current_tree=OTHER_TREE,
        trusted_anchor=trusted,
    )
    with pytest.raises(GovernorError) as exc:
        gov.lease("nope", "governor-pilot-local", branch="feat/x", worktree="repo")
    assert exc.value.code == "TARGET_MOVED"


def test_case_2_wrong_previous_main_parent() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, parent_1=OTHER_MAIN)
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_3_wrong_certified_candidate_head() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, head=OTHER_MAIN)
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_4_wrong_certified_candidate_tree() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, head_tree=OTHER_TREE)
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_5_merge_tree_mismatch() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, merge_tree=OTHER_TREE)
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_6_missing_owner_authorization() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    payload = _proof(current).model_dump(mode="json")
    payload.pop("owner_authorization")
    with pytest.raises(ValidationError):
        AdvancementProof.model_validate(payload)


def test_case_7_failed_post_merge_seal() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, seal="FAIL")
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_8_failed_required_post_merge_ci() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, ci="FAIL")
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_9_malformed_anchor_record() -> None:
    with pytest.raises(ValidationError):
        TrustedAnchorRecord.model_validate({"schema_version": 1, "trusted_main": "main"})


def test_case_10_tampered_evidence_digest() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, digest="ff" * 32)
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, proof, _future_topology())


def test_case_11_stale_advancement_record(tmp_path: Path) -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, current)
    proof = _proof(current)
    first = advance_trusted_anchor(current, proof, _future_topology(), store=tmp_path)
    assert first.trusted_main == NEW_MERGE
    with pytest.raises(TrustError) as exc:
        advance_trusted_anchor(first, proof, _future_topology(), store=tmp_path)
    assert exc.value.code in {"PREDECESSOR_MISMATCH", "ADVANCEMENT_DENIED"}


def test_case_12_concurrent_advancement_attempt(tmp_path: Path) -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, current)
    next_record = advance_trusted_anchor(current, _proof(current), _future_topology())
    errors: list[str] = []
    results: list[str] = []

    def _writer() -> None:
        try:
            advanced = compare_and_advance(tmp_path, current, next_record)
            results.append(advanced.record_digest)
        except TrustError as exc:
            errors.append(exc.code)

    threads = [threading.Thread(target=_writer) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 1
    assert errors
    assert set(errors) <= {
        "ANCHOR_CAS_MISMATCH",
        "CONCURRENT_ADVANCE",
        "TRUST_ANCHOR_HISTORY_REWRITTEN",
    }


def test_case_13_main_changes_during_verification() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    topology = _future_topology(
        observe_sequence=((NEW_MERGE, NEW_TREE), (OTHER_MAIN, OTHER_TREE)),
    )
    with pytest.raises(TrustError) as exc:
        advance_trusted_anchor(current, _proof(current), topology)
    assert exc.value.code == "TARGET_MOVED_DURING_VERIFICATION"


def test_case_14_record_references_nonexistent_git_object() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    with pytest.raises(TrustError) as exc:
        advance_trusted_anchor(
            current,
            _proof(current),
            _future_topology(include_merge=False, observed_main=NEW_MERGE, observed_tree=NEW_TREE),
        )
    assert exc.value.code == "GIT_OBJECT_MISSING"


def test_case_15_descendant_only_is_not_authority() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    topology = _future_topology()
    assert topology.is_descendant(NEW_MERGE, OLD_MAIN) is True
    state = classify_observation(
        NEW_MERGE,
        NEW_TREE,
        current,
        descendant_of_trusted=topology.is_descendant(NEW_MERGE, OLD_MAIN),
    )
    assert state is TrustState.TARGET_MOVED
    report = discover(_inventory(NEW_MERGE, NEW_TREE), trusted=current)
    assert report.blocker == "TARGET_MOVED"


def test_positive_a_pr398_transition() -> None:
    current = _anchor(
        main=BOOTSTRAP_MAIN,
        tree=BOOTSTRAP_TREE,
        predecessor_main=MISSING,
        certified_head=INITIAL_RETARGET_CERTIFIED_HEAD,
        certified_tree=INITIAL_RETARGET_TREE,
    )
    payload = {"kind": "OWNER_MERGE_GATE_002", "pr": 398}
    proof = AdvancementProof(
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        owner_authorization="OWNER_AUTHORIZED",
        expected_previous_main=BOOTSTRAP_MAIN,
        expected_previous_tree=BOOTSTRAP_TREE,
        authorized_candidate_head=INITIAL_RETARGET_CERTIFIED_HEAD,
        authorized_candidate_tree=INITIAL_RETARGET_TREE,
        merge_commit=INITIAL_RETARGET_MAIN,
        merge_parent_1=BOOTSTRAP_MAIN,
        merge_parent_2=INITIAL_RETARGET_CERTIFIED_HEAD,
        merge_tree=INITIAL_RETARGET_TREE,
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        evidence_reference="as-orch-autonomy-001-merge-002/FINAL_REPORT.md",
        evidence_digest=hash_payload(payload),
        source_package="AS-ORCH-AUTONOMY-001",
        source_directive="D-AUTONOMY-OWNER-MERGE-GATE-002",
        source_pr=398,
        evidence_payload=payload,
    )
    topology = FixtureGitObserver(
        observed_main=INITIAL_RETARGET_MAIN,
        observed_tree=INITIAL_RETARGET_TREE,
        objects={
            BOOTSTRAP_MAIN: (BOOTSTRAP_TREE, ()),
            INITIAL_RETARGET_CERTIFIED_HEAD: (INITIAL_RETARGET_TREE, ()),
            INITIAL_RETARGET_MAIN: (
                INITIAL_RETARGET_TREE,
                (BOOTSTRAP_MAIN, INITIAL_RETARGET_CERTIFIED_HEAD),
            ),
        },
    )
    advanced = advance_trusted_anchor(current, proof, topology)
    assert advanced.trusted_main == INITIAL_RETARGET_MAIN
    assert advanced.trusted_tree == INITIAL_RETARGET_TREE
    assert advanced.certified_head == INITIAL_RETARGET_CERTIFIED_HEAD
    assert advanced.trusted_main != advanced.certified_head
    assert advanced.trusted_tree == advanced.certified_tree
    assert advanced.predecessor_main == BOOTSTRAP_MAIN


def test_positive_b_unchanged_runtime_is_not_moved() -> None:
    trusted = load_shipped_initial_anchor()
    assert evaluate_target_moved(INITIAL_RETARGET_MAIN, INITIAL_RETARGET_TREE, trusted) is False
    report = discover(_inventory(INITIAL_RETARGET_MAIN, INITIAL_RETARGET_TREE), trusted=trusted)
    assert report.case == "A-A-PREFLIGHT"
    assert report.target_moved is False
    assert report.selected_package_id is None
    assert report.blocker == "OWNER_GATE"
    gov = AutonomousGovernor(
        current_main=INITIAL_RETARGET_MAIN,
        current_tree=INITIAL_RETARGET_TREE,
        trusted_anchor=trusted,
    )
    assert gov.snapshot().target_moved is False
    assert gov.snapshot().trust_state is TrustState.TRUSTED


def test_positive_c_disposable_future_valid_advancement(tmp_path: Path) -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, current)
    advanced = advance_trusted_anchor(
        current,
        _proof(current),
        _future_topology(),
        store=tmp_path,
    )
    assert advanced.trusted_main == NEW_MERGE
    assert advanced.predecessor_main == OLD_MAIN
    assert advanced.sequence == current.sequence + 1
    reloaded = load_runtime_anchor(store=tmp_path)
    assert reloaded.record_digest == advanced.record_digest
    assert (tmp_path / "history" / "00000001.json").is_file()


def test_shipped_record_is_evidence_based_not_live_main() -> None:
    shipped = load_shipped_initial_anchor()
    built = build_initial_retarget_record()
    assert shipped.model_dump(mode="json") == built.model_dump(mode="json")
    validate_record(shipped, "autonomy-trusted-anchor")
    assert shipped.trusted_main == INITIAL_RETARGET_MAIN
    assert shipped.source_pr == 398
    assert shipped.source_directive == "D-AUTONOMY-OWNER-MERGE-GATE-002"
    assert inspect.signature(build_initial_retarget_record).parameters == {}


def test_governor_cannot_invent_owner_authority() -> None:
    import project_atlas.orchestration.autonomy.trust as trust_mod

    names = {name for name, _ in inspect.getmembers(trust_mod, inspect.isfunction)}
    forbidden = {
        "proof_from_observed_main",
        "invent_owner_authority",
        "advance_from_observed_main",
        "authorize_from_origin_main",
    }
    assert names.isdisjoint(forbidden)
    assert "owner_authorization" not in inspect.signature(advance_trusted_anchor).parameters


def test_abbreviated_sha_rejected() -> None:
    with pytest.raises(TrustError) as exc:
        require_full_pin("62f8d59f", "abbrev")
    assert exc.value.code == "PIN_INVALID"
    with pytest.raises(ValidationError):
        TrustedAnchorRecord.model_validate(
            build_initial_retarget_record().model_dump(mode="json") | {"trusted_main": "62f8d59"}
        )


def test_branch_name_is_not_a_pin() -> None:
    with pytest.raises(ValidationError):
        TrustedAnchorRecord.model_validate(
            build_initial_retarget_record().model_dump(mode="json") | {"trusted_main": "main"}
        )


def test_path_escape_and_history_rewrite_fail_closed(tmp_path: Path) -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, current)
    history = tmp_path / "history" / "00000001.json"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text("{}", encoding="utf-8")
    nxt = advance_trusted_anchor(current, _proof(current), _future_topology())
    with pytest.raises(TrustError) as exc:
        compare_and_advance(tmp_path, current, nxt)
    assert exc.value.code == "TRUST_ANCHOR_HISTORY_REWRITTEN"


def test_cross_repository_reuse_rejected() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    proof = _proof(current, identity="github.com/other/repo")
    with pytest.raises(TrustError) as exc:
        advance_trusted_anchor(current, proof, _future_topology())
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_identity_mismatch_on_load() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    with pytest.raises(TrustError) as exc:
        load_runtime_anchor(
            explicit=current,
            expected_repository_identity="github.com/other/repo",
        )
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_rollback_and_downgrade_forbidden(tmp_path: Path) -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, current)
    advanced = advance_trusted_anchor(current, _proof(current), _future_topology(), store=tmp_path)
    rollback = _anchor(
        main=OLD_MAIN,
        tree=OLD_TREE,
        predecessor_main=NEW_MERGE,
        predecessor_tree=NEW_TREE,
        sequence=advanced.sequence + 1,
    )
    with pytest.raises(TrustError) as exc:
        compare_and_advance(tmp_path, advanced, rollback)
    assert exc.value.code == "ROLLBACK_FORBIDDEN"
    downgrade = seal_anchor(
        advanced.model_copy(
            update={
                "sequence": 1,
                "predecessor_main": advanced.trusted_main,
                "predecessor_tree": advanced.trusted_tree,
                "record_digest": "00" * 32,
            }
        )
    )
    with pytest.raises(TrustError) as exc2:
        compare_and_advance(tmp_path, advanced, downgrade)
    assert exc2.value.code == "DOWNGRADE_FORBIDDEN"


def test_conflicting_initialize_does_not_overwrite(tmp_path: Path) -> None:
    first = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    initialize_store(tmp_path, first)
    other = _anchor(main=NEW_MERGE, tree=NEW_TREE, predecessor_main=OLD_MAIN)
    with pytest.raises(TrustError) as exc:
        initialize_store(tmp_path, other)
    assert exc.value.code == "BLOCKED"


def test_tampered_record_digest_is_hash_invalid() -> None:
    record = build_initial_retarget_record()
    tampered = record.model_copy(update={"record_digest": "ee" * 32})
    with pytest.raises(TrustError) as exc:
        verify_anchor_integrity(tampered)
    assert exc.value.code == "HASH_INVALID"


def test_repository_identity_normalization() -> None:
    assert normalize_repository_identity("https://github.com/B0LK13/project-atlas.git") == (
        "github.com/b0lk13/project-atlas"
    )
    with pytest.raises(TrustError):
        normalize_repository_identity("https://github.com/../escape")


def test_shipped_schema_and_no_wall_clock() -> None:
    record = load_shipped_initial_anchor()
    dumped = json.dumps(record.model_dump(mode="json"))
    assert "generated.at" not in dumped
    assert "record_created_at" not in dumped
    validate_record(record, "autonomy-trusted-anchor")


def test_forged_owner_receipt_without_matching_evidence_fails() -> None:
    current = _anchor(main=OLD_MAIN, tree=OLD_TREE, predecessor_main=MISSING)
    forged = _proof(current, payload={"kind": "I_AM_OWNER"}, digest=hash_payload({"kind": "REAL"}))
    with pytest.raises(TrustError):
        advance_trusted_anchor(current, forged, _future_topology())
