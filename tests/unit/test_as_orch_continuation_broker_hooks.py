"""D-081 hook adapter: worktree src binding and stale-install resistance."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from project_atlas.orchestration.autonomy.continuation_broker import (
    BROKER_MARKER,
    SuccessorKind,
    enqueue_successor,
)
from project_atlas.orchestration.autonomy.models import CANONICAL_REPOSITORY_IDENTITY

REPO = Path(__file__).resolve().parents[2]
PIN = "7e797468a2eca37c959920912b1fa264df4be638"
TREE = "3cb40645c343edf8f8ab95f6ddf3a819e2110ef2"


def _install_hooks(repo: Path) -> Path:
    dest = repo / ".cursor" / "hooks"
    dest.mkdir(parents=True)
    hook_src = REPO / ".cursor" / "hooks"
    for name in (
        "atlas_stop.py",
        "atlas_before_submit.py",
        "atlas_hook_runtime.py",
        "atlas_hook_launch.py",
    ):
        shutil.copy2(hook_src / name, dest / name)
    shutil.copy2(REPO / ".cursor" / "hooks.json", repo / ".cursor" / "hooks.json")
    src_dst = repo / "src"
    try:
        src_dst.symlink_to(REPO / "src", target_is_directory=True)
    except OSError:
        shutil.copytree(REPO / "src", src_dst)
    return dest / "atlas_stop.py"


def _invoke(hook: Path, payload: object, *, cwd: Path, env: dict[str, str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=cwd,
        capture_output=True,
        check=False,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def test_stale_installed_package_does_not_win_over_worktree_src(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hook = _install_hooks(repo)
    enqueue_successor(
        repo,
        cycle_id="CYCLE-WT",
        kind=SuccessorKind.CHECKPOINT_CONTINUE,
        trusted_main=PIN,
        trusted_tree=TREE,
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
    )
    stale = tmp_path / "stale"
    stale_pkg = stale / "project_atlas" / "orchestration"
    stale_pkg.mkdir(parents=True)
    (stale / "project_atlas" / "__init__.py").write_text("", encoding="utf-8")
    (stale / "project_atlas" / "orchestration" / "__init__.py").write_text("", encoding="utf-8")
    (stale_pkg / "cursor_bridge.py").write_text(
        "def handle_stop_event(payload, *, root):\n"
        "    return {'followup_message': 'STALE_PACKAGE'}\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(stale) + os.pathsep + env.get("PYTHONPATH", "")
    code, stdout, stderr = _invoke(
        hook,
        {"status": "completed", "loop_count": 0, "conversation_id": "stale-attack"},
        cwd=tmp_path,
        env=env,
    )
    assert code == 0
    parsed = json.loads(stdout)
    assert parsed.get("followup_message") != "STALE_PACKAGE"
    assert BROKER_MARKER in parsed["followup_message"]
    assert "MODULE_ROOT_MISMATCH" not in stderr
    trace = (
        repo / ".atlas" / "orchestration" / "continuation-broker" / "hook-trace.jsonl"
    ).read_text(encoding="utf-8")
    assert "STOP_HOOK_FIRED" in trace
    assert '"module_root_match": true' in trace
    assert "STALE_PACKAGE" not in trace


def test_before_submit_hook_consumes_worktree_successor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    stop = _install_hooks(repo)
    enqueue_successor(
        repo,
        cycle_id="CYCLE-BS",
        kind=SuccessorKind.CI_PENDING_WITH_OBSERVER,
        trusted_main=PIN,
        trusted_tree=TREE,
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        next_action_class="MONITOR_EXACT_HEAD_CI",
    )
    env = os.environ.copy()
    code, stdout, _stderr = _invoke(
        stop,
        {"status": "completed", "loop_count": 1, "conversation_id": "bs"},
        cwd=tmp_path,
        env=env,
    )
    assert code == 0
    followup = json.loads(stdout)["followup_message"]
    before = stop.with_name("atlas_before_submit.py")
    code, stdout, _stderr = _invoke(
        before,
        {"prompt": followup, "conversation_id": "bs"},
        cwd=tmp_path,
        env=env,
    )
    assert code == 0
    assert json.loads(stdout) == {"continue": True}
    state = json.loads(
        (repo / ".atlas" / "orchestration" / "continuation-broker" / "current.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["phase"] == "CONSUMED"
    assert state["cycle_id"] == "CYCLE-BS"
