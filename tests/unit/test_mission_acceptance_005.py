"""AS-ACCEPT-005 -- the acceptance runner's own guarantees.

These test the RUNNER, not the mission machinery underneath it. The
properties that matter are refusals and blast radius: it must not execute
without explicit permission, must not silently run against a different
checkout, and must clean up only what it created.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "acceptance"))

import mission_accept as ma  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/acceptance/mission_accept.py"),
         "--repo-root", str(REPO_ROOT), *args],
        capture_output=True, text=True, check=False,
    )


def test_execution_requires_explicit_permission(tmp_path: Path):
    """No flag, no subprocesses. A Studio packet can never substitute."""
    out = tmp_path / "ev.json"
    p = _run("--json-out", str(out))
    assert p.returncode == 0, p.stderr[-800:]
    ev = json.loads(out.read_text(encoding="utf-8"))
    assert ev["authority"]["execution_permission"].startswith("NOT GRANTED")
    assert ev["authority"]["studio_can_authorize"] is False
    assert "missions" not in ev or ev["missions"] == []
    assert "not authorized" in ev["verdict"]


def test_trusted_policy_is_a_caller_literal():
    assert ma.TRUSTED_POLICY == {"MERGE_AUTHORIZATION": "NO"}
    src = (REPO_ROOT / "scripts/acceptance/mission_accept.py").read_text(encoding="utf-8")
    # the policy must not be read out of the Studio packet anywhere
    assert "packet" not in src.split("TRUSTED_POLICY: dict[str, Any] =")[1].split("\n")[0]


def test_idempotency_key_includes_the_adapter():
    """The default key omits the command; two actions at one commit collide.

    The runner must not rely on that default -- see the reproduction in
    docs/atlas-3/acceptance/AS-ACCEPT-005.md.
    """
    a = ma._adapter_digest(("/bin/echo", "a"))
    b = ma._adapter_digest(("/bin/echo", "b"))
    assert a != b
    assert len(a) == 16


def test_preflight_rejects_import_leakage(tmp_path: Path, monkeypatch):
    """A checkout whose project_atlas resolves elsewhere must fail closed."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"],
                   cwd=str(tmp_path), check=True)
    res = ma.preflight(tmp_path, strict_pins=False)
    assert res.ok is False
    assert "OUTSIDE" in res.detail or "partial assembly" in res.detail


def test_preflight_reports_partial_assembly(tmp_path: Path):
    """Missing bridge/mission modules are named, not silently tolerated."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"],
                   cwd=str(tmp_path), check=True)
    res = ma.preflight(tmp_path, strict_pins=False)
    assert res.ok is False
    assert "mission_bridge.py" in res.detail or "orchestration/mission" in res.detail


def test_preflight_passes_on_this_checkout():
    res = ma.preflight(REPO_ROOT, strict_pins=False)
    assert res.ok, res.detail
    assert res.diagnostics["head"]
    assert Path(res.diagnostics["project_atlas_from"]).is_relative_to(REPO_ROOT)


def test_strict_pins_fails_when_a_component_is_absent(monkeypatch):
    """--strict-pins turns an absent pinned head into a hard failure."""
    monkeypatch.setitem(ma.EXPECTED_PINS, "999", "0" * 40)
    res = ma.preflight(REPO_ROOT, strict_pins=True)
    assert res.ok is False
    assert "#999" in res.detail
    monkeypatch.undo()


def test_pin_absence_is_only_a_warning_by_default(monkeypatch):
    monkeypatch.setitem(ma.EXPECTED_PINS, "999", "0" * 40)
    res = ma.preflight(REPO_ROOT, strict_pins=False)
    assert res.ok, res.detail
    assert any("#999" in w for w in res.diagnostics.get("pin_warnings", []))
    monkeypatch.undo()


def test_cleanup_removes_only_what_the_run_created(tmp_path: Path):
    caller_file = tmp_path / "caller-owned.txt"
    caller_file.write_text("do not touch", encoding="utf-8")
    res = ma.RunResources(REPO_ROOT, keep=False)
    ws = res.plain_workspace("m1")
    (ws / "made-by-run.txt").write_text("x", encoding="utf-8")
    root = res.root
    report = res.cleanup()
    assert report["root_removed"] is True
    assert not root.exists()
    assert caller_file.read_text(encoding="utf-8") == "do not touch"


def test_keep_retains_and_says_so(tmp_path: Path):
    res = ma.RunResources(REPO_ROOT, keep=True)
    ws = res.plain_workspace("m1")
    report = res.cleanup()
    assert report["kept"] is True
    assert "note" in report
    assert ws.exists()
    import shutil
    shutil.rmtree(res.root, ignore_errors=True)


def _registered_worktrees() -> set[Path]:
    """Registered worktree paths, RESOLVED.

    Never compare these as raw strings: on Windows `git worktree list` prints
    forward slashes and the long account name (`.../runneradmin/...`) while
    `str(Path(...))` gives backslashes and may carry an 8.3 short name
    (`RUNNER~1`). Both spellings denote one path, so resolve before comparing.
    """
    out = subprocess.run(["git", "worktree", "list", "--porcelain"],
                         cwd=str(REPO_ROOT), capture_output=True, text=True).stdout
    paths: set[Path] = set()
    for line in out.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line[len("worktree "):].strip()).resolve())
    return paths


def test_worktree_cleanup_leaves_no_registration():
    """A disposable checkout must not linger in the caller's .git/worktrees."""
    before = _registered_worktrees()
    res = ma.RunResources(REPO_ROOT, keep=False)
    wt = res.worktree("probe", "HEAD")
    assert wt.is_dir()
    during = _registered_worktrees()
    assert wt.resolve() in during, f"{wt.resolve()} not among {during}"
    assert during == before | {wt.resolve()}
    res.cleanup()
    after = _registered_worktrees()
    assert wt.resolve() not in after
    assert after == before


def test_studio_packet_supplies_context_not_authority(tmp_path: Path):
    """A packet claiming to grant authority is refused by the bridge."""
    packet = tmp_path / "p.json"
    packet.write_text(json.dumps({
        "schema": "ATLAS_STUDIO_TASK_CONTEXT_V1",
        "lane": "pr/999", "agent": {"agent_id": "ubuntu-main"},
        "freshness": {"state": "LIVE"},
        "next_step": {"status": "SUPPORTED", "authorization": "GRANTED",
                      "action": {"action_type": "X", "action_class": "READONLY"}},
    }), encoding="utf-8")
    got = ma.stage_studio(packet, "ubuntu-main")
    assert got["state"] == "REFUSED_BY_STUDIO"
    assert got["error"] == "StudioAuthorityError"


def test_missing_packet_is_not_an_error():
    got = ma.stage_studio(None, "ubuntu-main")
    assert got["state"] == "NOT_SUPPLIED"


def test_missions_declare_expected_task_outcomes():
    """A failing mission must EXPECT failure, so a pass would be a regression."""
    labels = {m.label: m.expect_task_ok for m in ma.MISSIONS}
    assert labels["passing_change"] is True
    assert labels["intentional_test_failure"] is False
    assert labels["real_checkout"] is True
