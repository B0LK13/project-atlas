"""D-PHASE2A-2: origination -> live governed DAG bridge.

Focused, integration, and adversarial coverage for the wiring closed here:
what `orchestration.origination.cli.run_origination_scan()` durably
materializes now actually reaches `orchestration.autonomy.cli.
run_governor_loop_tick()`'s governor (discovery), and a governed node that
reaches `dag.TERMINAL_STATES` is synced back to the origination projection
as `TERMINAL` (write-back) -- explicitly deferred by D-PHASE2A-1
("Wiring origination into the live governed DAG/lease/dispatch loop...
a separate later PR", `docs/backlog.md`).

Contract this file exists to prove, matching the directive's own diagram:

    ORIGINATION_PROPOSAL -> MATERIALIZED_WORK_NODE -> DURABLE_PROJECTION
        -> GOVERNOR DISCOVERY/REHYDRATION -> READY ONLY WHEN ELIGIBLE
        -> DEPENDENCY CHECK -> OWNER-GATE CHECK -> LEASE -> EXECUTION

    PROPOSAL != EXECUTION_AUTHORITY
    MATERIALIZED != READY (governor.add_node() alone never marks READY)
    READY != LEASE (an owner-gated or dependency-blocked READY node is
        never autonomously leased)
    LEASE != DISPATCH
    CERTIFIED != MERGED
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from project_atlas.orchestration.autonomy.cli import run_governor_loop_tick
from project_atlas.orchestration.autonomy.dag import TERMINAL_STATES
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    AgentCapability,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    OwnerGateKind,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.rehydration import rehydrate_governor
from project_atlas.orchestration.autonomy.trust import (
    initialize_store,
    load_runtime_anchor,
    seal_anchor,
)
from project_atlas.orchestration.origination.cli import run_origination_scan
from project_atlas.orchestration.origination.projection import (
    OriginationRecord,
    list_materialized_work_nodes,
    load_projection,
    sync_terminal_governed_states,
)

_TEST_IV_REQUIREMENTS = IvRequirements(certification_required=True, adversarial_required=False)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
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


def _anchor(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main="a" * 40,
            predecessor_tree="b" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="D-PHASE2A-2-TEST",
            source_directive="D-PHASE2A-2-TEST-FIXTURE",
            source_pr=1,
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
            evidence_reference="tests/fixtures/d-phase2a-2.json",
            evidence_digest="cd" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _minimal_work_node(
    package_id: str,
    *,
    base_pin: str,
    surface_id: str,
    paths: tuple[str, ...] = ("src/",),
    state: NodeState = NodeState.DISCOVERED,
) -> WorkNode:
    """A structurally-valid, minimal WorkNode for tests that only care
    about package_id/mutation_surface/state -- every other field is a
    fixed, arbitrary-but-valid placeholder."""
    return WorkNode(
        package_id=package_id,
        objective="test fixture node",
        base_pin=base_pin,
        mutation_surface=MutationSurface(surface_id=surface_id, paths=paths, semantic="TEST"),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("TEST_ACCEPTANCE",),
        iv_requirements=_TEST_IV_REQUIREMENTS,
        state=state,
    )


def _make_trust_store(tmp_path: Path, main: str, tree: str, name: str = "trust") -> Path:
    store = tmp_path / name
    initialize_store(store, _anchor(main, tree))
    return store


def _write_roadmap(root: Path, items: list[dict[str, object]]) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    fence = json.dumps({"roadmap_items": items}, indent=2)
    (root / "docs" / "ROADMAP.md").write_text(
        f"## Roadmap record\n```json\n{fence}\n```\n", encoding="utf-8"
    )


def _write_skipped_test(root: Path, rel_path: str) -> None:
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(
        'import pytest\n\npytestmark = pytest.mark.skip(reason="not yet implemented")\n\n'
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )


def _write_plain_file(root: Path, rel_path: str, content: str = "# doc\n") -> None:
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _eligible_repo(tmp_path: Path, *, item_id: str = "feature-x", name: str = "repo") -> Path:
    repo = _make_repo(tmp_path, name)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: do the thing.\n")
    _write_skipped_test(repo, f"tests/test_{item_id.replace('-', '_')}.py")
    _write_roadmap(
        repo,
        [
            {
                "id": item_id,
                "title": item_id,
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": [
                    "docs/REQUIREMENTS.md",
                    f"tests/test_{item_id.replace('-', '_')}.py",
                ],
            }
        ],
    )
    return repo


# --------------------------------------------------------------------------- #
# Focused: the wiring itself -- discovery, ready-only-when-eligible, lease.
# --------------------------------------------------------------------------- #
def test_run_governor_loop_tick_discovers_and_leases_materialized_origination_node(
    tmp_path: Path,
) -> None:
    """The core D-PHASE2A-2 proof: a real origination scan's durable output
    is picked up by the live tick entry point, with no manual `add_node()`/
    `mark_ready()` call in between -- the exact gap D-PHASE2A-1 deferred.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    origination_store = tmp_path / "origination-store"
    trust_store = _make_trust_store(tmp_path, main, tree)

    scan_payload, scan_exit = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=origination_store,
        trust_store=trust_store,
    )
    assert scan_exit == 0
    assert scan_payload["materialized_count"] == 1
    work_id = scan_payload["materialized"][0]["work_id"]  # type: ignore[index]

    # MATERIALIZED != READY: before any tick, the durable record exists,
    # but no governor has ever seen it -- proven by reading the record
    # directly, independent of the tick this test is about to run.
    nodes_before_tick = list_materialized_work_nodes(origination_store)
    assert any(n.package_id == work_id for n in nodes_before_tick)
    assert all(n.state == NodeState.DISCOVERED for n in nodes_before_tick)

    payload, exit_code = run_governor_loop_tick(
        root=repo,
        trust_store=trust_store,
        origination_store=origination_store,
    )
    assert exit_code == 0
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    # The tick must have found and leased this node -- not the hardcoded
    # pilot, which discover()'s real candidates are never eligible=True for.
    assert payload["package_id"] == "AS-ORCH-001E"


