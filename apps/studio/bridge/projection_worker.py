"""Request-scoped acceleration of the existing A1 read path, never a truth cache."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from atlas_dag.gh import GhClient, GhError  # noqa: E402
from atlas_studio.mission_control import (  # noqa: E402
    build_mission_control,
    validate_mission_control,
)


class RequestClient(GhClient):
    """Same GhClient parsers, request-local exact-command reuse, bounded reads."""

    def __init__(self, repo, timeout=18, runner=subprocess.run):
        super().__init__(repo=repo, runner=runner)
        self.deadline = time.monotonic() + timeout
        self.cache = {}
        self.lock = threading.Lock()
        self.failed = False
        self.timings = []

    def _read_command(self, args):
        if args == ["auth", "status"]:
            return True
        pr_fields = (
            "number,title,author,isDraft,headRefName,headRefOid,baseRefName,mergeable,url,updatedAt"
        )
        if args == [
            "pr",
            "list",
            "--repo",
            self.repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            pr_fields,
        ]:
            return True
        if args == [
            "issue",
            "list",
            "--repo",
            self.repo,
            "--state",
            "all",
            "--search",
            '"Atlas Autonomous DAG Control" in:title',
            "--limit",
            "10",
            "--json",
            "number,title,state",
        ]:
            return True
        if not args or args[0] != "api":
            return False
        rest = list(args[1:])
        if rest[:1] == ["--paginate"]:
            rest.pop(0)
        if len(rest) not in (1, 3):
            return False
        endpoint = rest[0]
        prefix = f"repos/{self.repo}"
        if endpoint != prefix and not endpoint.startswith(prefix + "/"):
            return False
        if ".." in endpoint.split("/") or any(part in endpoint for part in ("\\", "\n", "\r")):
            return False
        return len(rest) == 1 or rest[1:] in (["--jq", ".default_branch"], ["--jq", ".body"])

    def run_gh(self, args):
        if not self._read_command(args):
            self.failed = True
            raise GhError("READ_ONLY_BOUNDARY")
        key = tuple(args)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.failed = True
            raise GhError("UPSTREAM_DEADLINE")
        started = time.monotonic()
        try:
            result = self._runner(
                ["gh", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=min(6, remaining),
            )
            if result.returncode:
                raise GhError("UPSTREAM_READ_FAILED")
        except (subprocess.TimeoutExpired, OSError):
            self.failed = True
            raise GhError("UPSTREAM_READ_TIMEOUT") from None
        except GhError:
            self.failed = True
            raise
        finally:
            with self.lock:
                self.timings.append(
                    {"family": args[0], "seconds": round(time.monotonic() - started, 3)}
                )
        with self.lock:
            self.cache[key] = result.stdout
        return result.stdout

    def _prefetch_repository(self):
        branch = self.default_branch() or "main"
        self.branch_head(branch)

    def _prefetch_events(self):
        issue = self.dag_issue()
        if issue:
            self.issue_comments(issue["number"])
            self.issue_body(issue["number"])

    def prefetch(self):
        """Warm exactly the reads used by A1; no durable cross-request reuse."""
        prs = self.open_prs()
        jobs = [(self._prefetch_repository, ()), (self._prefetch_events, ())]
        by_branch = {p["headRefName"]: p for p in prs}
        for pr in prs:
            head = pr.get("headRefOid")
            if head:
                jobs.extend([(self.commit, (head,)), (self.runs_for_head, (head,))])
            jobs.append((self.review_comments, (pr["number"],)))
            parent = by_branch.get(pr.get("baseRefName"))
            if parent and parent.get("headRefOid") and head:
                jobs.append((self.is_ancestor, (parent["headRefOid"], head)))
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(fn, *args) for fn, args in jobs]
            for future in futures:
                future.result()


def main():
    started = time.monotonic()
    client = RequestClient(sys.argv[1])
    stage = "authentication"
    stages = {}
    try:
        t = time.monotonic()
        client.run_gh(["auth", "status"])
        stages[stage] = round(time.monotonic() - t, 3)
        stage = "upstream_reads"
        t = time.monotonic()
        client.prefetch()
        if client.failed:
            raise RuntimeError("UPSTREAM_READ_FAILED")
        stages[stage] = round(time.monotonic() - t, 3)
        stage = "projection_construction"
        t = time.monotonic()
        packet = build_mission_control(
            live=True, repo=sys.argv[1], agent_id=sys.argv[2] or None, live_client=client
        )
        stages[stage] = round(time.monotonic() - t, 3)
        if client.failed:
            raise RuntimeError("UPSTREAM_READ_FAILED")
        if validate_mission_control(packet):
            raise RuntimeError("A1_SCHEMA_VALIDATION_FAILED")
        print(json.dumps(packet, separators=(",", ":")))
    except Exception:
        # Exception text can include gh stderr; only stage-coded diagnostics leave worker.
        print(json.dumps({"error": f"PROJECTION_FAILED_{stage.upper()}"}))
        return 1
    finally:
        print(
            json.dumps(
                {
                    "stages_seconds": stages,
                    "total_seconds": round(time.monotonic() - started, 3),
                    "upstream_reads": len(client.timings),
                    "read_seconds": client.timings,
                }
            ),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
