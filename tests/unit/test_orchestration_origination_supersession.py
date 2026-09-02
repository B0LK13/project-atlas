"""AS-ORIGIN-MATERIALIZED-SUPERSESSION-001.

Owner directive: D-ATLAS-ORIGINATION-MATERIALIZED-REVISION-SUPERSESSION.

Real incident this package fixes: a previously-MATERIALIZED origination
revision (``work_id`` stable, ``origination_identity`` content-addressed --
see ``identity.py``) stayed durably rehydratable forever once a LATER
authoritative-source revision for the SAME logical work became BLOCKED /
OWNER_HELD / otherwise not execution-ready, protected only by an incidental,
non-designed property (a MATERIALIZED record's ``base_pin`` is never
refreshed, so it eventually trails live main and the rehydration bridge's
own freshness check happens to reject it). ``reconcile_revision()``
(projection.py) is the real fix: the required invariant is *a materialized
revision is rehydratable iff it is still the current authoritative eligible
revision for its work_id*, enforced atomically, independent of base_pin.

These tests exercise ``reconcile_revision()`` and
``list_materialized_work_nodes()`` directly against the real projection
store (unit-level, below ``run_origination_scan()``'s own end-to-end
coverage in ``test_orchestration_origination_cli.py``).
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from project_atlas.orchestration.origination.materialize import materialize_work_node
from project_atlas.orchestration.origination.pipeline import originate_all
from project_atlas.orchestration.origination.projection import (
    PROJECTION_NAME,
    OriginationProjectionError,
    OriginationRecord,
    list_materialized_work_nodes,
    load_projection,
    persist_proposed,
    reconcile_revision,
)
from project_atlas.orchestration.origination.risk import classify as classify_risk


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "init")
    sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", sha)
    return repo


def _write_roadmap(root: Path, items: list[dict[str, object]]) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    fence = json.dumps({"roadmap_items": items}, indent=2)
    (root / "docs" / "ROADMAP.md").write_text(
        f"## Roadmap record\n```json\n{fence}\n```\n", encoding="utf-8"
    )


def _eligible_repo(tmp_path: Path) -> Path:
    repo = _make_repo(tmp_path)
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "REQUIREMENTS.md").write_text("# Requirements\nFR-1: do the thing.\n")
    test_path = repo / "tests" / "test_feature_x.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(
        'import pytest\n\npytestmark = pytest.mark.skip(reason="not yet implemented")\n\n'
        "def test_placeholder():\n    assert True\n"
    )
    _write_roadmap(
        repo,
        [
            {
                "id": "feature-x",
                "title": "Feature X",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": ["docs/REQUIREMENTS.md", "tests/test_feature_x.py"],
            }
        ],
    )
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "seed roadmap")
    sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", sha)
    return repo


def test_reconcile_revision_case_a_same_identity_replay_is_idempotent_and_supersedes_nothing(
    tmp_path: Path,
) -> None:
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal, policy = outcomes[0].proposal, outcomes[0].policy
    persist_proposed(store, proposal, policy)
    classification = classify_risk(
        proposed_scope=proposal.proposed_scope, success_criteria=proposal.success_criteria
    )
    node = materialize_work_node(
        proposal, classification, base_pin=main, surface_id=f"{proposal.project_id}-a"
    )

    first = reconcile_revision(
        store,
        origination_identity=proposal.origination_identity,
        package_id=proposal.work_id,
        work_node=node,
    )
    assert first.already_current is False
    assert first.superseded == ()
    assert first.materialized is not None

    # Case A: repeat call, SAME identity, SAME evidence -- a re-scan.
    second = reconcile_revision(
        store,
        origination_identity=proposal.origination_identity,
        package_id=proposal.work_id,
        work_node=node,
    )
    assert second.already_current is True
    assert second.superseded == ()  # never re-supersedes anything on replay
    assert second.materialized is not None
    assert second.materialized.work_node == first.materialized.work_node

    projection = load_projection(store)
    assert len(projection.records) == 1
    assert projection.records[0].state == "MATERIALIZED"


def test_reconcile_revision_case_b_new_blocked_revision_supersedes_without_materializing(
    tmp_path: Path,
) -> None:
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    persist_proposed(store, proposal_a, policy_a)
    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    outcome_a = reconcile_revision(
        store,
        origination_identity=proposal_a.origination_identity,
        package_id=proposal_a.work_id,
        work_node=node_a,
    )
    assert outcome_a.materialized is not None

    # B: a new, distinct revision (different origination_identity), now
    # BLOCKED -- materialize_work_node() would raise PROPOSAL_BLOCKED for
    # it, so the scan-level caller never even builds a WorkNode; here we
    # exercise reconcile_revision() directly with work_node=None, exactly
    # what cli.py's MaterializationError handler does.
    proposal_b = proposal_a.model_copy(
        update={"origination_identity": "b" * 64, "blockers": ("EXTERNAL_BLOCKED: needs data",)}
    )
    persist_proposed(store, proposal_b, policy_a)

    outcome_b = reconcile_revision(
        store,
        origination_identity=proposal_b.origination_identity,
        package_id=proposal_b.work_id,
        work_node=None,
    )
    assert outcome_b.materialized is None
    assert len(outcome_b.superseded) == 1
    assert outcome_b.superseded[0].origination_identity == proposal_a.origination_identity
    assert outcome_b.superseded[0].state == "SUPERSEDED"
    # Historical evidence preserved -- same work_node as before, only
    # `state` changed.
    assert outcome_b.superseded[0].work_node == outcome_a.materialized.work_node

    projection = load_projection(store)
    a_record = next(
        r for r in projection.records if r.origination_identity == proposal_a.origination_identity
    )
    b_record = next(
        r for r in projection.records if r.origination_identity == proposal_b.origination_identity
    )
    assert a_record.state == "SUPERSEDED"
    assert b_record.state == "PROPOSED"
    assert b_record.work_node is None

    # list_materialized_work_nodes() must not return A any more.
    assert list_materialized_work_nodes(store) == ()


def test_reconcile_revision_case_c_new_ready_revision_supersedes_and_materializes(
    tmp_path: Path,
) -> None:
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    other_pin = "d" * 40
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    persist_proposed(store, proposal_a, policy_a)
    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    reconcile_revision(
        store,
        origination_identity=proposal_a.origination_identity,
        package_id=proposal_a.work_id,
        work_node=node_a,
    )

    proposal_c = proposal_a.model_copy(update={"origination_identity": "c" * 64})
    persist_proposed(store, proposal_c, policy_a)
    node_c = materialize_work_node(
        proposal_c, classification, base_pin=other_pin, surface_id=f"{proposal_c.project_id}-c"
    )
    outcome_c = reconcile_revision(
        store,
        origination_identity=proposal_c.origination_identity,
        package_id=proposal_c.work_id,
        work_node=node_c,
    )
    assert outcome_c.already_current is False
    assert len(outcome_c.superseded) == 1
    assert outcome_c.superseded[0].origination_identity == proposal_a.origination_identity
    assert outcome_c.materialized is not None
    assert outcome_c.materialized.origination_identity == proposal_c.origination_identity
    assert outcome_c.materialized.work_node is not None
    assert outcome_c.materialized.work_node["base_pin"] == other_pin

    active = list_materialized_work_nodes(store)
    assert len(active) == 1
    assert active[0].base_pin == other_pin


def test_reconcile_revision_case_d_ambiguous_active_revisions_fails_closed(
    tmp_path: Path,
) -> None:
    """Owner directive §5 Case D: never pick one arbitrarily. Constructs a
    corrupt store with TWO already-active revisions sharing one
    package_id (a shape ``reconcile_revision()`` itself should never
    produce -- simulating pre-migration/corrupt data, or a bug elsewhere)
    and proves a THIRD revision's reconciliation refuses to touch either.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    node_b = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-b"
    )
    proposal_b = proposal_a.model_copy(update={"origination_identity": "b" * 64})
    proposal_c = proposal_a.model_copy(update={"origination_identity": "c" * 64})

    # Directly construct a corrupt store: A and B both already MATERIALIZED
    # and active, sharing one package_id -- bypassing reconcile_revision()
    # entirely (which would never produce this shape) to simulate corrupt/
    # pre-migration data.
    store.mkdir(parents=True, exist_ok=True)
    from project_atlas.orchestration.autonomy.lease_projection import _write_atomic
    from project_atlas.orchestration.origination.projection import (
        OriginationProjection,
    )

    corrupt = OriginationProjection(
        records=(
            OriginationRecord(
                origination_identity=proposal_a.origination_identity,
                project_id=proposal_a.project_id,
                proposal=proposal_a.model_dump(mode="json"),
                policy_result=policy_a.model_dump(mode="json"),
                work_node=node_a.model_dump(mode="json"),
                state="MATERIALIZED",
            ),
            OriginationRecord(
                origination_identity=proposal_b.origination_identity,
                project_id=proposal_b.project_id,
                proposal=proposal_b.model_dump(mode="json"),
                policy_result=policy_a.model_dump(mode="json"),
                work_node=node_b.model_dump(mode="json"),
                state="MATERIALIZED",
            ),
            OriginationRecord(
                origination_identity=proposal_c.origination_identity,
                project_id=proposal_c.project_id,
                proposal=proposal_c.model_dump(mode="json"),
                policy_result=policy_a.model_dump(mode="json"),
                work_node=None,
                state="PROPOSED",
            ),
        )
    )
    _write_atomic(store / PROJECTION_NAME, corrupt.model_dump(mode="json"))

    # reconcile_revision() for C must fail closed rather than pick one of
    # A/B to supersede.
    try:
        reconcile_revision(
            store,
            origination_identity=proposal_c.origination_identity,
            package_id=proposal_c.work_id,
            work_node=node_a,
        )
        raise AssertionError("expected OriginationProjectionError")
    except OriginationProjectionError as exc:
        assert exc.code == "AMBIGUOUS_ACTIVE_REVISION"

    # Nothing changed: still both A and B MATERIALIZED, C still PROPOSED.
    projection = load_projection(store)
    states = {r.origination_identity: r.state for r in projection.records}
    assert states[proposal_a.origination_identity] == "MATERIALIZED"
    assert states[proposal_b.origination_identity] == "MATERIALIZED"
    assert states[proposal_c.origination_identity] == "PROPOSED"

    # The READ side independently fails closed too, for any caller that
    # goes through list_materialized_work_nodes() (the rehydration bridge)
    # rather than reconcile_revision() -- defense in depth.
    try:
        list_materialized_work_nodes(store)
        raise AssertionError("expected OriginationProjectionError")
    except OriginationProjectionError as exc:
        assert exc.code == "AMBIGUOUS_ACTIVE_REVISION"


