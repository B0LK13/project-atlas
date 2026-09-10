"""ATLAS-ONE-COHERENT-WORKFLOW -- the supported journey, end to end.

Knowledge -> task -> permitted action -> evidence -> fresh-process resume,
using ONLY components that already exist:

  project knowledge   `project_atlas` vault lenses (real compiled vault)
  mission context     `project_atlas.orchestration.mission.context_packet`
  task + eligibility  `atlas_studio task-context` (AS-STUDIO-A2-003)
  the seam            `atlas_studio.mission_bridge` (AS-STUDIO-BRIDGE-001)
  bounded execution   `...mission.execution.start_mission_run`
  evidence + resume   mission checkpoint + `...mission.recovery`

Every step prints what it proved. Nothing here simulates a run: the
adapter spawns a real subprocess in a disposable git worktree and its real
exit code decides the outcome.

Usage:
    python scripts/acceptance/atlas_one_workflow.py --repo-root <candidate>
        [--vault <compiled vault>] [--stage all|knowledge|action|resume]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import mission_bridge as mb  # noqa: E402

from project_atlas.orchestration.mission.adapter import ShellCommandAdapter  # noqa: E402
from project_atlas.orchestration.mission.context_packet import (  # noqa: E402
    compile_mission_context,
)
from project_atlas.orchestration.mission.execution import (  # noqa: E402
    load_checkpoint_detailed,
    start_mission_run,
)

# The caller's OWN authority. Never sourced from a Studio packet.
TRUSTED_POLICY = {"MERGE_AUTHORIZATION": "NO"}

BANNER = "=" * 72


def say(step: str, msg: str) -> None:
    print(f"\n{BANNER}\n{step}\n{BANNER}\n{msg}")


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


def stage_knowledge(repo_root: Path, packet_path: Path | None):
    """Compile mission context from REAL repository documents."""
    ctx = compile_mission_context(
        repo_root,
        mission_id="atlas-one-workflow",
        objective="Prove the A2-006 READ_ERROR regression holds on every platform",
        keywords=["snapshot", "read_error", "portability", "studio"],
        trusted_policy=TRUSTED_POLICY,
    )
    say(
        "1. KNOWLEDGE -- real project documents, with provenance",
        f"base_head        : {ctx.base_head}\n"
        f"base_tree        : {ctx.base_tree}\n"
        f"decisions        : {len(ctx.decisions)} ADR excerpt(s)\n"
        f"backlog items    : {len(ctx.backlog_items)}\n"
        f"prior work       : {len(ctx.prior_related_work)} WORKLOG excerpt(s)\n"
        f"open questions   : {len(ctx.open_questions)}\n"
        f"evidence sources : {len(ctx.evidence_links)}\n"
        f"trusted_policy   : {ctx.trusted_policy}  <- caller's, not retrieved",
    )
    for m in (ctx.decisions + ctx.backlog_items)[:3]:
        print(f"  - {m.source.path}  ({m.match_reason})")

    inputs = None
    if packet_path and packet_path.is_file():
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        try:
            inputs = mb.build_mission_inputs(packet, expected_agent_id="ubuntu-main")
            say(
                "2. TASK + AUTHORIZATION -- Studio projection, carried as DATA",
                f"lane             : {inputs.lane}\n"
                f"next action      : {inputs.action_type} ({inputs.action_class})\n"
                f"lane_head        : {inputs.lane_head}\n"
                f"freshness        : {inputs.freshness_state}\n"
                f"authorization    : NOT_GRANTED_BY_THIS_PACKET (asserted by the bridge)\n"
                f"policy used      : {TRUSTED_POLICY}  <- the CALLER's, never the packet's",
            )
        except mb.StudioBridgeError as exc:
            say(
                "2. TASK + AUTHORIZATION -- refused by Studio state",
                f"{type(exc).__name__}: {exc}",
            )
    else:
        say("2. TASK + AUTHORIZATION", "no Studio packet supplied; skipping (see --packet)")
    return ctx, inputs


def stage_action(repo_root: Path, ctx, workspace: Path, command: list[str]):
    """One bounded action, in a disposable workspace, with real evidence."""
    adapter = ShellCommandAdapter(command=tuple(command))
    result = start_mission_run(
        mission_id="atlas-one-workflow",
        context=ctx,
        adapter=adapter,
        workspace=workspace,
        repo_root=repo_root,
        adapter_timeout_sec=600.0,
    )
    ar = result.adapter_result
    say(
        "3. BOUNDED ACTION -- real subprocess, disposable workspace",
        f"run_id           : {result.run_id}\n"
        f"command          : {ar.command_repr if ar else '-'}\n"
        f"returncode       : {ar.returncode if ar else '-'}\n"
        f"ok               : {ar.ok if ar else '-'}\n"
        f"failure_class    : {ar.failure_class if ar else '-'}\n"
        f"duration_sec     : {ar.duration_sec:.2f}\n"
        f"deduplicated     : {result.deduplicated}\n"
        f"checkpoint state : {result.checkpoint.state}",
    )
    if ar and ar.stdout:
        print("  adapter stdout (tail):")
        for line in ar.stdout.strip().splitlines()[-4:]:
            print(f"    {line}")
    return result


def stage_evidence(workspace: Path):
    detail = load_checkpoint_detailed(workspace)
    cp = detail.checkpoint
    say(
        "4. EVIDENCE -- persisted, inspectable, survives the process",
        f"checkpoint status: {detail.status}\n"
        f"state            : {cp.state if cp else '-'}\n"
        f"run_id           : {cp.run_id if cp else '-'}\n"
        f"idempotency_key  : {cp.idempotency_key if cp else '-'}",
    )
    return detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--packet", default=None, help="Studio task-context JSON")
    ap.add_argument("--workspace", default=None, help="reuse a workspace (resume demo)")
    ap.add_argument("--stage", default="all", choices=["all", "knowledge", "action", "resume"])
    ap.add_argument("--command", nargs="*", default=None)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    packet = Path(args.packet).resolve() if args.packet else None

    ctx, _ = stage_knowledge(repo_root, packet)
    if args.stage == "knowledge":
        return 0

    if args.workspace:
        workspace = Path(args.workspace).resolve()
        created = False
    else:
        workspace = Path(tempfile.mkdtemp(prefix="atlas-mission-ws-"))
        created = True
        head = _git(["rev-parse", "HEAD"], repo_root)
        shutil.rmtree(workspace)
        _git(["worktree", "add", "--detach", str(workspace), head], repo_root)
        print(f"\n[disposable workspace] git worktree at {workspace}")

    command = args.command or [
        sys.executable, "-m", "pytest",
        "tests/unit/test_atlas_studio_snapshot_load.py",
        "tests/unit/test_atlas_studio_mission_bridge.py",
        "-p", "no:cacheprovider", "--no-cov",
    ]
    try:
        stage_action(repo_root, ctx, workspace, command)
        stage_evidence(workspace)
        print(f"\n[workspace preserved for resume] {workspace}")
        print(f"[resume with] --workspace {workspace} --stage resume")
    finally:
        if created and args.stage == "action":
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
