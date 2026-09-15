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

import subprocess
from pathlib import Path

from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.orchestration.origination.cli import EXIT_OK, run_origination_scan
from project_atlas.orchestration.origination.identity import work_id_for
from project_atlas.orchestration.origination.pipeline import originate_all
from project_atlas.orchestration.origination.projection import (
    list_materialized_work_nodes,
    load_projection,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The real, actual trusted-main commit before PR #675 added INT-013's
#: EXTERNAL_BLOCKED continuation line to docs/backlog.md -- verified
#: empirically (git show) to carry NO blocker text on that line. Used
#: below as real, historical repository content, never fabricated.
_PRE_675_COMMIT = "e8f4a0234a92cb034fdd2bcdd5c367adfe6c6907"


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


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def _ensure_commit_available(commit: str) -> None:
    """Real-IV finding (PR #675): CI's own checkout is shallow
    (``actions/checkout``'s default ``fetch-depth: 1``, unchanged by
    this test module -- deliberately not widened repo-wide just for one
    test's own need), so a real historical commit like
    ``_PRE_675_COMMIT`` is genuinely absent from CI's local object
    database even though it is present in every worktree used to author
    and run this test locally. Self-heal: fetch exactly this one commit
    (a no-op, and cheap, when it is already present -- the common local
    case) rather than widen CI's checkout depth for every job and every
    other test. Never raises for a fetch that fails for a reason other
    than "commit already present" here -- the subsequent ``git show``
    call is the real, load-bearing assertion; this is best-effort
    self-healing for the one known shallow-checkout gap, not a new
    fail-closed boundary of its own.
    """
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        return  # already present -- the common local-worktree case
    except subprocess.CalledProcessError:
        pass
    subprocess.run(
        ["git", "fetch", "--quiet", "--depth", "1", "origin", commit],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )


def _real_anchor(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main="a" * 40,
            predecessor_tree="b" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORIGIN-MATERIALIZED-SUPERSESSION-001-TEST",
            source_directive="D-ATLAS-PR677-REVISION-IDENTITY-BINDING-FINALIZATION-TEST-FIXTURE",
            source_pr=675,
            merge_commit=main,
            merge_parent_1="a" * 40,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/int013-persisted-state.json",
            evidence_digest="cd" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def test_int013_persisted_materialized_revision_supersedes_and_becomes_non_rehydratable(
    tmp_path: Path,
) -> None:
    """Owner directive D-ATLAS-PR677-REVISION-IDENTITY-BINDING-FINALIZATION
    §4: prove the real PERSISTED-STATE transition, not merely a fresh
    ``originate_all()`` call -- MATERIALIZED -> SUPERSEDED ->
    non-rehydratable -- using the REAL, supported reconciler
    (``run_origination_scan()`` -> ``reconcile_revision()``), never
    hand-edited state, against this repository's OWN real, historical
    ``docs/backlog.md`` content (before PR #675's EXTERNAL_BLOCKED line
    existed) followed by its real, current content (after).

    Real content, throwaway repo: this repository's actual origination-
    relevant files (project marker, backlog.md, the INT-013 acceptance
    contract, its evidence test file) are copied byte-for-byte -- via
    ``git show`` for the pre-#675 backlog.md revision, directly from disk
    for everything else (identical on both sides of #675) -- into a
    fresh, self-contained git repo, exactly this test module's own
    established real-content convention, extended to also exercise a
    second, later revision the live checkout alone cannot represent
    (its own history has already moved past the "before" state).
    """
    _ensure_commit_available(_PRE_675_COMMIT)
    old_backlog = _run_git("show", f"{_PRE_675_COMMIT}:docs/backlog.md")
    assert "- [ ] INT-013 Run the bounded multi-project integration pilot" in old_backlog
    assert (
        "EXTERNAL_BLOCKED" not in old_backlog.split("- [ ] INT-013", 1)[1].split("\n\n", 1)[0]
    ), "the pre-#675 commit's own INT-013 line must genuinely carry no blocker text"

    current_backlog = (REPO_ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    assert "EXTERNAL_BLOCKED" in current_backlog.split("- [ ] INT-013", 1)[1].split(")", 1)[0]

    project_marker = (REPO_ROOT / ".atlas-project.yaml").read_text(encoding="utf-8")
    contracts_yaml = (REPO_ROOT / "docs" / "origination-acceptance-contracts.yaml").read_text(
        encoding="utf-8"
    )
    evidence_test = (
        REPO_ROOT / "tests" / "integration" / "test_int_013_bounded_multi_project_pilot.py"
    ).read_text(encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".atlas-project.yaml").write_text(project_marker, encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "origination-acceptance-contracts.yaml").write_text(
        contracts_yaml, encoding="utf-8"
    )
    (repo / "tests" / "integration").mkdir(parents=True)
    (repo / "tests" / "integration" / "test_int_013_bounded_multi_project_pilot.py").write_text(
        evidence_test, encoding="utf-8"
    )
    (repo / "docs" / "backlog.md").write_text(old_backlog, encoding="utf-8")

    def _run_git_repo(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    _run_git_repo("init", "-q")
    _run_git_repo("config", "user.email", "test@example.com")
    _run_git_repo("config", "user.name", "Test")
    _run_git_repo("add", "-A")
    _run_git_repo("commit", "-q", "-m", "pre-675 state")
    sha = _run_git_repo("rev-parse", "HEAD")
    _run_git_repo("update-ref", "refs/remotes/origin/main", sha)

    main = _run_git_repo("rev-parse", "origin/main")
    tree = _run_git_repo("rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    first_payload, first_exit = run_origination_scan(
        root=repo,
        project_id="project-atlas",
        origination_store=store,
        explicit_trusted=_real_anchor(main, tree),
    )
    assert first_exit == EXIT_OK
    # The real docs/backlog.md carries other, unrelated real items too
    # (bounded but not INT-013-only) -- filter to the one this test is
    # about, exactly this test module's own `_int013_outcome()`
    # convention above, rather than assume INT-013 is the sole item.
    work_id = work_id_for("project-atlas", "INT-013")
    first_materialized = {
        entry["work_id"]: entry  # type: ignore[index]
        for entry in first_payload["materialized"]  # type: ignore[union-attr]
    }
    assert work_id in first_materialized, (
        f"INT-013 (work_id={work_id!r}) must materialize from the real pre-#675 "
        f"backlog.md content; got {sorted(first_materialized)!r}"
    )
    old_identity = next(
        r.origination_identity
        for r in load_projection(store).records
        if r.work_node is not None and r.work_node.get("package_id") == work_id
    )

    # OLD_INT013_REVISION = MATERIALIZED, real and rehydratable right now.
    active_before = list_materialized_work_nodes(store)
    assert any(n.package_id == work_id for n in active_before)

    # Overlay this repo's REAL, current (post-#675) docs/backlog.md --
    # the actual authoritative-source change that happened for real.
    (repo / "docs" / "backlog.md").write_text(current_backlog, encoding="utf-8")

    second_payload, second_exit = run_origination_scan(
        root=repo,
        project_id="project-atlas",
        origination_store=store,
        explicit_trusted=_real_anchor(main, tree),
    )
    assert second_exit == EXIT_OK
    second_materialized_ids = {
        entry["work_id"]  # type: ignore[index]
        for entry in second_payload["materialized"]  # type: ignore[union-attr]
    }
    assert work_id not in second_materialized_ids, (
        "INT-013's new, blocked revision must not materialize"
    )
    not_materialized_by_id = {
        entry["work_id"]: entry  # type: ignore[index]
        for entry in second_payload["not_materialized"]  # type: ignore[union-attr]
    }
    assert work_id in not_materialized_by_id
    int013_not_materialized = not_materialized_by_id[work_id]
    assert int013_not_materialized["materialization_error_code"] == "PROPOSAL_BLOCKED"
    assert int013_not_materialized["execution_ready"] is False
    assert int013_not_materialized["superseded_prior_revisions"] == [old_identity]

    # OLD_INT013_REVISION = SUPERSEDED (preserved, not deleted).
    projection_after = load_projection(store)
    old_record = next(
        r for r in projection_after.records if r.origination_identity == old_identity
    )
    assert old_record.state == "SUPERSEDED"
    assert old_record.work_node is not None  # historical evidence preserved

    # OLD_INT013_REVISION is no longer discoverable, rehydratable, or
    # leaseable -- the real read side the governor bridge itself uses.
    active_after = list_materialized_work_nodes(store)
    assert not any(n.package_id == work_id for n in active_after)
