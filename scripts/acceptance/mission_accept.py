"""AS-ACCEPT-005 -- reusable mission acceptance from a clean checkout.

One command another engineer can run without reconstructing the original
session. It does NOT introduce an orchestration framework: every stage
calls the components that already exist --

    project_atlas.orchestration.mission.context_packet   knowledge
    project_atlas.orchestration.mission.execution        bounded execution
    project_atlas.orchestration.mission.recovery         reconciliation
    atlas_studio.mission_bridge                          Studio -> mission seam

WHAT AUTHORIZES THE SUBPROCESSES

`--i-authorize-bounded-execution` (or `ATLAS_ACCEPT_EXECUTE=1`), plus
`TRUSTED_POLICY` below, which is a literal owned by THIS caller. A Studio
task-context packet can supply context and can REFUSE a run; it can never
authorize one. Without the flag, the runner does preflight and planning only.

CALLER STATE

Every workspace is created by this run under a single run-scoped root and
is removed by this run. Disposable checkouts are made with `git worktree`
and are `git worktree remove`d, so no registration is left in the caller's
`.git/worktrees`. Nothing outside the run root is written. `--keep` retains
workspaces for inspection and then says so explicitly.

IDEMPOTENCY KEYS ARE EXPLICIT HERE ON PURPOSE

`execution.start_mission_run`'s DEFAULT key is `f"{mission_id}:{base_head}"`,
which does not include the adapter command: two different commands at the
same commit collide, and the second silently returns the first's result
(reproduced -- see `docs/atlas-3/acceptance/AS-ACCEPT-005.md`). This runner
therefore always passes an explicit key that includes an adapter digest.
That is a mitigation in this caller, not a fix in #789.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "ATLAS_MISSION_ACCEPTANCE_V1"
PACKAGE = "AS-ACCEPT-005"

def _spawn_kwargs() -> dict[str, Any]:
    """Popen kwargs making a worker killable as a tree on POSIX and Windows."""
    import execution_env as _ee
    return _ee.spawn_kwargs()


def _hard_kill(proc: subprocess.Popen) -> None:
    import execution_env as _ee
    _ee.hard_kill_tree(proc)


#: Mirror of `project_atlas.orchestration.mission.MISSION_STATE_DIR_NAME`.
#:
#: Duplicated ON PURPOSE. Under --isolated-execution the parent must not import
#: the candidate at all -- the whole point is that the candidate runs only in
#: the provisioned interpreter -- but the parent still has to poll for the
#: worker's checkpoint before that worker finishes. A test asserts this string
#: still matches the package's value wherever the package IS importable, so the
#: duplication cannot drift silently.
MISSION_STATE_DIR = ".atlas-mission"

#: This caller's OWN authority. Never sourced from a Studio packet.
TRUSTED_POLICY: dict[str, Any] = {"MERGE_AUTHORIZATION": "NO"}

#: Component heads this acceptance run is written against.
EXPECTED_PINS: dict[str, str] = {
    "791": "181f2ebaa756a6f64149fa4f7cae098be5ad7524",
    "786": "1082b1e4381069f142c546c5adcc37070f4f7103",
    "781": "750586a678eb3a5fe44994141afa2ac73bdb0845",
    "789": "1c6bd038c2cc8ee2e6da4c902e6504cfe07852e2",
}
EXPECTED_BASE = "b87b4a226f4aa8b2f669edf112aa3476454f754f"


class PreflightError(Exception):
    """A prerequisite is missing or the checkout is not what was expected."""


@dataclass
class StageResult:
    name: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _git(args: list[str], cwd: Path, check: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise PreflightError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def _adapter_digest(command: tuple[str, ...]) -> str:
    return hashlib.sha256("\x00".join(command).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- preflight

def preflight(repo_root: Path, *, strict_pins: bool,
              isolated_execution: bool = False) -> StageResult:
    """Prerequisites, repository identity, and explicit source pins."""
    diag: dict[str, Any] = {}
    problems: list[str] = []

    diag["python"] = sys.version.split()[0]
    diag["platform"] = f"{platform.system()} {platform.machine()}"
    if (sys.version_info.major, sys.version_info.minor) < (3, 12):
        problems.append(f"Python >= 3.12 required, found {diag['python']}")

    if shutil.which("git") is None:
        problems.append("git not found on PATH")
    else:
        diag["git"] = _git(["--version"], repo_root, check=False)

    # The checkout must be a git repo, and the one we are importing FROM.
    try:
        top = Path(_git(["rev-parse", "--show-toplevel"], repo_root)).resolve()
    except PreflightError as exc:
        return StageResult("preflight", False, str(exc), diagnostics=diag)
    diag["repo_root"] = str(top)
    diag["head"] = _git(["rev-parse", "HEAD"], top)
    diag["tree"] = _git(["rev-parse", "HEAD^{tree}"], top)

    # Import leakage: the installed package MUST come from this checkout,
    # otherwise the run silently exercises a different working tree.
    try:
        import project_atlas
        pkg = Path(project_atlas.__file__).resolve()
        diag["project_atlas_from"] = str(pkg)
        if top not in pkg.parents:
            msg = (
                f"project_atlas resolves to {pkg}, which is OUTSIDE {top}. "
                f"Run `pip install -e .[dev]` inside this checkout; subprocess "
                f"tests resolve through the install, not PYTHONPATH."
            )
            if isolated_execution:
                # Under --isolated-execution the engine runs from a wheel built
                # from the selected commit, in its own venv. The caller's import
                # origin is then IRRELEVANT to what executes -- recording it is
                # useful, failing on it would be wrong.
                diag.setdefault("import_origin_warnings", []).append(
                    msg + " (informational under --isolated-execution: the mission "
                          "engine does not run from the caller's environment)"
                )
            else:
                problems.append(msg)
    except ImportError as exc:
        msg = f"project_atlas not importable: {exc} -- run `pip install -e .[dev]`"
        if isolated_execution:
            diag.setdefault("import_origin_warnings", []).append(msg)
        else:
            problems.append(msg)

    scripts = top / "scripts"
    if not (scripts / "atlas_studio").is_dir():
        problems.append(f"missing {scripts / 'atlas_studio'} (incomplete assembly)")
    for mod in ("mission_bridge.py", "mission_session.py", "task_context.py"):
        if not (scripts / "atlas_studio" / mod).is_file():
            problems.append(f"missing scripts/atlas_studio/{mod} -- partial assembly")
    if not (top / "src/project_atlas/orchestration/mission/execution.py").is_file():
        problems.append("missing orchestration/mission -- #789 not present in this checkout")

    # Explicit source pins: are the components we were written against here?
    pins: dict[str, Any] = {"expected_base": EXPECTED_BASE, "components": {}}
    for pr, sha in EXPECTED_PINS.items():
        rc = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                            cwd=str(top), capture_output=True)
        ok = rc.returncode == 0
        pins["components"][f"#{pr}"] = {"sha": sha, "present": ok}
        if not ok:
            msg = f"pinned head for #{pr} ({sha[:8]}) is not an ancestor of HEAD"
            (problems if strict_pins else diag.setdefault("pin_warnings", [])).append(msg)
    diag["pins"] = pins

    if problems:
        return StageResult("preflight", False, "; ".join(problems),
                           data=pins, diagnostics=diag)
    return StageResult("preflight", True, "prerequisites, identity and pins verified",
                       data=pins, diagnostics=diag)


# ------------------------------------------------------------- run resources

class RunResources:
    """Everything this run creates, so cleanup targets ONLY these."""

    def __init__(self, repo_root: Path, keep: bool) -> None:
        self.repo_root = repo_root
        self.keep = keep
        self.root = Path(tempfile.mkdtemp(prefix="atlas-accept-"))
        self.worktrees: list[Path] = []
        #: set only when THIS run created the env cache; a caller-supplied
        #: --env-cache is never removed, because we did not create it.
        self.env_cache: Path | None = None

    def plain_workspace(self, name: str) -> Path:
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def worktree(self, name: str, commit: str) -> Path:
        p = self.root / name
        subprocess.run(["git", "worktree", "add", "--detach", str(p), commit],
                       cwd=str(self.repo_root), capture_output=True, text=True, check=True)
        self.worktrees.append(p)
        return p

    def cleanup(self) -> dict[str, Any]:
        """Remove only what this run created. Never touches caller files."""
        report: dict[str, Any] = {"kept": self.keep, "root": str(self.root),
                                  "worktrees_removed": [], "errors": [],
                                  "env_cache_removed": None,
                                  "caller_env_cache_preserved": self.env_cache is None}
        if self.keep:
            report["note"] = "--keep: workspaces retained for inspection; remove them yourself"
            return report
        for wt in self.worktrees:
            r = subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                               cwd=str(self.repo_root), capture_output=True, text=True)
            if r.returncode == 0:
                report["worktrees_removed"].append(str(wt))
            else:
                report["errors"].append(f"worktree remove {wt}: {r.stderr.strip()}")
        if self.env_cache is not None and self.env_cache.exists():
            # Only a cache this run created. Anything under a caller-supplied
            # --env-cache stays put.
            shutil.rmtree(self.env_cache, ignore_errors=True)
            report["env_cache_removed"] = str(self.env_cache)
        shutil.rmtree(self.root, ignore_errors=True)
        report["root_removed"] = not self.root.exists()
        return report


# ---------------------------------------------------------------- missions

@dataclass
class Mission:
    """One permitted disposable engineering task."""

    mission_id: str
    objective: str
    keywords: list[str]
    #: builds the command to run inside the workspace
    build: Any
    #: what a SUCCESSFUL TASK looks like -- distinct from "the command ran"
    expect_task_ok: bool
    label: str
    #: workspace must be a real disposable git checkout, not an empty dir
    needs_checkout: bool = False


def _write(path: Path, text: str, mode: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)
    return path


def mission_passing_change(ws: Path) -> tuple[str, ...]:
    """A real source change plus a test that proves it -- task SUCCEEDS."""
    _write(ws / "acc_mod.py", "def slugify(s):\n    return '-'.join(s.lower().split())\n")
    _write(ws / "test_acc_mod.py",
           "from acc_mod import slugify\n"
           "def test_basic():\n    assert slugify('Hello World') == 'hello-world'\n"
           "def test_collapses_runs():\n    assert slugify('a   b') == 'a-b'\n")
    return (sys.executable, "-m", "pytest", "test_acc_mod.py",
            "-p", "no:cacheprovider", "--no-cov", "-q")


def mission_failing_tests(ws: Path) -> tuple[str, ...]:
    """The command RUNS FINE; the engineering task FAILS. Not the same thing."""
    _write(ws / "acc_bug.py", "def add(a, b):\n    return a - b   # deliberate defect\n")
    _write(ws / "test_acc_bug.py",
           "from acc_bug import add\n"
           "def test_add():\n    assert add(2, 2) == 4\n")
    return (sys.executable, "-m", "pytest", "test_acc_bug.py",
            "-p", "no:cacheprovider", "--no-cov", "-q")


def mission_interrupted(ws: Path) -> tuple[str, ...]:
    """Long-running task, killed by the runner mid-flight."""
    _write(ws / "slow.sh", "#!/bin/sh\nsleep 120\n", 0o755)
    return (str(ws / "slow.sh"),)


def mission_repo_checkout(ws: Path) -> tuple[str, ...]:
    """Workspace IS a real repository checkout.

    #789 calls this out as expected usage -- the lease then protects exclusive
    ownership of that checkout during the run. It exercises a different risk
    from the synthetic missions: operational state must land under
    `.atlas-mission/` rather than loose in the repo root, and the disposable
    checkout must be removable afterwards without touching the caller's repo.

    LIMIT, stated because it is easy to over-read: the workspace is a real
    checkout, but the Python code under test still resolves through the
    editable install in the CALLER's environment, not from this worktree's own
    `src/`. Verified directly -- running inside the worktree,
    `project_atlas.__file__` points back at the clone. So this mission covers
    the lease, workspace hygiene and cleanup; it does NOT prove anything about
    the worktree's own source copy. That is the same editable-install
    resolution that `preflight` guards against, wearing a different hat.
    """
    return (sys.executable, "-m", "pytest",
            "tests/unit/test_atlas_studio_mission_bridge.py",
            "-p", "no:cacheprovider", "--no-cov", "-q")


MISSIONS: list[Mission] = [
    Mission("accept-passing-change",
            "Add slugify() and prove it with tests",
            ["backlog", "studio", "test"], mission_passing_change, True, "passing_change"),
    Mission("accept-failing-tests",
            "Run a suite against a known-defective implementation",
            ["backlog", "test"], mission_failing_tests, False, "intentional_test_failure"),
    Mission("accept-repo-checkout",
            "Run the bridge suite inside a real disposable checkout",
            ["studio", "bridge"], mission_repo_checkout, True, "real_checkout",
            needs_checkout=True),
]


# ------------------------------------------------------------------- stages

def stage_knowledge(repo_root: Path, mission: Mission):
    from project_atlas.orchestration.mission.context_packet import compile_mission_context
    return compile_mission_context(
        repo_root, mission_id=mission.mission_id, objective=mission.objective,
        keywords=mission.keywords, trusted_policy=TRUSTED_POLICY,
    )


def stage_studio(packet_path: Path | None, agent: str) -> dict[str, Any]:
    """Optional. Studio can REFUSE; it can never authorize."""
    if packet_path is None or not packet_path.is_file():
        return {"state": "NOT_SUPPLIED",
                "note": "Studio packet optional; it supplies context, never authority"}
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from atlas_studio import mission_bridge as mb
    try:
        got = mb.build_mission_inputs(json.loads(packet_path.read_text(encoding="utf-8")),
                                      expected_agent_id=agent)
        return {"state": "CARRIED_AS_DATA", "lane": got.lane,
                "action_type": got.action_type, "action_class": got.action_class,
                "lane_head": got.lane_head, "freshness": got.freshness_state,
                "authorization": "NOT_GRANTED_BY_THIS_PACKET"}
    except mb.StudioBridgeError as exc:
        return {"state": "REFUSED_BY_STUDIO", "error": type(exc).__name__, "detail": str(exc)}


def run_mission(repo_root: Path, res: RunResources, mission: Mission,
                *, interrupt: bool = False) -> dict[str, Any]:
    """Execute one mission and return machine-readable evidence."""
    from project_atlas.orchestration.mission import execution as ex
    from project_atlas.orchestration.mission.adapter import ShellCommandAdapter

    out: dict[str, Any] = {"mission_id": mission.mission_id, "label": mission.label}
    if mission.needs_checkout:
        ws = res.worktree(mission.mission_id, "HEAD")
        out["workspace_kind"] = "disposable_git_worktree"
    else:
        ws = res.plain_workspace(mission.mission_id)
        out["workspace_kind"] = "plain_directory"
    out["workspace"] = str(ws)

    ctx = stage_knowledge(repo_root, mission)
    out["context"] = {"base_head": ctx.base_head, "base_tree": ctx.base_tree,
                      "decisions": len(ctx.decisions), "backlog_items": len(ctx.backlog_items),
                      "prior_work": len(ctx.prior_related_work),
                      "evidence_sources": len(ctx.evidence_links),
                      "trusted_policy": dict(ctx.trusted_policy),
                      "trusted_policy_origin": "CALLER_LITERAL_NOT_STUDIO"}

    command = mission.build(ws)
    key = f"{mission.mission_id}:{ctx.base_head}:{_adapter_digest(command)}"
    out["execution_identity"] = {"idempotency_key": key,
                                 "adapter_digest": _adapter_digest(command),
                                 "command": list(command),
                                 "key_includes_adapter": True}

    if interrupt:
        return _run_interrupted(repo_root, ws, ctx, command, key, mission, out)

    t0 = time.perf_counter()
    try:
        r = ex.start_mission_run(mission_id=mission.mission_id, context=ctx,
                                 adapter=ShellCommandAdapter(command=tuple(command)),
                                 workspace=ws, repo_root=repo_root,
                                 adapter_timeout_sec=300.0, idempotency_key=key)
    except Exception as exc:
        out["outcome"] = {"stage": "execution", "error": type(exc).__name__,
                          "detail": str(exc), "traceback": traceback.format_exc()[-1500:]}
        out["task_completed"] = False
        return out
    ar = r.adapter_result
    out["run"] = {"run_id": r.run_id, "deduplicated": r.deduplicated,
                  "checkpoint_state": r.checkpoint.state,
                  "wall_sec": round(time.perf_counter() - t0, 2)}
    out["command_result"] = {"spawned": ar is not None,
                             "returncode": ar.returncode if ar else None,
                             "failure_class": ar.failure_class if ar else None,
                             "stdout_tail": ((ar.stdout or "").strip().splitlines()[-3:]
                                             if ar else [])}
    # command success != task success
    task_ok = bool(ar and ar.ok)
    out["task_completed"] = task_ok
    out["expectation"] = {"expected_task_ok": mission.expect_task_ok,
                          "observed_task_ok": task_ok,
                          "as_expected": task_ok == mission.expect_task_ok}
    out["command_vs_task"] = (
        "command spawned and exited; task outcome is judged by exit status, "
        "NOT by whether the subprocess ran"
    )
    return out


def _worker_source(repo_root: Path, ws: Path, *, ctx_args, command, key,
                   emit_json: bool) -> str:
    """Source for a genuinely separate process that runs one mission.

    Built with repr() so paths, tuples and the policy dict survive exactly;
    a separate process is what makes "fresh-process resume" real rather than
    an in-process function call.
    """
    mission_id, objective, keywords = ctx_args
    lines = [
        "import sys, json",
        f"sys.path.insert(0, {str(repo_root / 'scripts')!r})",
        "from pathlib import Path",
        "from project_atlas.orchestration.mission.adapter import ShellCommandAdapter",
        "from project_atlas.orchestration.mission.context_packet import compile_mission_context",
        "from project_atlas.orchestration.mission.execution import start_mission_run",
        f"c = compile_mission_context(Path({str(repo_root)!r}), mission_id={mission_id!r},",
        f"    objective={objective!r}, keywords={keywords!r},",
        f"    trusted_policy={TRUSTED_POLICY!r})",
        f"r = start_mission_run(mission_id={mission_id!r}, context=c,",
        f"    adapter=ShellCommandAdapter(command={command!r}),",
        f"    workspace=Path({str(ws)!r}), repo_root=Path({str(repo_root)!r}),",
        f"    adapter_timeout_sec=300.0, idempotency_key={key!r})",
    ]
    if emit_json:
        lines.append(
            "print(json.dumps({'deduplicated': r.deduplicated, 'run_id': r.run_id,"
            " 'state': r.checkpoint.state}))"
        )
    return "\n".join(lines) + "\n"


def _run_interrupted(repo_root: Path, ws: Path, ctx, command, key,
                     mission: Mission, out: dict[str, Any]) -> dict[str, Any]:
    """Kill a real worker mid-adapter, then reconcile. Never auto-replays."""

    from project_atlas.orchestration.mission import (
        MISSION_STATE_DIR_NAME,
    )
    from project_atlas.orchestration.mission import (
        execution as ex,
    )
    from project_atlas.orchestration.mission import (
        recovery as rec,
    )

    worker = _worker_source(
        repo_root, ws, ctx_args=(mission.mission_id, mission.objective, mission.keywords),
        command=tuple(command), key=key, emit_json=False,
    )

    p = subprocess.Popen([sys.executable, "-c", worker], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, **_spawn_kwargs())
    cp_path = ws / MISSION_STATE_DIR_NAME / "mission-run-checkpoint.json"
    appeared = False
    for _ in range(400):
        time.sleep(0.25)
        if cp_path.exists():
            appeared = True
            break
        if p.poll() is not None:
            break
    if not appeared:
        p.kill()
        p.wait()
        out["outcome"] = {"stage": "interrupt", "error": "worker never checkpointed"}
        out["task_completed"] = False
        return out

    _hard_kill(p)
    time.sleep(0.3)

    r = rec.reconcile_mission_run(ws)
    out["interruption"] = {"killed_signal": "SIGKILL", "process_group": True,
                           "reconcile_outcome": r.outcome,
                           "safe_to_retry": r.safe_to_retry,
                           "detail": r.detail[:200], "run_id": r.run_id}
    # A new run must be BLOCKED, not silently replayed.
    blocked = False
    try:
        from project_atlas.orchestration.mission.adapter import ShellCommandAdapter
        ex.start_mission_run(mission_id=mission.mission_id, context=ctx,
                             adapter=ShellCommandAdapter(command=tuple(command)),
                             workspace=ws, repo_root=repo_root,
                             adapter_timeout_sec=10.0, idempotency_key=key)
    except ex.UnreconciledPriorRunError as exc:
        blocked = True
        out["interruption"]["next_run_blocked_with"] = str(exc)[:160]
    out["interruption"]["auto_replay_prevented"] = blocked
    out["task_completed"] = False
    out["expectation"] = {"expected_task_ok": False, "observed_task_ok": False,
                          "as_expected": blocked and not r.safe_to_retry}
    return out


def stage_resume(repo_root: Path, mission: Mission, ws: Path, key: str,
                 command: tuple[str, ...]) -> dict[str, Any]:
    """Fresh-process resume: same key must NOT repeat the measured effect."""
    probe = _worker_source(
        repo_root, ws, ctx_args=(mission.mission_id, mission.objective, mission.keywords),
        command=tuple(command), key=key, emit_json=True,
    )

    p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    if p.returncode != 0:
        return {"state": "RESUME_FAILED", "stderr": p.stderr.strip()[-500:]}
    data = json.loads(p.stdout.strip().splitlines()[-1])
    return {"state": "RESUMED_IN_FRESH_PROCESS", **data,
            "effect_repeated": not data["deduplicated"]}




# ------------------------------------------------- isolated mission worker

def _isolated_worker_source(repo_root: Path, ws: Path, *, mission_id: str, objective: str,
                            keywords: list[str], command: tuple[str, ...], key: str,
                            timeout: float) -> str:
    """Worker source for the ISOLATED interpreter.

    No `sys.path` manipulation at all -- that is the point. Every import must
    resolve through the provisioned distribution, and the worker reports where
    it actually resolved from so the parent can verify rather than assume.
    `atlas_studio` is deliberately NOT imported here: it lives in `scripts/`
    and is not part of the wheel, so it cannot be provenance-proven this way.
    """
    return "\n".join([
        "import json, sys",
        "import project_atlas",
        "from pathlib import Path",
        "from project_atlas.orchestration.mission.adapter import ShellCommandAdapter",
        "from project_atlas.orchestration.mission.context_packet import "
        "compile_mission_context",
        "from project_atlas.orchestration.mission.execution import start_mission_run",
        f"c = compile_mission_context(Path({str(repo_root)!r}), mission_id={mission_id!r},",
        f"    objective={objective!r}, keywords={keywords!r},",
        f"    trusted_policy={TRUSTED_POLICY!r})",
        f"r = start_mission_run(mission_id={mission_id!r}, context=c,",
        f"    adapter=ShellCommandAdapter(command={command!r}),",
        f"    workspace=Path({str(ws)!r}), repo_root=Path({str(repo_root)!r}),",
        f"    adapter_timeout_sec={timeout!r}, idempotency_key={key!r})",
        "ar = r.adapter_result",
        "print(json.dumps({",
        "  'run_id': r.run_id, 'deduplicated': r.deduplicated,",
        "  'checkpoint_state': r.checkpoint.state,",
        "  'returncode': ar.returncode if ar else None,",
        "  'ok': bool(ar and ar.ok),",
        "  'failure_class': ar.failure_class if ar else None,",
        "  'stdout_tail': ((ar.stdout or '').strip().splitlines()[-3:] if ar else []),",
        "  'worker_origin': project_atlas.__file__,",
        "  'worker_executable': sys.executable,",
        "  'worker_isolated': bool(sys.flags.isolated),",
        "  'worker_no_user_site': bool(sys.flags.no_user_site),",
        "}))",
    ]) + "\n"


def run_mission_isolated(repo_root: Path, res: RunResources, mission: Mission,
                         env_dir: Path, python: Path) -> dict[str, Any]:
    """Run one mission INSIDE the provisioned distribution and verify it did.

    The engine (`project_atlas.orchestration.mission`) executes in the isolated
    interpreter, not in the caller's. Provenance is checked on the worker's own
    report; a worker that cannot prove its origin fails the mission rather than
    being quietly accepted.
    """
    import execution_env as ee

    out: dict[str, Any] = {"mission_id": mission.mission_id, "label": mission.label,
                           "execution_mode": "ISOLATED_DISTRIBUTION"}
    if mission.needs_checkout:
        ws = res.worktree(mission.mission_id, "HEAD")
        out["workspace_kind"] = "disposable_git_worktree"
    else:
        ws = res.plain_workspace(mission.mission_id)
        out["workspace_kind"] = "plain_directory"
    out["workspace"] = str(ws)

    command = mission.build(ws)
    head = _git(["rev-parse", "HEAD"], repo_root)
    key = f"{mission.mission_id}:{head}:{_adapter_digest(command)}"
    out["execution_identity"] = {"idempotency_key": key,
                                 "adapter_digest": _adapter_digest(command),
                                 "command": list(command),
                                 "key_includes_adapter": True}

    src = _isolated_worker_source(repo_root, ws, mission_id=mission.mission_id,
                                  objective=mission.objective, keywords=mission.keywords,
                                  command=tuple(command), key=key, timeout=300.0)
    p = subprocess.run(ee.isolated_command(python, ["-c", src]),
                       capture_output=True, text=True, env=ee.clean_env())
    if p.returncode != 0:
        out["outcome"] = {"stage": "isolated_execution", "error": "WORKER_FAILED",
                          "detail": p.stderr.strip()[-1200:]}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": mission.expect_task_ok,
                              "observed_task_ok": False, "as_expected": False}
        return out
    try:
        data = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out["outcome"] = {"stage": "isolated_execution", "error": "UNPARSEABLE_WORKER_OUTPUT",
                          "detail": p.stdout[-800:]}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": mission.expect_task_ok,
                              "observed_task_ok": False, "as_expected": False}
        return out

    # Provenance is VERIFIED, never assumed, and a failure here fails the mission.
    try:
        ee.verify_import_origin(env_dir, {
            "origin": data["worker_origin"], "version": "verified-at-provision",
            "flags_isolated": data["worker_isolated"],
            "flags_no_user_site": data["worker_no_user_site"],
        })
        out["provenance"] = {"verified": True, "worker_origin": data["worker_origin"],
                             "worker_executable": data["worker_executable"],
                             "isolated": data["worker_isolated"],
                             "no_user_site": data["worker_no_user_site"]}
    except ee.ProvenanceError as exc:
        out["provenance"] = {"verified": False, "error": str(exc)}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": mission.expect_task_ok,
                              "observed_task_ok": False, "as_expected": False}
        return out

    out["run"] = {"run_id": data["run_id"], "deduplicated": data["deduplicated"],
                  "checkpoint_state": data["checkpoint_state"]}
    out["command_result"] = {"spawned": True, "returncode": data["returncode"],
                             "failure_class": data["failure_class"],
                             "stdout_tail": data["stdout_tail"]}
    task_ok = bool(data["ok"])
    out["task_completed"] = task_ok
    out["expectation"] = {"expected_task_ok": mission.expect_task_ok,
                          "observed_task_ok": task_ok,
                          "as_expected": task_ok == mission.expect_task_ok}
    out["command_vs_task"] = ("command spawned and exited; task outcome is judged by "
                              "exit status, NOT by whether the subprocess ran")
    return out



def run_interrupted_isolated(repo_root: Path, res: RunResources, mission: Mission,
                             env_dir: Path, python: Path) -> dict[str, Any]:
    """Kill a real worker running INSIDE the provisioned distribution.

    The reconciliation that follows is performed by the same distribution, so
    "uncertain outcome, no auto-replay" is a property of the candidate's code,
    not of whatever happens to be installed in the caller's environment.
    """

    import execution_env as ee

    out: dict[str, Any] = {"mission_id": mission.mission_id, "label": mission.label,
                           "execution_mode": "ISOLATED_DISTRIBUTION",
                           "workspace_kind": "plain_directory"}
    ws = res.plain_workspace(mission.mission_id)
    out["workspace"] = str(ws)
    command = mission.build(ws)
    head = _git(["rev-parse", "HEAD"], repo_root)
    key = f"{mission.mission_id}:{head}:{_adapter_digest(command)}"
    out["execution_identity"] = {"idempotency_key": key,
                                 "adapter_digest": _adapter_digest(command),
                                 "command": list(command), "key_includes_adapter": True}

    src = _isolated_worker_source(repo_root, ws, mission_id=mission.mission_id,
                                  objective=mission.objective, keywords=mission.keywords,
                                  command=tuple(command), key=key, timeout=300.0)
    p = subprocess.Popen(ee.isolated_command(python, ["-c", src]), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=ee.clean_env(), **_spawn_kwargs())
    cp_path = ws / MISSION_STATE_DIR / "mission-run-checkpoint.json"
    appeared = False
    for _ in range(400):
        time.sleep(0.25)
        if cp_path.exists():
            appeared = True
            break
        if p.poll() is not None:
            break
    if not appeared:
        p.kill()
        p.wait()
        out["outcome"] = {"stage": "interrupt", "error": "worker never checkpointed",
                          "worker_stderr": (p.stderr.read().decode(errors="replace")[-800:]
                                            if p.stderr else "")}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": False, "observed_task_ok": False,
                              "as_expected": False}
        return out

    _hard_kill(p)
    time.sleep(0.3)

    # Reconcile and re-attempt USING THE CANDIDATE, in a fresh isolated process.
    recon_src = "\n".join([
        "import json, sys",
        "import project_atlas",
        "from pathlib import Path",
        "from project_atlas.orchestration.mission import recovery as rec, execution as ex",
        "from project_atlas.orchestration.mission.adapter import ShellCommandAdapter",
        "from project_atlas.orchestration.mission.context_packet import "
        "compile_mission_context",
        f"r = rec.reconcile_mission_run(Path({str(ws)!r}))",
        "blocked = False",
        "err = None",
        f"c = compile_mission_context(Path({str(repo_root)!r}), "
        f"mission_id={mission.mission_id!r},",
        f"    objective={mission.objective!r}, keywords={mission.keywords!r},",
        f"    trusted_policy={TRUSTED_POLICY!r})",
        "try:",
        f"    ex.start_mission_run(mission_id={mission.mission_id!r}, context=c,",
        f"        adapter=ShellCommandAdapter(command={tuple(command)!r}),",
        f"        workspace=Path({str(ws)!r}), repo_root=Path({str(repo_root)!r}),",
        f"        adapter_timeout_sec=10.0, idempotency_key={key!r})",
        "except ex.UnreconciledPriorRunError as exc:",
        "    blocked = True",
        "    err = str(exc)[:160]",
        "print(json.dumps({'outcome': r.outcome, 'safe_to_retry': r.safe_to_retry,",
        "  'detail': r.detail[:200], 'run_id': r.run_id, 'blocked': blocked,",
        "  'blocked_with': err, 'worker_origin': project_atlas.__file__,",
        "  'worker_isolated': bool(sys.flags.isolated),",
        "  'worker_no_user_site': bool(sys.flags.no_user_site)}))",
    ]) + "\n"
    rp = subprocess.run(ee.isolated_command(python, ["-c", recon_src]),
                        capture_output=True, text=True, env=ee.clean_env())
    if rp.returncode != 0:
        out["outcome"] = {"stage": "reconcile", "error": "RECONCILER_FAILED",
                          "detail": rp.stderr.strip()[-1000:]}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": False, "observed_task_ok": False,
                              "as_expected": False}
        return out
    d = json.loads(rp.stdout.strip().splitlines()[-1])
    try:
        ee.verify_import_origin(env_dir, {
            "origin": d["worker_origin"], "version": "verified-at-provision",
            "flags_isolated": d["worker_isolated"],
            "flags_no_user_site": d["worker_no_user_site"]})
        out["provenance"] = {"verified": True, "worker_origin": d["worker_origin"]}
    except ee.ProvenanceError as exc:
        out["provenance"] = {"verified": False, "error": str(exc)}
        out["task_completed"] = False
        out["expectation"] = {"expected_task_ok": False, "observed_task_ok": False,
                              "as_expected": False}
        return out

    out["interruption"] = {"killed_signal": "SIGKILL", "process_group": True,
                           "reconcile_outcome": d["outcome"],
                           "safe_to_retry": d["safe_to_retry"],
                           "detail": d["detail"], "run_id": d["run_id"],
                           "auto_replay_prevented": d["blocked"],
                           "next_run_blocked_with": d["blocked_with"]}
    out["task_completed"] = False
    out["expectation"] = {"expected_task_ok": False, "observed_task_ok": False,
                          "as_expected": d["blocked"] and not d["safe_to_retry"]}
    return out


# ------------------------------------------------------------- boundaries

def probe_boundaries(repo_root: Path, res: RunResources) -> list[dict[str, Any]]:
    """Reproduce the recovery/idempotency boundaries, so the findings in
    docs/atlas-3/acceptance/AS-ACCEPT-005.md are re-derivable rather than
    merely asserted. Read-only with respect to the caller: every workspace
    is inside this run's root.
    """
    from project_atlas.orchestration.mission import (
        MISSION_STATE_DIR_NAME,
    )
    from project_atlas.orchestration.mission import (
        execution as ex,
    )
    from project_atlas.orchestration.mission import (
        recovery as rec,
    )
    from project_atlas.orchestration.mission.adapter import ShellCommandAdapter
    from project_atlas.orchestration.mission.context_packet import compile_mission_context

    def ctx(mid: str = "probe"):
        return compile_mission_context(repo_root, mission_id=mid, objective="boundary probe",
                                       keywords=["studio"], trusted_policy=TRUSTED_POLICY)

    out: list[dict[str, Any]] = []

    def record(name: str, expected: str, observed: str, ok: bool, **extra: Any) -> None:
        out.append({"probe": name, "expected": expected, "observed": observed,
                    "as_expected": ok, **extra})

    # 1. corrupt checkpoint
    w = res.plain_workspace("probe-corrupt")
    (w / MISSION_STATE_DIR_NAME).mkdir(parents=True, exist_ok=True)
    (w / MISSION_STATE_DIR_NAME / "mission-run-checkpoint.json").write_text("{not json",
                                                                           encoding="utf-8")
    st = ex.load_checkpoint_detailed(w).status
    r = rec.reconcile_mission_run(w)
    record("corrupt_checkpoint", "MALFORMED + unsafe to retry",
           f"{st} / {r.outcome}",
           st == "MALFORMED" and r.outcome == "UNKNOWN_CHECKPOINT_UNSAFE_TO_RETRY")

    # 2. missing checkpoint
    w = res.plain_workspace("probe-missing")
    st = ex.load_checkpoint_detailed(w).status
    r = rec.reconcile_mission_run(w)
    record("missing_checkpoint", "ABSENT + NO_RUN_FOUND, safe",
           f"{st} / {r.outcome} / safe={r.safe_to_retry}",
           st == "ABSENT" and r.outcome == "NO_RUN_FOUND" and r.safe_to_retry)

    # 3. wrong-workspace attribution
    wa, wb = res.plain_workspace("probe-wsA"), res.plain_workspace("probe-wsB")
    ex.start_mission_run(mission_id="probe", context=ctx(),
                         adapter=ShellCommandAdapter(command=("/bin/true",)),
                         workspace=wa, repo_root=repo_root, adapter_timeout_sec=30.0,
                         idempotency_key="probe:wsA")
    shutil.copytree(wa / MISSION_STATE_DIR_NAME, wb / MISSION_STATE_DIR_NAME,
                    dirs_exist_ok=True)
    try:
        ex.start_mission_run(mission_id="probe", context=ctx(),
                             adapter=ShellCommandAdapter(command=("/bin/true",)),
                             workspace=wb, repo_root=repo_root, adapter_timeout_sec=30.0,
                             idempotency_key="probe:wsA")
        record("wrong_workspace_attribution", "refused", "ACCEPTED a foreign checkpoint", False)
    except ex.UnreconciledPriorRunError as exc:
        record("wrong_workspace_attribution", "refused on identity mismatch",
               "refused", "identity mismatch" in str(exc), detail=str(exc)[:140])

    # 4. repeated resume after a confirmed result
    w = res.plain_workspace("probe-repeat")
    ids, dedups = [], []
    for _ in range(3):
        rr = ex.start_mission_run(mission_id="probe", context=ctx(),
                                  adapter=ShellCommandAdapter(command=("/bin/true",)),
                                  workspace=w, repo_root=repo_root, adapter_timeout_sec=30.0,
                                  idempotency_key="probe:repeat")
        ids.append(rr.run_id)
        dedups.append(rr.deduplicated)
    record("repeated_resume", "stable dedup, one run_id",
           f"dedup={dedups} unique_ids={len(set(ids))}",
           dedups == [False, True, True] and len(set(ids)) == 1)

    # 5. stale knowledge between preparation and execution
    wt = res.worktree("probe-stale", "HEAD")
    c = compile_mission_context(wt, mission_id="stale", objective="stale probe",
                                keywords=["studio", "backlog"], trusted_policy=TRUSTED_POLICY)
    changed = None
    if c.evidence_links:
        src = wt / c.evidence_links[0]
        if src.is_file():
            src.write_text(src.read_text(encoding="utf-8") + "\n<!-- mutated -->\n",
                           encoding="utf-8")
            changed = c.evidence_links[0]
    try:
        ex.start_mission_run(mission_id="stale", context=c,
                             adapter=ShellCommandAdapter(command=("/bin/true",)),
                             workspace=wt, repo_root=wt, adapter_timeout_sec=30.0,
                             idempotency_key="probe:stale")
        record("stale_context", "refused by default", "RAN on stale context", False,
               mutated_source=changed)
    except ex.ContextStaleError:
        record("stale_context", "refused by default", "ContextStaleError", True,
               mutated_source=changed)

    # 6. same key, DIFFERENT execution inputs -- the known #789 defect
    w = res.plain_workspace("probe-samekey")
    marker = w / "which.txt"
    a = _write(w / "a.sh", f"#!/bin/sh\necho A >> {marker}\n", 0o755)
    b = _write(w / "b.sh", f"#!/bin/sh\necho B >> {marker}\n", 0o755)
    c = ctx("samekey")
    ex.start_mission_run(mission_id="samekey", context=c,
                         adapter=ShellCommandAdapter(command=(str(a),)),
                         workspace=w, repo_root=repo_root, adapter_timeout_sec=30.0)
    r2 = ex.start_mission_run(mission_id="samekey", context=c,
                              adapter=ShellCommandAdapter(command=(str(b),)),
                              workspace=w, repo_root=repo_root, adapter_timeout_sec=30.0)
    ran = marker.read_text(encoding="utf-8").split() if marker.exists() else []
    misattributed = bool(r2.adapter_result and r2.adapter_result.command_repr.endswith("a.sh"))
    record("same_key_different_inputs",
           "KNOWN DEFECT (#789): default key omits the adapter",
           f"dedup={r2.deduplicated} ran={ran} misattributed={misattributed}",
           r2.deduplicated and misattributed,
           note="reproduction, not a regression in this runner; the runner passes "
                "explicit keys including an adapter digest",
           owner="PR_789")
    return out


# ------------------------------------------------------------------ report

def human_summary(ev: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append
    add("=" * 72)
    add(f"{PACKAGE} mission acceptance   schema={ev['schema']}")
    add("=" * 72)
    c = ev["candidate"]
    add(f"repo        {c['repo_root']}")
    add(f"head/tree   {c['head'][:12]} / {c['tree'][:12]}")
    add(f"platform    {c['platform']}  python {c['python']}")
    add(f"authority   trusted_policy={ev['authority']['trusted_policy']} "
        f"({ev['authority']['origin']})")
    add(f"execution   {ev['authority']['execution_permission']}")
    add("")
    ep = ev.get("execution_provenance")
    if ep:
        if ep.get("established"):
            add("PROVENANCE  ESTABLISHED -- " + ep["contract"])
            add(f"   commit     {ep['commit'][:12]}   tree {ep['tree'][:12]}")
            add(f"   wheel      {ep['wheel']}  sha {ep['wheel_sha256'][:16]}")
            add(f"   interpreter{ep['interpreter']}")
            add(f"   origin     {ep['worker_import_origin']}")
            add(f"   isolated={ep['worker_isolated']} no_user_site={ep['worker_no_user_site']}")
            ig = ep.get("integrity") or {}
            add(f"   integrity  {ig.get('record_files_verified')} RECORD files hashed, "
                f"{ig.get('dependency_versions_recorded')} dep versions pinned, "
                f"bytecode purged")
            add(f"   covers     {', '.join(ep['covers'])}")
            add(f"   NOT proven {', '.join(ep['does_not_cover'])}; "
                f"dependency file contents not hashed")
        else:
            add(f"PROVENANCE  NOT ESTABLISHED -- {str(ep.get('error'))[:200]}")
        add("")
    pf = ev["preflight"]
    add(f"PREFLIGHT   {'PASS' if pf['ok'] else 'FAIL'}  {pf['detail']}")
    for pr, info in sorted(pf.get("data", {}).get("components", {}).items()):
        add(f"   pin {pr:<6} {info['sha'][:8]}  {'present' if info['present'] else 'ABSENT'}")
    add("")
    if not ev.get("missions"):
        add("MISSIONS    not executed")
    for m in ev.get("missions", []):
        exp = m.get("expectation", {})
        mark = "OK " if exp.get("as_expected") else "!! "
        add(f"{mark}{m['label']:<26} task_completed={m.get('task_completed')} "
            f"expected={exp.get('expected_task_ok')}")
        cr = m.get("command_result")
        if cr:
            add(f"     command rc={cr['returncode']} failure_class={cr['failure_class']}")
        it = m.get("interruption")
        if it:
            add(f"     reconcile={it['reconcile_outcome']} safe_to_retry={it['safe_to_retry']}")
            add(f"     auto_replay_prevented={it['auto_replay_prevented']}")
        pv = m.get("provenance")
        if pv:
            add(f"     provenance verified={pv.get('verified')}"
                + ("" if pv.get("verified") else f" -- {str(pv.get('error'))[:80]}"))
        rs = m.get("resume")
        if rs:
            add(f"     resume={rs.get('state')} deduplicated={rs.get('deduplicated')} "
                f"effect_repeated={rs.get('effect_repeated')}")
        if m.get("outcome", {}).get("error"):
            add(f"     ERROR {m['outcome']['error']}: {m['outcome']['detail'][:90]}")
    if ev.get("boundaries"):
        add("")
        add("BOUNDARIES")
        for b in ev["boundaries"]:
            mark = "OK " if b["as_expected"] else "!! "
            add(f"   {mark}{b['probe']:<28} {b['observed']}")
            if b.get("owner"):
                add(f"        owner={b['owner']}  {b.get('note','')[:70]}")
    add("")
    add(f"CLEANUP     {ev['cleanup']}")
    add("")
    add("SCOPE       Linux-local unless a CI job says otherwise. The resume evidence")
    add("            covers THIS measured action only; it does not generalize to")
    add("            arbitrary external effects the checkpoint cannot observe.")
    add(f"VERDICT     {ev['verdict']}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mission_accept",
                                 description=f"{PACKAGE} reusable mission acceptance")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--packet", default=None, help="optional Studio task-context JSON")
    ap.add_argument("--agent", default="ubuntu-main")
    ap.add_argument("--json-out", default=None, help="write machine-readable evidence here")
    ap.add_argument("--keep", action="store_true", help="retain workspaces for inspection")
    ap.add_argument("--strict-pins", action="store_true",
                    help="fail preflight when a pinned component head is absent")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--isolated-execution", action="store_true",
                    help="run missions from a wheel built from the selected commit, in a "
                         "dedicated venv under -I (AS-PROV-006); proves WHICH code ran")
    ap.add_argument("--env-cache", default=None,
                    help="where provisioned candidate environments live "
                         "(default: ~/.cache/atlas-acceptance/envs, disk-backed and "
                         "reused across runs; never removed by this run)")
    ap.add_argument("--ephemeral-env", action="store_true",
                    help="provision into a run-scoped cache and remove it on cleanup "
                         "(costs a full rebuild every run)")
    ap.add_argument("--prune-envs", type=int, default=2, metavar="N",
                    help="keep at most N cached environments besides this run's "
                         "(default 2); only directories this tool created")
    ap.add_argument("--probe-boundaries", action="store_true",
                    help="also reproduce the recovery/idempotency boundary matrix")
    ap.add_argument("--i-authorize-bounded-execution", action="store_true",
                    help="explicit permission to spawn bounded subprocesses")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    authorized = args.i_authorize_bounded_execution or os.environ.get("ATLAS_ACCEPT_EXECUTE") == "1"

    ev: dict[str, Any] = {
        "schema": SCHEMA, "package": PACKAGE,
        "authority": {
            "trusted_policy": TRUSTED_POLICY,
            "origin": "caller literal; never sourced from a Studio packet",
            "execution_permission": ("GRANTED via --i-authorize-bounded-execution"
                                     if authorized else "NOT GRANTED (planning only)"),
            "studio_can_authorize": False,
        },
    }

    pf = preflight(repo_root, strict_pins=args.strict_pins,
                   isolated_execution=args.isolated_execution)
    ev["preflight"] = {"ok": pf.ok, "detail": pf.detail, "data": pf.data,
                       "diagnostics": pf.diagnostics}
    ev["candidate"] = {
        "repo_root": pf.diagnostics.get("repo_root", str(repo_root)),
        "head": pf.diagnostics.get("head", "?"), "tree": pf.diagnostics.get("tree", "?"),
        "python": pf.diagnostics.get("python"), "platform": pf.diagnostics.get("platform"),
        "project_atlas_from": pf.diagnostics.get("project_atlas_from"),
    }
    ev["studio"] = stage_studio(Path(args.packet) if args.packet else None, args.agent)

    if not pf.ok:
        ev["verdict"] = "PREFLIGHT_FAILED -- diagnostics preserved, nothing executed"
        ev["cleanup"] = {"kept": False, "note": "no resources created"}
        _emit(ev, args)
        return 2
    if args.preflight_only or not authorized:
        ev["verdict"] = ("PREFLIGHT_PASSED -- execution not authorized"
                         if not authorized else "PREFLIGHT_PASSED")
        ev["cleanup"] = {"kept": False, "note": "no resources created"}
        _emit(ev, args)
        return 0

    res = RunResources(repo_root, args.keep)
    ev["run_root"] = str(res.root)

    env_dir = worker_python = None
    if args.isolated_execution:
        import execution_env as ee
        if args.ephemeral_env:
            cache = res.root / "envs"
            res.env_cache = cache          # run-created -> removed on cleanup
        elif args.env_cache:
            cache = Path(args.env_cache).resolve()
            res.env_cache = None           # caller-owned -> never removed
        else:
            cache = ee.DEFAULT_ENV_CACHE
            res.env_cache = None           # persistent by design -> pruned, not deleted
        try:
            env_dir, identity, probe = ee.provision(repo_root, "HEAD", cache)
        except ee.ProvenanceError as exc:
            ev["execution_provenance"] = {"established": False, "error": str(exc)}
            ev["verdict"] = ("EXECUTION_PROVENANCE_NOT_ESTABLISHED -- refusing to run "
                             "in the caller's environment")
            ev["cleanup"] = res.cleanup()
            _emit(ev, args)
            return 3
        worker_python = ee._venv_python(env_dir)
        ev["execution_provenance"] = {
            "established": True, "contract": identity.contract,
            "commit": identity.commit, "tree": identity.tree,
            "wheel": identity.wheel_name, "wheel_sha256": identity.wheel_sha256,
            "install_method": identity.install_method,
            "env_dir": str(env_dir), "interpreter": str(worker_python),
            "worker_import_origin": probe["origin"],
            "worker_isolated": probe["flags_isolated"],
            "worker_no_user_site": probe["flags_no_user_site"],
            "distribution_version": probe["version"],
            "covers": ["project_atlas", "atlas_contracts"],
            "does_not_cover": ["atlas_studio (lives in scripts/, not in the wheel)"],
            "integrity": {
                "record_files_verified": (probe.get("manifest") or {}).get("checked"),
                "record_mismatched": (probe.get("manifest") or {}).get("n_mismatched"),
                "record_missing": (probe.get("manifest") or {}).get("n_missing"),
                "dependency_versions_recorded": len(
                    (probe.get("manifest") or {}).get("dependencies") or {}),
                "bytecode": "purged at verification; .pyc carries no digest in RECORD",
                "dependency_file_contents_hashed": False,
            },
        }
        ev["execution_provenance"]["env_cache"] = str(cache)
        ev["execution_provenance"]["env_cache_owned_by_run"] = res.env_cache is not None
        # Pruning happens later, after the lease is held, so this run's own
        # environment cannot be a candidate for removal.
        _prune_after_lease = (None if args.ephemeral_env
                              else (cache, {identity.tree}, args.prune_envs))

    missions_out: list[dict[str, Any]] = []
    # Hold the environment for as long as workers use it. `provision` releases
    # its build lock on return, so without a lease a concurrent prune can (and
    # did, when tested) delete the environment out from under a running worker.
    lease = contextlib.ExitStack()
    if worker_python is not None:
        import execution_env as ee
        lease.enter_context(ee.env_lease(cache, env_dir.name[len("env-"):]))
        ev["execution_provenance"]["leased_during_use"] = True
        if _prune_after_lease is not None:
            c, keep_trees, n = _prune_after_lease
            ev["execution_provenance"]["env_prune"] = ee.prune_envs(c, keep_trees, keep=n)
    try:
        for m in MISSIONS:
            if worker_python is not None:
                r = run_mission_isolated(repo_root, res, m, env_dir, worker_python)
            else:
                r = run_mission(repo_root, res, m)
            if (r.get("task_completed") and r.get("execution_identity")
                    and worker_python is None):
                r["resume"] = stage_resume(
                    repo_root, m, Path(r["workspace"]),
                    r["execution_identity"]["idempotency_key"],
                    tuple(r["execution_identity"]["command"]),
                )
            missions_out.append(r)
        interrupted = Mission("accept-interrupted", "Long task killed mid-flight",
                              ["studio"], mission_interrupted, False, "interrupted_task")
        if worker_python is not None:
            missions_out.append(
                run_interrupted_isolated(repo_root, res, interrupted, env_dir, worker_python))
        else:
            missions_out.append(run_mission(repo_root, res, interrupted, interrupt=True))
        if args.probe_boundaries:
            ev["boundaries"] = probe_boundaries(repo_root, res)
    finally:
        ev["missions"] = missions_out
        lease.close()
        ev["cleanup"] = res.cleanup()

    bad = [m for m in missions_out if not m.get("expectation", {}).get("as_expected")]
    bad_probes = [b for b in ev.get("boundaries", []) if not b["as_expected"]]
    if bad_probes:
        ev["boundary_failures"] = [b["probe"] for b in bad_probes]
    problems = [m["label"] for m in bad] + [b["probe"] for b in bad_probes]
    ev["verdict"] = ("ALL_MISSIONS_AS_EXPECTED" + (" + BOUNDARIES_REPRODUCED"
                                                   if ev.get("boundaries") else "")
                     if not problems else f"UNEXPECTED: {problems}")
    _emit(ev, args)
    return 0 if not problems else 1


def _emit(ev: dict[str, Any], args) -> None:
    print(human_summary(ev))
    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\n[machine-readable evidence] {p}")


if __name__ == "__main__":
    raise SystemExit(main())