def test_reconcile_revision_record_unknown_when_identity_never_proposed(tmp_path: Path) -> None:
    store = tmp_path / "origination-store"
    store.mkdir(parents=True, exist_ok=True)
    try:
        reconcile_revision(
            store,
            origination_identity="a" * 64,
            package_id="ORIG-doesnotexist",
            work_node=None,
        )
        raise AssertionError("expected OriginationProjectionError")
    except OriginationProjectionError as exc:
        assert exc.code == "RECORD_UNKNOWN"


def test_reconcile_revision_supersession_does_not_depend_on_base_pin(tmp_path: Path) -> None:
    """Owner directive §17: add an explicit regression where the old
    materialization's base_pin EQUALS current live main (i.e. it would
    still pass the rehydration bridge's independent base_pin freshness
    check) and authoritative source content changes to blocked WITHOUT
    changing that supplied base_pin. The old revision must still become
    non-rehydratable -- proving supersession is a real, designed
    invariant, not merely a side effect of base_pin going stale.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    persist_proposed(store, proposal_a, policy_a)
    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    reconcile_revision(
        store,
        origination_identity=proposal_a.origination_identity,
        package_id=proposal_a.work_id,
        work_node=node_a,
    )

    proposal_b = proposal_a.model_copy(
        update={"origination_identity": "e" * 64, "blockers": ("EXTERNAL_BLOCKED: needs data",)}
    )
    persist_proposed(store, proposal_b, policy_a)
    outcome_b = reconcile_revision(
        store,
        origination_identity=proposal_b.origination_identity,
        package_id=proposal_b.work_id,
        work_node=None,  # blocked -- never materializes
    )
    assert len(outcome_b.superseded) == 1

    projection = load_projection(store)
    a_record = next(
        r for r in projection.records if r.origination_identity == proposal_a.origination_identity
    )
    # A's base_pin is UNCHANGED -- still exactly live main. If the fix
    # were (bugfully) relying on base_pin staleness, this record would
    # still look "fresh" to a naive base_pin check -- but it is SUPERSEDED
    # regardless, and list_materialized_work_nodes() excludes it purely
    # by state, never consulting base_pin at all.
    assert a_record.work_node is not None
    assert a_record.work_node["base_pin"] == main
    assert a_record.state == "SUPERSEDED"
    active = list_materialized_work_nodes(store)
    assert not any(node.package_id == proposal_a.work_id for node in active)


def test_reconcile_revision_closes_the_toctou_race_between_two_new_revisions(
    tmp_path: Path,
) -> None:
    """Same threat model as the pre-existing
    ``persist_materialized_if_no_active_conflict`` TOCTOU test, but for
    ``reconcile_revision()``: two REAL threads racing to reconcile two
    different ``origination_identity`` proposals sharing one
    ``package_id``, synchronized with a ``Barrier`` to maximize actual
    lock contention. Exactly one must end up as the sole active
    (MATERIALIZED) revision; the other must be superseded or itself
    supersede the first -- never both active, never neither, never a
    corrupt/ambiguous store.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    proposal_b = proposal_a.model_copy(update={"origination_identity": "f" * 64})
    node_b = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-b"
    )
    persist_proposed(store, proposal_a, policy_a)
    persist_proposed(store, proposal_b, policy_a)

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _race(identity: str, node: object) -> None:
        try:
            barrier.wait()
            reconcile_revision(
                store,
                origination_identity=identity,
                package_id=proposal_a.work_id,
                work_node=node,  # type: ignore[arg-type]
            )
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(
        target=_race, args=(proposal_a.origination_identity, node_a)
    )
    t2 = threading.Thread(
        target=_race, args=(proposal_b.origination_identity, node_b)
    )
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert not t1.is_alive()
    assert not t2.is_alive()
    assert errors == []

    active = list_materialized_work_nodes(store)
    assert len(active) == 1

    projection = load_projection(store)
    assert len(projection.records) == 2
    states = {r.origination_identity: r.state for r in projection.records}
    superseded_count = sum(1 for state in states.values() if state == "SUPERSEDED")
    materialized_count = sum(1 for state in states.values() if state == "MATERIALIZED")
    assert superseded_count == 1
    assert materialized_count == 1
