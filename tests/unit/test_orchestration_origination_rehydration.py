"""D-PHASE2A: cross-process rehydration of an origination-derived WorkNode.

This is the single test that most directly proves
``CROSS_PROCESS_ORIGINATION`` (the sealed baseline's stated gap): a
WorkNode whose mutation surface, acceptance criteria, and risk
classification came from real project evidence -- not from anything the
live inventory alone could reconstruct -- surviving a simulated process
restart via ``rehydration.py``'s new, additive origination path.

Mirrors the existing pilot-node cross-process contract tests in
``test_orchestration_autonomy_rehydration.py`` (same fixture shape: a
fresh ``AutonomousGovernor`` that reads only from disk, never the
governor/loop object that produced the state).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_atlas.orchestration.autonomy.discovery import collect_live_inventory
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.loop import (
    LoopPhase,
    initial_loop_state,
    persist_loop_state,
    seal_loop_state,
)
from project_atlas.orchestration.autonomy.models import (
    AdvancementReason,
    NodeState,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.rehydration import RehydrationError, rehydrate_governor
from project_atlas.orchestration.autonomy.trust import (
    CANONICAL_REPOSITORY_IDENTITY,
    initialize_store,
    load_runtime_anchor,
    seal_anchor,
)
from project_atlas.orchestration.origination import materialize, projection, risk
from project_atlas.orchestration.origination.pipeline import originate_all

_OLD_MAIN = "a" * 40
_OLD_TREE = "b" * 40


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


def _anchor(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=_OLD_MAIN,
            predecessor_tree=_OLD_TREE,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-PHASE2A-TEST-FIXTURE",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=_OLD_MAIN,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/phase2a.json",
            evidence_digest="ab" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _make_trust_store(tmp_path: Path, main: str, tree: str) -> Path:
    store = tmp_path / "trust"
    initialize_store(store, _anchor(main, tree))
    return store


def _write_specified_project(project_root: Path) -> None:
    """A generic, self-contained specification-backed project -- same
    evidence shape as the real Gamma/TASK-017 estate, but synthetic so
    this test never depends on an external path."""
    (project_root / "docs").mkdir(parents=True)
    (project_root / "tests").mkdir(parents=True)
    (project_root / "docs" / "REQUIREMENTS.md").write_text(
        "# Requirements\nFR-1: implement the thing.\n", encoding="utf-8"
    )
    (project_root / "tests" / "test_feature_x.py").write_text(
        'import pytest\n\npytestmark = pytest.mark.skip(reason="not yet implemented")\n\n'
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    import json

    record = {
        "roadmap_items": [
            {
                "id": "feature-x",
                "title": "Feature X",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": ["docs/REQUIREMENTS.md", "tests/test_feature_x.py"],
            }
        ]
    }
    (project_root / "docs" / "ROADMAP.md").write_text(
        f"# Roadmap\n\n## Roadmap record\n```json\n{json.dumps(record, indent=2)}\n```\n",
        encoding="utf-8",
    )


def _lease_origination_node(
    repo: Path, trust_store: Path, lease_store: Path, origination_store: Path, project_root: Path
):
    trusted = load_runtime_anchor(store=trust_store)
    inventory = collect_live_inventory(repo)

    outcomes = originate_all(project_root, "demo-project")
    assert len(outcomes) == 1
    proposal, policy_result = outcomes[0].proposal, outcomes[0].policy
    assert policy_result.execution_ready is True

    classification = risk.classify(
        proposed_scope=proposal.proposed_scope, success_criteria=proposal.success_criteria
    )
    node = materialize.materialize_work_node(
        proposal,
        classification,
        base_pin=inventory.current_main,
        surface_id="demo-project-feature-x",
    )

    projection.persist_proposed(origination_store, proposal, policy_result)
    projection.persist_materialized(origination_store, proposal.origination_identity, node)

    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
        # Wired exactly like the real production tick
        # (`autonomy/cli.py::run_governor_loop_tick`), which is what this
        # Process-A helper stands in for. Leasing an origination-derived
        # node requires proving its revision is still current, and a
        # governor with no origination projection cannot prove that
        # (owner directive
        # D-ATLAS-PR678-UNWIRED-GOVERNOR-FAIL-CLOSED-FINAL: failure to
        # verify is not permission to execute). The node materialized
        # just above IS the current revision in this same store, so the
        # check passes on its own merits here -- it is not bypassed.
        origination_projection_store=origination_store,
    )
    governor.add_node(node)
    governor.mark_ready(node.package_id)
    lease = governor.lease(
        node.package_id, "governor-pilot-local", branch="feat/origination", worktree="wt"
    )
    return trusted, inventory, lease, node.package_id


def test_origination_node_survives_simulated_process_restart(tmp_path: Path) -> None:
    """Process A originates + leases; a FRESH governor (Process B, reading
    only from disk) rehydrates the exact same WorkNode and restores the
    lease -- CROSS_PROCESS_ORIGINATION, proven."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    origination_store = tmp_path / "origination"
    project_root = tmp_path / "project"
    _write_specified_project(project_root)

    trusted, inventory, lease, package_id = _lease_origination_node(
        repo, trust_store, lease_store, origination_store, project_root
    )

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": package_id,
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    # Process B: a brand-new governor that has never seen this node.
    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    assert fresh.snapshot().nodes == ()

    rehydrate_governor(
        fresh,
        inventory=inventory,
        trusted=trusted,
        loop_store=loop_store,
        lease_projection_store=lease_store,
        origination_projection_store=origination_store,
    )

    snapshot = fresh.snapshot()
    node = next(item for item in snapshot.nodes if item.package_id == package_id)
    assert node.state == NodeState.LEASED
    assert node.execution_host_class.value == "IN_PROCESS"
    assert node.owner_gate is None  # this proposal cleared policy as O1, not OWNER_HELD
    restored = next(item for item in snapshot.leases if item.lease_id == lease.lease_id)
    assert restored.agent_id == lease.agent_id
    assert restored.base_pin == lease.base_pin


