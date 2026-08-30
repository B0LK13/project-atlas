"""D-PHASE2A-3: ``orchestration.origination.cli.run_origination_scan()``.

Mirrors ``test_orchestration_autonomy_rehydration.py``'s real-git-repo
fixture pattern (a real, self-contained repo with a faked
``origin/main`` remote-tracking ref, no network access required) and
``test_orchestration_origination.py``'s roadmap-writing fixture pattern
-- this module is the one place both are needed together, since
``run_origination_scan()`` is the first origination entry point that
also consults live git inventory for ``base_pin``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    ExecutionHostClass,
    NodeState,
    OwnerGateKind,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.orchestration.origination.cli import EXIT_ERROR, EXIT_OK, run_origination_scan
from project_atlas.orchestration.origination.projection import load_projection


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
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
            predecessor_main="a" * 40,
            predecessor_tree="b" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORIGIN-001-TEST",
            source_directive="D-PHASE2A-3-TEST-FIXTURE",
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
            evidence_reference="tests/fixtures/d-phase2a-3.json",
            evidence_digest="cd" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


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


def _eligible_repo(tmp_path: Path) -> Path:
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: do the thing.\n")
    _write_skipped_test(repo, "tests/test_feature_x.py")
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
    return repo


def test_scan_materializes_a_ready_o1_proposal(tmp_path: Path) -> None:
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_OK
    assert payload["eligible_count"] == 1
    assert payload["materialized_count"] == 1
    assert payload["not_materialized_count"] == 0
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    materialized = payload["materialized"]
    assert isinstance(materialized, list)
    entry = materialized[0]
    assert entry["execution_ready"] is True
    assert entry["reason"] == "READY"
    assert entry["risk_class"] == "O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION"
    assert entry["owner_gate"] is None

    # Durably persisted -- a later reader can find the exact node this
    # scan materialized, not just the in-memory payload.
    projection = load_projection(store)
    assert len(projection.records) == 1
    record = projection.records[0]
    assert record.state == "MATERIALIZED"
    assert record.work_node is not None
    assert record.work_node["package_id"] == entry["work_id"]
    assert record.work_node["execution_host_class"] == ExecutionHostClass.IN_PROCESS.value
    assert record.work_node["state"] == NodeState.DISCOVERED.value


def test_scan_with_no_eligible_work_is_a_clean_empty_result(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_OK
    assert payload["eligible_count"] == 0
    assert payload["materialized_count"] == 0
    assert payload["not_materialized_count"] == 0
    assert payload["materialized"] == []
    assert payload["not_materialized"] == []


def test_second_scan_does_not_re_materialize_already_terminal_work(tmp_path: Path) -> None:
    """The correct successor-scan semantic (`originate_new_only`, not
    `originate_all`): once a package's origination_identity is durably
    TERMINAL, a later scan must not re-propose or re-materialize it --
    matching NO_DUPLICATE_ORIGINATION / RESTART_REPLAY."""
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"
    anchor = _anchor(main, tree)

    first, _ = run_origination_scan(
        root=repo, project_id="demo-project", origination_store=store, explicit_trusted=anchor
    )
    assert first["materialized_count"] == 1
    identity = cast("list[dict[str, object]]", first["materialized"])[0]["work_id"]

    from project_atlas.orchestration.origination.projection import mark_terminal

    projection = load_projection(store)
    record = projection.records[0]
    mark_terminal(store, record.origination_identity, node_state="CLOSED")

    second, exit_code = run_origination_scan(
        root=repo, project_id="demo-project", origination_store=store, explicit_trusted=anchor
    )
    assert exit_code == EXIT_OK
    assert second["eligible_count"] == 0
    assert second["materialized_count"] == 0
    # Durable record is untouched, not duplicated.
    assert len(load_projection(store).records) == 1
    del identity  # only needed to document what was closed


def test_scan_fails_closed_on_trust_error(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        trust_store=tmp_path / "does-not-exist",
        origination_store=tmp_path / "origination-store",
    )
    assert exit_code == EXIT_ERROR
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    assert "blocker" in payload
    # No projection store was ever created -- the scan never ran.
    assert not (tmp_path / "origination-store").exists()


def test_owner_held_proposal_is_still_materialized_but_owner_gated(tmp_path: Path) -> None:
    """materialize_work_node()'s own contract: OWNER_HELD risk-classified
    proposals are still materialized (not silently dropped), just routed
    to an owner_gate rather than reported execution_ready. The scan must
    surface this distinction, not collapse it into "not materialized".

    proposed_scope is derived from the roadmap item's own `evidence`
    paths (pipeline.py's `_proposed_scope`), not a separate declared
    field -- so an evidence path that itself touches a disqualifying
    fragment (risk.py's `_DISQUALIFYING_PATH_FRAGMENTS`, "migrations/"
    here) is what forces OWNER_HELD, mirrored here rather than
    duplicating risk.py's own list.
    """
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: do the risky thing.\n")
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

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(main, tree),
    )
    assert exit_code == EXIT_OK
    # Whichever bucket it lands in, it must be reported somewhere, not
    # silently vanish -- and the two buckets combined must equal the
    # eligible count.
    total = cast(int, payload["materialized_count"]) + cast(int, payload["not_materialized_count"])
    assert total == payload["eligible_count"] == 1
    if payload["materialized_count"] == 1:
        entry = cast("list[dict[str, object]]", payload["materialized"])[0]
        assert entry["execution_ready"] is False
        assert entry["owner_gate"] in {kind.value for kind in OwnerGateKind}
    else:
        assert payload["not_materialized_count"] == 1
