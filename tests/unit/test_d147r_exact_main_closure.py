"""D-147R — exact-main closure integrity regression tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_atlas.orchestration.autonomy.exact_main_closure import (
    ClosureIntegrity,
    GitObjectPin,
    closure_integrity_pass,
    inspect_closure_integrity,
    reject_mixed_head_tree_packet,
    validate_head_tree_coherence,
)
from project_atlas.orchestration.autonomy.return_gate import (
    AutonomyReturnState,
    may_emit_final_return,
)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "c1"], cwd=repo, check=True, capture_output=True)
    return repo


def _head(repo: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _tree(repo: Path, rev: str) -> str:
    out = subprocess.run(
        ["git", "rev-parse", f"{rev}^{{tree}}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_validate_head_tree_coherent(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _head(repo)
    tree = _tree(repo, head)
    assert validate_head_tree_coherence(GitObjectPin(head=head, tree=tree), repo)


def test_current_head_stale_tree_forbidden(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _head(repo)
    (repo / "README.md").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "c2"], cwd=repo, check=True, capture_output=True)
    stale_tree = _tree(repo, head)
    live_head = _head(repo)
    assert reject_mixed_head_tree_packet(live_head, stale_tree, repo)


def test_stale_head_current_tree_forbidden(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head1 = _head(repo)
    (repo / "README.md").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "c2"], cwd=repo, check=True, capture_output=True)
    live_head = _head(repo)
    live_tree = _tree(repo, live_head)
    assert reject_mixed_head_tree_packet(head1, live_tree, repo)


def test_immutable_target_ancestor_model(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    cert_head = _head(repo)
    cert_tree = _tree(repo, cert_head)
    (repo / "docs" / "productization").mkdir(parents=True)
    runbook = repo / "docs/productization/CLEAN-MACHINE-PREP-RUNBOOK.md"
    runbook.write_text(
        f'$TARGET_HEAD = "{cert_head}"\n- `TREE` = `{cert_tree}`\n',
        encoding="utf-8",
    )
    (repo / "meta.txt").write_text("pin\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "metadata"], cwd=repo, check=True, capture_output=True)
    integrity = inspect_closure_integrity(
        repo, certification_target_head=cert_head, certification_target_tree=cert_tree
    )
    assert integrity.live_main_advanced_past_cert_target
    assert integrity.certification_target_is_ancestor_of_live_main
    assert closure_integrity_pass(integrity)


def test_operational_pins_disagree_fails_closure(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    cert_head = _head(repo)
    cert_tree = _tree(repo, cert_head)
    (repo / "docs" / "productization").mkdir(parents=True)
    runbook = repo / "docs/productization/CLEAN-MACHINE-PREP-RUNBOOK.md"
    runbook.write_text(
        '$TARGET_HEAD = "0000000000000000000000000000000000000001"\n'
        "- `TREE` = `0000000000000000000000000000000000000002`\n",
        encoding="utf-8",
    )
    integrity = inspect_closure_integrity(
        repo, certification_target_head=cert_head, certification_target_tree=cert_tree
    )
    assert not integrity.operational_pins_match_cert_target
    assert not closure_integrity_pass(integrity)


def test_case_b_forbidden_on_mixed_packet_state() -> None:
    state = AutonomyReturnState(
        genuine_owner_frontier=True,
        closure_integrity_pass=False,
    )
    assert may_emit_final_return(state) is False


def test_closure_model_fields() -> None:
    integrity = ClosureIntegrity(
        live_main_head="a" * 40,
        live_main_tree="b" * 40,
        certification_target_head="c" * 40,
        certification_target_tree="d" * 40,
        certification_target_is_ancestor_of_live_main=True,
        live_head_tree_coherent=True,
        cert_target_head_tree_coherent=True,
        operational_pins_match_cert_target=True,
    )
    assert closure_integrity_pass(integrity)
