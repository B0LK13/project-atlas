"""Request-scoped acceleration of the existing A1 read path, never a truth cache."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from atlas_dag.gh import GhClient, GhError  # noqa: E402
from atlas_studio.mission_control import build_mission_control, validate_mission_control  # noqa: E402


class RequestClient(GhClient):
    """Same GhClient parsers, request-local exact-command reuse, bounded reads."""

    def __init__(self, repo, timeout=18, runner=subprocess.run):
        super().__init__(repo=repo, runner=runner)
        self.deadline = time.monotonic() + timeout
        self.cache = {}
        self.lock = threading.Lock()
        self.failed = False
        self.timings = []

    def run_gh(self, args):
        allowed = (args[:2] in (["auth", "status"], ["pr", "list"], ["issue", "list"])
                   or (args[:1] == ["api"] and any(
                       arg.startswith(f"repos/{self.repo}") for arg in args[1:])))
        if not allowed or any(arg in {"-X", "--method", "-f", "-F", "--field", "--raw-field",
                                      "--input"} or arg.startswith(("--method=", "--field=", "--raw-field="))
                              for arg in args):
            self.failed = True
            raise GhError("READ_ONLY_BOUNDARY")
        key = tuple(args)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.failed = True
            raise GhError('UPSTREAM_DEADLINE')
        started = time.monotonic()
        try:
            result = self._runner(['gh', *args], capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=min(6, remaining))
            if result.returncode:
                raise GhError('UPSTREAM_READ_FAILED')
        except (subprocess.TimeoutExpired, OSError):
            self.failed = True
            raise GhError('UPSTREAM_READ_TIMEOUT') from None
        except GhError:
            self.failed = True
            raise
        finally:
            with self.lock:
                self.timings.append({'family': args[0], 'seconds': round(time.monotonic()-started, 3)})
        with self.lock:
            self.cache[key] = result.stdout
        return result.stdout

    def prefetch(self):
        """Warm exactly the reads used by A1; no durable cross-request reuse."""
        prs = self.open_prs()
        jobs = []
        by_branch = {p['headRefName']: p for p in prs}
        for pr in prs:
            head = pr.get('headRefOid')
            if head:
                jobs.extend([(self.commit, (head,)), (self.runs_for_head, (head,))])
            jobs.append((self.review_comments, (pr['number'],)))
            parent = by_branch.get(pr.get('baseRefName'))
            if parent and parent.get('headRefOid') and head:
                jobs.append((self.is_ancestor, (parent['headRefOid'], head)))
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fn, *args) for fn, args in jobs]
            for future in futures:
                future.result()


def main():
    started = time.monotonic()
    client = RequestClient(sys.argv[1])
    stage = 'authentication'
    stages = {}
    try:
        t = time.monotonic()
        client.run_gh(['auth', 'status'])
        stages[stage] = round(time.monotonic()-t, 3)
        stage = 'upstream_reads'
        t = time.monotonic()
        client.prefetch()
        stages[stage] = round(time.monotonic()-t, 3)
        stage = 'projection_construction'
        t = time.monotonic()
        packet = build_mission_control(live=True, repo=sys.argv[1],
                                      agent_id=sys.argv[2] or None, live_client=client)
        stages[stage] = round(time.monotonic()-t, 3)
        if client.failed:
            raise RuntimeError('UPSTREAM_READ_FAILED')
        if validate_mission_control(packet):
            raise RuntimeError('A1_SCHEMA_VALIDATION_FAILED')
        print(json.dumps(packet, separators=(',', ':')))
    except Exception:
        # Exception text can include gh stderr; only stage-coded diagnostics leave worker.
        print(json.dumps({'error': f'PROJECTION_FAILED_{stage.upper()}'}))
        return 1
    finally:
        print(json.dumps({'stages_seconds': stages, 'total_seconds': round(time.monotonic()-started, 3),
                          'upstream_reads': len(client.timings), 'read_seconds': client.timings}), file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