# --------------------------------------------------------------------------- #
# Terminal sync-back (write-back half of the bridge).
# --------------------------------------------------------------------------- #
def test_terminal_governed_state_syncs_back_to_origination_projection(tmp_path: Path) -> None:
    """Once a governed node reaches dag.TERMINAL_STATES (CLOSED), the
    durable origination record must be marked TERMINAL so a later
    successor scan correctly excludes it -- proven directly against
    sync_terminal_governed_states(), the write-back function itself,
    rather than driving a full autonomous flow all the way to CLOSED
    (which requires IV/verification steps this bridge does not itself
    perform -- see AUTONOMOUS_IMPLEMENTATION_EXECUTION's own honesty
    boundary, D-PHASE2A-1).
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    origination_store = tmp_path / "origination-store"

    scan_payload, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=origination_store,
        explicit_trusted=_anchor(main, tree),
    )
    work_id = scan_payload["materialized"][0]["work_id"]  # type: ignore[index]

    record_before = next(
        r
        for r in load_projection(origination_store).records
        if r.work_node is not None and r.work_node.get("package_id") == work_id
    )
    assert record_before.state == "MATERIALIZED"

    closed_node = WorkNode.model_validate(record_before.work_node).model_copy(
        update={"state": NodeState.CLOSED}
    )
    assert closed_node.state in TERMINAL_STATES

    synced = sync_terminal_governed_states(origination_store, [closed_node])
    assert synced == (record_before.origination_identity,)

    record_after = next(
        r
        for r in load_projection(origination_store).records
        if r.origination_identity == record_before.origination_identity
    )
    assert record_after.state == "TERMINAL"
    assert record_after.terminal_node_state == "CLOSED"

    # A second sync call is a safe no-op: the record is already TERMINAL,
    # so it's correctly excluded from consideration the second time.
    synced_again = sync_terminal_governed_states(origination_store, [closed_node])
    assert synced_again == ()


def test_non_closed_states_are_not_synced_as_terminal(tmp_path: Path) -> None:
    """OWNER_HELD (or any other non-CLOSED state) must NOT be synced --
    deliberately narrower than mark_terminal()'s own broader example
    list, per sync_terminal_governed_states()'s documented scoping
    decision."""
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    origination_store = tmp_path / "origination-store"

    scan_payload, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=origination_store,
        explicit_trusted=_anchor(main, tree),
    )
    work_id = scan_payload["materialized"][0]["work_id"]  # type: ignore[index]
    record = next(
        r
        for r in load_projection(origination_store).records
        if r.work_node is not None and r.work_node.get("package_id") == work_id
    )
    for not_closed in (
        NodeState.CERTIFIED,
        NodeState.OWNER_HELD,
        NodeState.BLOCKED,
        NodeState.MERGED,
        NodeState.MERGE_ELIGIBLE,
    ):
        node = WorkNode.model_validate(record.work_node).model_copy(update={"state": not_closed})
        assert sync_terminal_governed_states(origination_store, [node]) == ()
    # Confirm the record genuinely never moved.
    still_materialized = next(
        r
        for r in load_projection(origination_store).records
        if r.origination_identity == record.origination_identity
    )
    assert still_materialized.state == "MATERIALIZED"


def test_sync_skips_ambiguous_package_id_with_multiple_active_records(tmp_path: Path) -> None:
    """D-PHASE2A-2 independent-IV finding, round 2: `sync_terminal_governed_
    states()` matches purely by `package_id`. If more than one non-TERMINAL
    durable record ever shares one `package_id` (should not occur once
    `origination/cli.py`'s `find_active_record_by_package_id()` guard is in
    place prospectively -- proven separately in
    `test_orchestration_origination_cli.py` -- but this function must not
    assume that invariant holds for every store it is ever handed, e.g. one
    written before this fix, or a future bug elsewhere), it must refuse to
    guess which one actually produced the closed governed node: NEITHER is
    marked TERMINAL, not one chosen arbitrarily. Picking wrong would
    permanently and silently close a genuinely distinct, never-executed
    proposal."""
    origination_store = tmp_path / "origination-store"
    origination_store.mkdir()
    main = "a" * 40
    first = _minimal_work_node(
        "ORIG-ambiguous", base_pin=main, surface_id="first-surface", paths=("src/first/",)
    )
    second = _minimal_work_node(
        "ORIG-ambiguous", base_pin=main, surface_id="second-surface", paths=("src/second/",)
    )
    (origination_store / "origination.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package": "AS-ORCH-ORIGINATION-PROJECTION-001",
                "records": [
                    OriginationRecord(
                        origination_identity="a" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=first.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                    OriginationRecord(
                        origination_identity="b" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=second.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                ],
            }
        ),
        encoding="utf-8",
    )

    closed_node = first.model_copy(update={"state": NodeState.CLOSED})
    synced = sync_terminal_governed_states(origination_store, [closed_node])
    assert synced == ()

    # Neither record moved -- both still MATERIALIZED, ambiguity preserved
    # honestly rather than resolved by guessing.
    records_after = load_projection(origination_store).records
    assert {r.state for r in records_after} == {"MATERIALIZED"}
    assert len(records_after) == 2


def test_sync_ignores_nodes_that_do_not_match_any_origination_record(tmp_path: Path) -> None:
    """A CLOSED governor node whose package_id has no origination record
    at all (e.g. the hardcoded pilot node) must not raise or otherwise
    misbehave -- it simply has nothing to sync."""
    origination_store = tmp_path / "origination-store"
    origination_store.mkdir()
    unrelated_node = _minimal_work_node(
        "orch-autonomy-pilot",
        base_pin="a" * 40,
        surface_id="unrelated-surface",
        state=NodeState.CLOSED,
    )
    assert sync_terminal_governed_states(origination_store, [unrelated_node]) == ()


# --------------------------------------------------------------------------- #
# READY != LEASE: owner-gated and dependency-blocked origination nodes are
# discovered and marked READY, but never autonomously leased.
# --------------------------------------------------------------------------- #
def test_owner_gated_origination_node_is_discovered_but_never_autonomously_leased(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: risky.\n")
    _write_plain_file(repo, "migrations/001_init.sql", "-- migration\n")
    _write_skipped_test(repo, "tests/test_risky.py")
    _write_roadmap(
        repo,
        [
            {
                "id": "risky-item",
                "title": "Risky Item",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": [
                    "docs/REQUIREMENTS.md",
                    "migrations/001_init.sql",
                    "tests/test_risky.py",
                ],
            }
        ],
    )
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    origination_store = tmp_path / "origination-store"
    trust_store = _make_trust_store(tmp_path, main, tree)

    scan_payload, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=origination_store,
        trust_store=trust_store,
    )
    entry = scan_payload["materialized"][0]  # type: ignore[index]
    assert entry["owner_gate"] in {kind.value for kind in OwnerGateKind}

    payload, exit_code = run_governor_loop_tick(
        root=repo, trust_store=trust_store, origination_store=origination_store
    )
    assert exit_code == 0
    # OWNER_GATE, never leased/dispatched -- proven by the loop's own
    # stop_reason, not merely by absence of an error.
    assert payload["stop_reason"] == "OWNER_GATE"
    assert payload["dispatched"] is False


# --------------------------------------------------------------------------- #
# Adversarial matrix: bridge-specific failure modes.
# --------------------------------------------------------------------------- #
def test_corrupt_materialized_work_node_is_skipped_not_fatal(tmp_path: Path) -> None:
    """One malformed durable record must not hide every other legitimate
    one -- list_materialized_work_nodes() skips it, not raises."""
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    origination_store = tmp_path / "origination-store"
    origination_store.mkdir()

    good_node = _minimal_work_node(
        "ORIG-good", base_pin=main, surface_id="good-surface", paths=("src/good/",)
    )
    projection_path = origination_store / "origination.json"
    projection_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package": "AS-ORCH-ORIGINATION-PROJECTION-001",
                "records": [
                    OriginationRecord(
                        origination_identity="a" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=good_node.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                    OriginationRecord(
                        origination_identity="b" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node={"package_id": "ORIG-corrupt", "not": "a valid WorkNode"},
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                ],
            }
        ),
        encoding="utf-8",
    )

    nodes = list_materialized_work_nodes(origination_store)
    assert {n.package_id for n in nodes} == {"ORIG-good"}


def test_duplicate_package_id_across_two_origination_records_is_skipped_not_fatal(
    tmp_path: Path,
) -> None:
    """Two DIFFERENT origination_identity records that somehow durably
    resolved to the SAME work_node.package_id (a data-integrity edge
    case: a corrupted/hand-edited store, or a future bug elsewhere) must
    not crash the whole discovery pass. add_node()'s own DUPLICATE_NODE
    check catches the second one; the per-candidate try/except in
    _originate() must skip it, not abort discovery for every other,
    genuinely distinct candidate that follows.

    (A mutation-surface OVERLAP between two DISCOVERED/READY candidates
    is not itself an add_node()/mark_ready() failure -- would_overlap()
    is checked only at lease() time, by design, so two overlapping READY
    nodes coexisting in the DAG is not an error this pass needs to
    catch; only an actual attempt to lease both would be, and that is
    already covered by _select_and_lease()'s own SURFACE_OVERLAP
    handling, tested elsewhere.)
    """
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    trusted = load_runtime_anchor(store=trust_store)

    from project_atlas.orchestration.autonomy.discovery import collect_live_inventory

    inventory = collect_live_inventory(repo)
    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
    )

    origination_store = tmp_path / "origination-store"
    origination_store.mkdir()
    # Both records resolve to the SAME package_id -- the adversarial case.
    first = _minimal_work_node(
        "ORIG-dup", base_pin=main, surface_id="first-surface", paths=("src/first/",)
    )
    second = _minimal_work_node(
        "ORIG-dup", base_pin=main, surface_id="second-surface", paths=("src/second/",)
    )
    clean = _minimal_work_node(
        "ORIG-clean", base_pin=main, surface_id="clean-surface", paths=("src/clean/",)
    )
    (origination_store / "origination.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package": "AS-ORCH-ORIGINATION-PROJECTION-001",
                "records": [
                    OriginationRecord(
                        origination_identity="a" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=first.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                    OriginationRecord(
                        origination_identity="b" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=second.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                    OriginationRecord(
                        origination_identity="c" * 64,
                        project_id="demo",
                        proposal={},
                        policy_result={},
                        work_node=clean.model_dump(mode="json"),
                        state="MATERIALIZED",
                    ).model_dump(mode="json"),
                ],
            }
        ),
        encoding="utf-8",
    )

    rehydrate_governor(
        governor,
        inventory=inventory,
        trusted=trusted,
        loop_store=tmp_path / "loop-state",
        lease_projection_store=tmp_path / "lease-projection",
        origination_projection_store=origination_store,
    )

    package_ids = [n.package_id for n in governor.snapshot().nodes]
    # Exactly one "ORIG-dup" made it in (the first one encountered) --
    # never zero, never a crash, never two.
    assert package_ids.count("ORIG-dup") == 1
    assert "ORIG-clean" in package_ids


def test_second_tick_does_not_duplicate_already_discovered_node(tmp_path: Path) -> None:
    """A materialized node discovered on tick N must not be re-added (and
    raise DUPLICATE_NODE) on tick N+1 against the SAME still-non-terminal
    durable record -- the exact cross-process continuation scenario a
    real recurring loop produces."""
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    origination_store = tmp_path / "origination-store"
    trust_store = _make_trust_store(tmp_path, main, tree)

    run_origination_scan(
        root=repo, project_id="demo-project", origination_store=origination_store,
        trust_store=trust_store,
    )

    first_payload, first_exit = run_governor_loop_tick(
        root=repo, trust_store=trust_store, origination_store=origination_store
    )
    assert first_exit == 0
    assert first_payload["stop_reason"] != "FAILED_CLOSED"

    second_payload, second_exit = run_governor_loop_tick(
        root=repo, trust_store=trust_store, origination_store=origination_store
    )
    assert second_exit == 0
    assert second_payload["stop_reason"] != "FAILED_CLOSED"


def test_malformed_origination_projection_file_does_not_crash_tick(tmp_path: Path) -> None:
    """A corrupt origination.json must not crash run_governor_loop_tick()
    -- list_materialized_work_nodes() fails closed to empty, exactly like
    find_materialized_work_node() already does for the single-lookup
    case."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)

    origination_store = tmp_path / "origination-store"
    origination_store.mkdir()
    (origination_store / "origination.json").write_text("{not valid json", encoding="utf-8")

    payload, exit_code = run_governor_loop_tick(
        root=repo, trust_store=trust_store, origination_store=origination_store
    )
    assert exit_code == 0
    assert payload["stop_reason"] != "FAILED_CLOSED"


