"""Lane guard — fail-closed "may this agent write to this lane now?".

UNOWNED != PERMITTED · AMBIGUOUS != OWNED · UNKNOWN != OWNED · GUARD != AUTHORIZATION
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as dag_cli  # noqa: E402
from atlas_dag import lane_guard as lg  # noqa: E402
from test_atlas_dag import comments_with, make_event  # noqa: E402

FIXED = "2026-09-09T12:00:00Z"
ME = "ubuntu-main"
OTHER = "windows-main"


def clock():
    return FIXED


def _claim(actor, pr=776, eid=None):
    return make_event(eid or f"claim-{actor}-{pr}", "OWNER_CLAIMED", pr=pr,
                      actor=actor, state="CLAIMED")


def _release(actor, pr=776, eid=None):
    return make_event(eid or f"release-{actor}-{pr}", "OWNER_RELEASED", pr=pr,
                      actor=actor, state="RELEASED")


class FakeClient:
    def __init__(self, *, prs=None, events=None, issue=True):
        self.repo = "B0LK13/project-atlas"
        self._prs = prs if prs is not None else [
            {"number": 776, "headRefName": "feat/as-studio-a2-001", "headRefOid": "a" * 40}
        ]
        self._events = events or []
        self._issue = issue

    def open_prs(self):
        return self._prs

    def dag_issue(self):
        return {"number": 719} if self._issue else None

    def issue_comments(self, number):
        return comments_with(*self._events)


# --- pure verdicts -----------------------------------------------------------


def test_owner_is_allowed():
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=776, events=[_claim(ME)], clock=clock)
    assert packet["decision"] == lg.ALLOWED
    assert packet["ownership"] == "OWNED"
    assert packet["claimants"] == [ME]
    assert packet["reasons"] == ["LANE_OWNED_BY_AGENT"]
    assert packet["schema"] == lg.SCHEMA_CONST
    assert packet["honesty"]["guard_ne_authorization"] is True


def test_other_owner_refused():
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=776, events=[_claim(OTHER)], clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == [f"LANE_OWNED_BY_OTHER:{OTHER}"]


def test_unowned_is_not_permitted():
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=776, events=[], clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["ownership"] == "UNOWNED"
    assert packet["reasons"] == ["LANE_UNOWNED_CLAIM_FIRST"]


def test_released_lane_is_unowned_again():
    events = [_claim(ME), _release(ME)]
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=776, events=events, clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["ownership"] == "UNOWNED"


def test_ambiguous_ownership_refused_for_everyone():
    events = [_claim(ME), _claim(OTHER)]
    for agent in (ME, OTHER):
        packet = lg.evaluate_lane_guard(agent_id=agent, pr=776, events=events, clock=clock)
        assert packet["decision"] == lg.REFUSED, agent
        assert packet["ownership"] == "AMBIGUOUS"
        assert packet["reasons"] == ["OWNERSHIP_AMBIGUOUS"]
        assert packet["claimants"] == sorted([ME, OTHER])


def test_claim_on_other_lane_does_not_leak():
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=776, events=[_claim(ME, pr=770)], clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["LANE_UNOWNED_CLAIM_FIRST"]


@pytest.mark.parametrize("agent", [None, "", "   "])
def test_missing_identity_refused_even_when_lane_unowned(agent):
    packet = lg.evaluate_lane_guard(agent_id=agent, pr=776, events=[], clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["AGENT_IDENTITY_UNSET"]
    assert packet["agent"] is None


def test_missing_lane_refused_even_for_valid_agent():
    packet = lg.evaluate_lane_guard(agent_id=ME, pr=None, events=[_claim(ME)], clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["LANE_UNRESOLVED"]
    assert packet["lane"] is None


def test_guard_never_mutates_events():
    events = [_claim(ME)]
    before = json.dumps(events, sort_keys=True)
    lg.evaluate_lane_guard(agent_id=ME, pr=776, events=events, clock=clock)
    assert json.dumps(events, sort_keys=True) == before


# --- live resolution (fake client) -------------------------------------------


def test_live_branch_resolves_to_pr_and_allows_owner():
    client = FakeClient(events=[_claim(ME)])
    packet = lg.guard_live(client, agent_id=ME, branch="feat/as-studio-a2-001", clock=clock)
    assert packet["decision"] == lg.ALLOWED
    assert packet["pr"] == 776
    assert packet["branch"] == "feat/as-studio-a2-001"


def test_live_branch_without_open_pr_refused():
    client = FakeClient(events=[_claim(ME)])
    packet = lg.guard_live(client, agent_id=ME, branch="feat/unknown", clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["NO_OPEN_PR_FOR_BRANCH:feat/unknown"]
    assert packet["ownership"] == "UNKNOWN"


def test_live_branch_match_is_exact_not_prefix():
    client = FakeClient(events=[_claim(ME)])
    packet = lg.guard_live(client, agent_id=ME, branch="feat/as-studio-a2-00", clock=clock)
    assert packet["decision"] == lg.REFUSED


def test_live_bus_unavailable_refused():
    client = FakeClient(events=[_claim(ME)], issue=False)
    packet = lg.guard_live(client, agent_id=ME, pr=776, clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["DAG_CONTROL_ISSUE_NOT_FOUND"]
    assert packet["ownership"] == "UNKNOWN"


def test_live_unowned_refused():
    packet = lg.guard_live(FakeClient(), agent_id=ME, pr=776, clock=clock)
    assert packet["decision"] == lg.REFUSED
    assert packet["reasons"] == ["LANE_UNOWNED_CLAIM_FIRST"]


# --- CLI ---------------------------------------------------------------------


def _run_cli(monkeypatch, capsys, client, argv):
    monkeypatch.setattr(dag_cli, "_client", lambda args: client)
    rc = dag_cli.main(argv)
    return rc, capsys.readouterr()


def test_cli_exit_zero_only_when_owner(monkeypatch, capsys):
    rc, out = _run_cli(monkeypatch, capsys, FakeClient(events=[_claim(ME)]),
                       ["lane-guard", "--agent", ME, "--pr", "776", "--json"])
    assert rc == 0
    assert json.loads(out.out)["decision"] == lg.ALLOWED

    rc, out = _run_cli(monkeypatch, capsys, FakeClient(events=[_claim(OTHER)]),
                       ["lane-guard", "--agent", ME, "--pr", "776"])
    assert rc == 1
    assert f"LANE_OWNED_BY_OTHER:{OTHER}" in out.out
    assert "GUARD!=AUTHORIZATION" in out.out


def test_cli_requires_pr_or_branch(monkeypatch, capsys):
    rc, out = _run_cli(monkeypatch, capsys, FakeClient(), ["lane-guard", "--agent", ME])
    assert rc == 2
    assert "--pr or --branch" in out.err


def test_cli_has_no_bypass_flag():
    parser = dag_cli.build_parser() if hasattr(dag_cli, "build_parser") else None
    src = Path(lg.__file__).read_text(encoding="utf-8")
    assert "bypass" not in src.lower().replace("no bypass switch by design", "")
    if parser is not None:
        with pytest.raises(SystemExit):
            parser.parse_args(["lane-guard", "--agent", ME, "--pr", "1", "--force"])


# --- hook install ------------------------------------------------------------


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "wt"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def test_install_hook_writes_marked_executable_script(tmp_path):
    repo = _git_repo(tmp_path)
    dag = REPO_ROOT / "scripts" / "atlas-dag.py"
    target = lg.install_hook(repo, agent_id=ME, dag_script=dag, repo="B0LK13/project-atlas")
    assert target.name == "pre-commit"
    text = target.read_text(encoding="utf-8")
    assert lg.HOOK_MARKER in text
    assert f'--agent "{ME}"' in text
    assert '--repo "B0LK13/project-atlas"' in text
    assert str(dag.resolve()) in text
    assert target.stat().st_mode & 0o111


def test_install_hook_refuses_to_clobber_foreign_hook(tmp_path):
    repo = _git_repo(tmp_path)
    hooks = Path(subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=repo,
                                capture_output=True, text=True, check=True).stdout.strip())
    hooks = hooks if hooks.is_absolute() else repo / hooks
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\necho someone-elses-hook\n", encoding="utf-8")
    with pytest.raises(lg.LaneGuardError, match="FOREIGN_PRE_COMMIT_HOOK_PRESENT"):
        lg.install_hook(repo, agent_id=ME, dag_script=REPO_ROOT / "scripts" / "atlas-dag.py")
    assert "someone-elses-hook" in (hooks / "pre-commit").read_text(encoding="utf-8")


def test_install_hook_is_idempotent_over_its_own_hook(tmp_path):
    repo = _git_repo(tmp_path)
    dag = REPO_ROOT / "scripts" / "atlas-dag.py"
    first = lg.install_hook(repo, agent_id=ME, dag_script=dag)
    second = lg.install_hook(repo, agent_id=OTHER, dag_script=dag)
    assert first == second
    assert f'--agent "{OTHER}"' in second.read_text(encoding="utf-8")


def test_install_hook_requires_identity_and_git_worktree(tmp_path):
    with pytest.raises(lg.LaneGuardError, match="AGENT_IDENTITY_UNSET"):
        lg.install_hook(_git_repo(tmp_path), agent_id=" ", dag_script=REPO_ROOT / "x")
    with pytest.raises(lg.LaneGuardError, match="NOT_A_GIT_WORKTREE"):
        lg.install_hook(tmp_path / "nope", agent_id=ME, dag_script=REPO_ROOT / "x")


def test_installed_hook_blocks_commit_when_lane_not_owned(tmp_path, monkeypatch):
    """End-to-end: the hook actually stops `git commit` (bus resolution stubbed)."""
    repo = _git_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feat/x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    # Stand-in for atlas-dag.py: refuses unless branch is feat/owned.
    stub = tmp_path / "atlas-dag.py"
    stub.write_text(
        "import sys\n"
        "argv = sys.argv[1:]\n"
        "branch = argv[argv.index('--branch') + 1]\n"
        "sys.exit(0 if branch == 'feat/owned' else 1)\n",
        encoding="utf-8",
    )
    lg.install_hook(repo, agent_id=ME, dag_script=stub)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    blocked = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "try"],
                             capture_output=True, text=True)
    assert blocked.returncode != 0
    assert subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
                          capture_output=True).returncode != 0
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feat/owned"], check=True)
    ok = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "ok"],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
