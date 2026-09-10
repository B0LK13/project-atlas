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

def preflight(repo_root: Path, *, strict_pins: bool) -> StageResult:
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
            problems.append(
                f"project_atlas resolves to {pkg}, which is OUTSIDE {top}. "
                f"Run `pip install -e .[dev]` inside this checkout; subprocess "
                f"tests resolve through the install, not PYTHONPATH."
            )
    except ImportError as exc:
        problems.append(f"project_atlas not importable: {exc} -- run `pip install -e .[dev]`")

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
                                  "worktrees_removed": [], "errors": []}
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
    import signal

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

    p = subprocess.Popen([sys.executable, "-c", worker], start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    p.wait()
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
        rs = m.get("resume")
        if rs:
            add(f"     resume={rs.get('state')} deduplicated={rs.get('deduplicated')} "
                f"effect_repeated={rs.get('effect_repeated')}")
        if m.get("outcome", {}).get("error"):
            add(f"     ERROR {m['outcome']['error']}: {m['outcome']['detail'][:90]}")
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

    pf = preflight(repo_root, strict_pins=args.strict_pins)
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
    missions_out: list[dict[str, Any]] = []
    try:
        for m in MISSIONS:
            r = run_mission(repo_root, res, m)
            if r.get("task_completed") and r.get("execution_identity"):
                r["resume"] = stage_resume(
                    repo_root, m, Path(r["workspace"]),
                    r["execution_identity"]["idempotency_key"],
                    tuple(r["execution_identity"]["command"]),
                )
            missions_out.append(r)
        interrupted = Mission("accept-interrupted", "Long task killed mid-flight",
                              ["studio"], mission_interrupted, False, "interrupted_task")
        missions_out.append(run_mission(repo_root, res, interrupted, interrupt=True))
    finally:
        ev["missions"] = missions_out
        ev["cleanup"] = res.cleanup()

    bad = [m for m in missions_out if not m.get("expectation", {}).get("as_expected")]
    ev["verdict"] = ("ALL_MISSIONS_AS_EXPECTED" if not bad
                     else f"UNEXPECTED: {[m['label'] for m in bad]}")
    _emit(ev, args)
    return 0 if not bad else 1


def _emit(ev: dict[str, Any], args) -> None:
    print(human_summary(ev))
    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\n[machine-readable evidence] {p}")


if __name__ == "__main__":
    raise SystemExit(main())