def test_origination_node_fails_closed_without_projection_store(tmp_path: Path) -> None:
    """Same durable state as above, but the caller does not pass
    ``origination_projection_store`` -- byte-identical fail-closed
    behavior to before this parameter existed. Proves the extension is
    additive, not a relaxation of the existing NODE_NOT_REHYDRATABLE
    guarantee for every caller that doesn't opt in."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    origination_store = tmp_path / "origination"
    project_root = tmp_path / "project"
    _write_specified_project(project_root)

    trusted, inventory, lease, package_id = _lease_origination_node(
        repo, trust_store, lease_store, origination_store, project_root
    )
    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": package_id,
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    try:
        rehydrate_governor(
            fresh,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
            # origination_projection_store intentionally omitted
        )
        raised = False
    except RehydrationError as exc:
        raised = True
        assert exc.code == "NODE_NOT_REHYDRATABLE"
    assert raised is True


def test_origination_node_fails_closed_on_wrong_projection_store(tmp_path: Path) -> None:
    """A projection store that exists but has no record for this
    package_id (e.g. pointed at the wrong root) fails closed identically
    -- never silently falls back to fabricating a node."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    origination_store = tmp_path / "origination"
    project_root = tmp_path / "project"
    _write_specified_project(project_root)

    trusted, inventory, lease, package_id = _lease_origination_node(
        repo, trust_store, lease_store, origination_store, project_root
    )
    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": package_id,
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    empty_origination_store = tmp_path / "empty-origination"
    empty_origination_store.mkdir()
    try:
        rehydrate_governor(
            fresh,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
            origination_projection_store=empty_origination_store,
        )
        raised = False
    except RehydrationError as exc:
        raised = True
        assert exc.code == "NODE_NOT_REHYDRATABLE"
    assert raised is True
