"""AS-ORCH-001C hook stdin/stdout contract and cwd-independent root resolution."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from project_atlas.orchestration.cursor_bridge import STATE_RELATIVE, stage_result

REPO = Path(__file__).resolve().parents[2]
HOOK_SRC = REPO / ".cursor" / "hooks" / "atlas_stop.py"


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": "local", "agent_id": "local-agent"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {"receipt_id": "ASR-1234567890abcdef", "status": "valid"},
        "blockers": [],
        "requested_transition": None,
    }
    data.update(overrides)
    return data


def _install_hook(repo: Path) -> Path:
    dest = repo / ".cursor" / "hooks" / "atlas_stop.py"
    dest.parent.mkdir(parents=True)
    shutil.copy2(HOOK_SRC, dest)
    shutil.copy2(REPO / ".cursor" / "hooks.json", repo / ".cursor" / "hooks.json")
    return dest


def _invoke(hook: Path, payload: object, *, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload,
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def test_hook_task_route_stdout_is_pure_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hook = _install_hook(repo)
    stage_result(_payload(), root=repo)
    code, stdout, _stderr = _invoke(
        hook, {"status": "completed", "loop_count": 0, "conversation_id": "c"}, cwd=tmp_path
    )
    assert code == 0
    assert stdout.endswith("\n")
    parsed = json.loads(stdout)
    assert set(parsed) == {"followup_message"}
    assert "[ATLAS_CURSOR_BRIDGE]" in parsed["followup_message"]
    assert "\x1b" not in stdout
    assert not stdout.lstrip().startswith("#")
    assert "INFO" not in stdout


def test_hook_owner_gate_and_terminal_and_aborted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hook = _install_hook(repo)
    stage_result(
        _payload(producer={"role": "integration", "agent_id": "iv"}, state="MERGE_ELIGIBLE"),
        root=repo,
    )
    code, stdout, _stderr = _invoke(hook, {"status": "completed", "loop_count": 0}, cwd=tmp_path)
    assert code == 0
    assert "OWNER_REQUIRED" in json.loads(stdout)["followup_message"]

    other = tmp_path / "term"
    other.mkdir()
    hook2 = _install_hook(other)
    stage_result(_payload(receipt=None), root=other)
    code, stdout, _stderr = _invoke(hook2, {"status": "completed", "loop_count": 0}, cwd=tmp_path)
    assert code == 0
    assert json.loads(stdout) == {}

    code, stdout, _stderr = _invoke(hook, {"status": "aborted", "loop_count": 0}, cwd=tmp_path)
    assert json.loads(stdout) == {}
    code, stdout, _stderr = _invoke(hook, {"status": "error", "loop_count": 0}, cwd=tmp_path)
    assert json.loads(stdout) == {}
    code, stdout, _stderr = _invoke(hook, {"status": "completed", "loop_count": 1}, cwd=tmp_path)
    assert json.loads(stdout) == {}


def test_hook_invalid_stdin_and_missing_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hook = _install_hook(repo)
    code, stdout, stderr = _invoke(hook, b"{", cwd=tmp_path)
    assert code == 0
    assert json.loads(stdout) == {}
    assert "invalid stdin JSON" in stderr
    code, stdout, _stderr = _invoke(hook, {"status": "completed", "loop_count": 0}, cwd=tmp_path)
    assert json.loads(stdout) == {}


def test_hook_tampered_state_returns_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hook = _install_hook(repo)
    stage_result(_payload(), root=repo)
    path = repo / STATE_RELATIVE
    broken = json.loads(path.read_text(encoding="utf-8"))
    broken["route"]["target"]["role"] = "autonomous"
    path.write_text(json.dumps(broken), encoding="utf-8")
    code, stdout, _stderr = _invoke(hook, {"status": "completed", "loop_count": 0}, cwd=tmp_path)
    assert code == 0
    assert json.loads(stdout) == {}


def test_hook_cwd_independence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    foreign = tmp_path / "foreign-cwd"
    repo.mkdir()
    foreign.mkdir()
    hook = _install_hook(repo)
    stage_result(_payload(), root=repo)
    code, stdout, _stderr = _invoke(hook, {"status": "completed", "loop_count": 0}, cwd=foreign)
    assert code == 0
    assert "candidate_verification" in json.loads(stdout)["followup_message"]
    assert not (foreign / STATE_RELATIVE).exists()
    assert (repo / STATE_RELATIVE).is_file()


def test_runtime_state_is_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".atlas/orchestration/cursor/state.json"],
        cwd=REPO,
        check=False,
    )
    assert proc.returncode == 0
