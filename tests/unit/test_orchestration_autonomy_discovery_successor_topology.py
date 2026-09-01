"""AS-ORCH-AUTONOMY-001 STALE_SUCCESSOR_BRANCH_CLASSIFICATION.

Real IV finding during the first supervised-autonomy retry (D-CLAUDE-
ATLAS-RESUME-AUTONOMY-PREREQUISITES-AND-RETRY): a historical successor
branch (``feat/as-orch-001e-autonomous-loop``, merged via PR #401,
commit ``806218ae29792db63416a654e6a8390268764a1``) simply left on the
remote after merging permanently hard-blocked discovery via
``SUCCESSOR_ALREADY_STARTED`` -- ``collect_live_inventory()`` detected
"active successor" activity purely from a matching BRANCH NAME
existing, never checking whether that branch's content was already
integrated into main. ``BRANCH_REF_EXISTS != ACTIVE_SUCCESSOR``.

These tests use fully self-built, hermetic temp git repos (real ``git``
subprocess calls, real commits, ``git update-ref refs/remotes/origin/
main`` to simulate a fetched remote-tracking ref without any network
access -- the same technique this session's trust-checkpoint work
already established) rather than depending on this repository's own
live, historical branch state, which is not something a portable CI
checkout can be relied on to reproduce identically (shallow/limited
remote fetch scope). The exact real-repository regression (the
``feat/as-orch-001e-autonomous-loop`` branch specifically) was
independently, manually re-verified against this repository's actual
live state as part of closing this finding -- see WORKLOG.md.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.discovery import (
    DiscoveryError,
    _is_merged_into,
    collect_live_inventory,
    discover,
)
from project_atlas.orchestration.autonomy.models import AdvancementReason, TrustedAnchorRecord
from project_atlas.orchestration.autonomy.trust import seal_anchor


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path, *, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "f.txt").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "root")
    return repo


def _commit(repo: Path, message: str) -> str:
    (repo / "f.txt").write_text(f"{message}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _set_origin_main(repo: Path, sha: str) -> None:
    _git(repo, "update-ref", "refs/remotes/origin/main", sha)


def _set_remote_branch(repo: Path, refname: str, sha: str) -> None:
    _git(repo, "update-ref", refname, sha)


def _set_local_branch(repo: Path, name: str, sha: str) -> None:
    _git(repo, "branch", name, sha)


def _anchor_at(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity="github.com/b0lk13/project-atlas",
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main="0" * 40,
            predecessor_tree="0" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-AUTONOMY-PIN-RETARGET-003",
            source_pr=1,
            merge_commit=main,
            merge_parent_1="0" * 40,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/discovery-successor.json",
            evidence_digest="ab" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


# ---------------------------------------------------------------------------
# A/C -- a matching ref whose tip IS an ancestor of origin/main (including
# the trivial case of being main itself) is NOT active.
# ---------------------------------------------------------------------------


def test_a_merged_remote_successor_branch_is_not_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    main_tip = _commit(repo, "second")
    _set_origin_main(repo, main_tip)
    # The historical branch's tip (root) is an ancestor of current main.
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-old", root)

    inventory = collect_live_inventory(repo)
    assert inventory.active_successor_packages == ()
    assert inventory.as_orch_001e_started == "NO"

    report = discover(inventory, trusted=_anchor_at(main_tip, inventory.current_tree))
    assert report.blocker != "SUCCESSOR_ALREADY_STARTED"


def test_c_successor_branch_tip_equals_current_main_is_not_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    _set_origin_main(repo, main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-same", main_tip)

    inventory = collect_live_inventory(repo)
    assert inventory.active_successor_packages == ()


# ---------------------------------------------------------------------------
# B -- a matching LOCAL branch that is already merged is NOT active.
# ---------------------------------------------------------------------------


def test_b_merged_local_successor_branch_is_not_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    main_tip = _commit(repo, "second")
    _set_origin_main(repo, main_tip)
    _set_local_branch(repo, "as-orch-001d-r2-legacy", root)

    inventory = collect_live_inventory(repo)
    assert inventory.active_successor_packages == ()
    assert inventory.r2_created == "NO"


# ---------------------------------------------------------------------------
# D -- a matching ref with a genuinely UNMERGED tip IS active, and
# discover() correctly reports SUCCESSOR_ALREADY_STARTED for it.
# ---------------------------------------------------------------------------


def test_d_unmerged_successor_branch_is_active_and_blocks(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    _set_origin_main(repo, main_tip)
    _git(repo, "checkout", "-q", "-b", "feat/as-orch-001e-in-flight")
    unmerged_tip = _commit(repo, "still in flight")
    _git(repo, "checkout", "-q", "-B", "main-detached", main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-in-flight", unmerged_tip)

    inventory = collect_live_inventory(repo)
    # The local branch (still present from the checkout above) AND the
    # remote-tracking ref both match and are both genuinely unmerged --
    # correctly both counted (local-branch detection works too, not
    # just remote refs).
    assert set(inventory.active_successor_packages) == {
        "refs/heads/feat/as-orch-001e-in-flight",
        "refs/remotes/origin/feat/as-orch-001e-in-flight",
    }
    assert inventory.as_orch_001e_started == "YES"

    report = discover(inventory, trusted=_anchor_at(main_tip, inventory.current_tree))
    assert report.case == "A-B"
    assert report.blocker == "SUCCESSOR_ALREADY_STARTED"


# ---------------------------------------------------------------------------
# E -- one stale merged ref + one genuinely active ref -> still blocks
# (the merged one doesn't mask the real one, and vice versa).
# ---------------------------------------------------------------------------


def test_e_mixed_merged_and_unmerged_successor_refs_still_blocks(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    main_tip = _commit(repo, "second")
    _set_origin_main(repo, main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-old", root)
    _git(repo, "checkout", "-q", "-b", "feat/as-orch-001e-new")
    unmerged_tip = _commit(repo, "genuinely new work")
    _git(repo, "checkout", "-q", "-B", "main-detached", main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-new", unmerged_tip)

    inventory = collect_live_inventory(repo)
    assert "refs/remotes/origin/feat/as-orch-001e-old" not in inventory.active_successor_packages
    assert "refs/remotes/origin/feat/as-orch-001e-new" in inventory.active_successor_packages
    assert inventory.as_orch_001e_started == "YES"


# ---------------------------------------------------------------------------
# F -- a non-matching branch name, even with an unmerged tip, is irrelevant.
# ---------------------------------------------------------------------------


def test_f_nonmatching_branch_name_is_irrelevant(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    _set_origin_main(repo, main_tip)
    _git(repo, "checkout", "-q", "-b", "feat/totally-unrelated-work")
    unmerged_tip = _commit(repo, "unrelated")
    _git(repo, "checkout", "-q", "-B", "main-detached", main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/totally-unrelated-work", unmerged_tip)

    inventory = collect_live_inventory(repo)
    assert inventory.active_successor_packages == ()


# ---------------------------------------------------------------------------
# G -- multiple refs (simulating multiple remotes) pointing at the same
# already-integrated tip -> no false blocker from either.
# ---------------------------------------------------------------------------


def test_g_multiple_remote_refs_at_same_merged_tip_no_false_blocker(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    main_tip = _commit(repo, "second")
    _set_origin_main(repo, main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-old", root)
    _set_remote_branch(repo, "refs/remotes/upstream/feat/as-orch-001e-old", root)

    inventory = collect_live_inventory(repo)
    assert inventory.active_successor_packages == ()


# ---------------------------------------------------------------------------
# H -- topology query failure fails closed (DiscoveryError), never silently
# treated as "not merged" or "merged".
# ---------------------------------------------------------------------------


def test_h_topology_query_failure_fails_closed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(DiscoveryError):
        # A syntactically-invalid ref/object -- forces a real git error,
        # not one of the two genuine ancestry outcomes (0 or 1).
        _is_merged_into(repo, "not-a-real-object", main_tip)


# ---------------------------------------------------------------------------
# I -- symbolic remote HEAD refs are excluded (never mistaken for a real
# branch matching the successor patterns).
# ---------------------------------------------------------------------------


def test_symbolic_remote_head_ref_is_excluded(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    _set_origin_main(repo, main_tip)
    _git(repo, "checkout", "-q", "-b", "feat/as-orch-001e-branch")
    unmerged_tip = _commit(repo, "in flight")
    _git(repo, "checkout", "-q", "-B", "main-detached", main_tip)
    _set_remote_branch(repo, "refs/remotes/origin/feat/as-orch-001e-branch", unmerged_tip)
    # A symbolic HEAD ref for the same remote must never itself be
    # misread as a second matching branch (it wouldn't match the name
    # pattern anyway here, but confirms for-each-ref's HEAD exclusion
    # doesn't error or duplicate-count).
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    inventory = collect_live_inventory(repo)
    assert set(inventory.active_successor_packages) == {
        "refs/heads/feat/as-orch-001e-branch",
        "refs/remotes/origin/feat/as-orch-001e-branch",
    }
    # The symbolic HEAD ref itself never appears as a third entry.
    assert "refs/remotes/origin/HEAD" not in inventory.active_successor_packages


# ---------------------------------------------------------------------------
# K -- pre-existing successor-blocking behavior (genuinely unmerged, no
# name-pattern match confusion) still works after this change.
# ---------------------------------------------------------------------------


def test_k_existing_target_moved_precedence_unchanged(tmp_path: Path) -> None:
    """TARGET_MOVED still takes precedence over successor-activity
    classification -- this codepath is untouched by this fix."""
    repo = _make_repo(tmp_path)
    main_tip = _git(repo, "rev-parse", "HEAD")
    _set_origin_main(repo, main_tip)
    inventory = collect_live_inventory(repo)
    # A trusted anchor pointed at a DIFFERENT commit than observed main.
    other = "9" * 40
    report = discover(inventory, trusted=_anchor_at(other, "8" * 40))
    assert report.case == "A-B"
    assert report.blocker == "TARGET_MOVED"