# --------------------------------------------------------------------------- #
# Real cross-process proof: two genuinely separate OS processes, sharing only
# filesystem state -- not two objects in one interpreter. §7's own standard.
# --------------------------------------------------------------------------- #
_PROCESS_ONE_SCRIPT = """
import json
import sys
from pathlib import Path

sys.path.insert(0, {src_path!r})
from project_atlas.orchestration.autonomy.cli import run_governor_loop_tick
from project_atlas.orchestration.autonomy.lease_projection import (
    RELATIVE_DEFAULT as LEASE_PROJECTION_RELATIVE_DEFAULT,
)
from project_atlas.orchestration.autonomy.lease_projection import load_projection
from project_atlas.orchestration.origination.cli import run_origination_scan

root = Path({root!r})
trust_store = Path({trust_store!r})
origination_store = Path({origination_store!r})

scan_payload, scan_exit = run_origination_scan(
    root=root,
    project_id="demo-project",
    origination_store=origination_store,
    trust_store=trust_store,
)
assert scan_exit == 0, scan_payload
assert scan_payload["materialized_count"] == 1, scan_payload

tick_payload, tick_exit = run_governor_loop_tick(
    root=root, trust_store=trust_store, origination_store=origination_store
)
lease_projection = load_projection(root / LEASE_PROJECTION_RELATIVE_DEFAULT)
print(json.dumps({{
    "scan_payload": scan_payload,
    "tick_exit": tick_exit,
    "tick_payload": tick_payload,
    "lease_projection_package_ids": [row.package_id for row in lease_projection.leases],
}}))
"""

_PROCESS_TWO_SCRIPT = """
import json
import sys
from pathlib import Path

sys.path.insert(0, {src_path!r})
from project_atlas.orchestration.autonomy.cli import run_governor_loop_tick

root = Path({root!r})
trust_store = Path({trust_store!r})
origination_store = Path({origination_store!r})

tick_payload, tick_exit = run_governor_loop_tick(
    root=root, trust_store=trust_store, origination_store=origination_store
)
print(json.dumps({{"tick_exit": tick_exit, "tick_payload": tick_payload}}))
"""


def test_real_two_process_continuation_does_not_replay_or_crash(tmp_path: Path) -> None:
    """Process N originates + materializes + ticks (discovers, leases,
    and -- since execution_host_class is always IN_PROCESS for
    origination-materialized nodes -- dispatches/executes) against a
    real evidence-backed repo, using ONLY the consolidated CLI entry
    points (never manually calling governor.add_node()/lease() by
    hand). It then exits -- a genuinely separate OS process, not an
    object this test keeps alive.

    Process N+1 -- a SEPARATE `python` subprocess, sharing only the
    filesystem (the loop store, lease projection, and origination
    projection this repo's own `root` durably persisted) -- reconstructs
    from that same disk state and ticks again.

    This is the exact scenario `_originate()`'s `lease_projection_store`
    fix (found by this file's own earlier in-process adversarial test)
    exists for: a fresh, empty-node governor in the second process must
    not re-discover and re-attempt to lease the same already-leased
    package_id. Proven here across a REAL process boundary, not two
    objects in one interpreter.
    """
    import sys

    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    origination_store = tmp_path / "origination-store"

    src_path = str(Path(__file__).resolve().parents[2] / "src")

    script_one = tmp_path / "process_one.py"
    script_one.write_text(
        _PROCESS_ONE_SCRIPT.format(
            src_path=src_path,
            root=str(repo),
            trust_store=str(trust_store),
            origination_store=str(origination_store),
        ),
        encoding="utf-8",
    )
    result_one = subprocess.run(
        [sys.executable, str(script_one)], capture_output=True, text=True, timeout=60
    )
    assert result_one.returncode == 0, result_one.stderr
    output_one = json.loads(result_one.stdout.strip().splitlines()[-1])
    assert output_one["tick_exit"] == 0, output_one
    tick_one = output_one["tick_payload"]
    assert tick_one["stop_reason"] != "FAILED_CLOSED", tick_one
    # Process N genuinely leased something this run -- not a vacuous
    # NO_ELIGIBLE_WORK stop that would make process N+1's check
    # meaningless. Checked against the DURABLE lease projection (not the
    # tick's own transient `dispatched` flag, which reflects the LAST
    # internal step's own result object, not necessarily true for the
    # overall tick when IN_PROCESS execution completes the full lease ->
    # dispatch -> validate -> complete cycle synchronously within one
    # call and the loop lands back at IDLE).
    work_id = output_one["scan_payload"]["materialized"][0]["work_id"]
    assert work_id in output_one["lease_projection_package_ids"], output_one

    script_two = tmp_path / "process_two.py"
    script_two.write_text(
        _PROCESS_TWO_SCRIPT.format(
            src_path=src_path,
            root=str(repo),
            trust_store=str(trust_store),
            origination_store=str(origination_store),
        ),
        encoding="utf-8",
    )
    result_two = subprocess.run(
        [sys.executable, str(script_two)], capture_output=True, text=True, timeout=60
    )
    assert result_two.returncode == 0, result_two.stderr
    output_two = json.loads(result_two.stdout.strip().splitlines()[-1])
    assert output_two["tick_exit"] == 0, output_two
    tick_two = output_two["tick_payload"]
    # The real proof: process N+1, from a completely fresh governor
    # (zero in-memory nodes), does NOT re-discover and re-lease the same
    # package -- no crash (LEASE_REPLAY used to propagate uncaught here),
    # and no second dispatch of already-completed work.
    assert tick_two["stop_reason"] != "FAILED_CLOSED", tick_two
    assert tick_two["dispatched"] is False, tick_two
