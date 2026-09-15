"""Hardened semantic acceptance beyond weak porcelain signals.

WORKER_REPORTED_COMPLETION != ACCEPTANCE
PRE_EXISTING_DIRT != SUCCESS
EMPTY_OUTPUT != SCOPED_DIFF
ACCEPTANCE != INDEPENDENT_VERIFICATION

Baseline manifests are captured by the supervisor before a coding launch.
After the worker finishes, semantic gates require a demonstrable new scoped
diff versus that baseline inside the task allowlist — never pre-existing dirt.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.orchestration.program.acceptance import (
    AcceptanceResult,
    CheckResult,
)
from project_atlas.orchestration.program.adapters.base import build_child_env
from project_atlas.orchestration.program.models import AcceptanceKind, ProgramTask
from project_atlas.orchestration.program.profiles import AgentProfile

_MAX_CAPTURE = 8192
_KERNEL_HELPER_RE = re.compile(
    r"def\s+_kernel_readiness_status\s*\(",
)
_KERNEL_READY_MAP = (
    ("kernel_start_failure", "BLOCKED"),
    ("tool_result_received", "READY"),
    ("UNKNOWN", "UNKNOWN"),
)


@dataclass(frozen=True)
class BaselineManifest:
    """Content hashes of allowlisted paths plus porcelain recorded before launch."""

    attempt_id: str
    workspace: str
    allowlist: tuple[str, ...]
    path_sha256: dict[str, str | None]
    pre_existing_porcelain: tuple[str, ...]
    head_sha: str | None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "workspace": self.workspace,
            "allowlist": list(self.allowlist),
            "path_sha256": dict(self.path_sha256),
            "pre_existing_porcelain": list(self.pre_existing_porcelain),
            "head_sha": self.head_sha,
        }

    @classmethod
    def from_public_dict(cls, document: dict[str, Any]) -> BaselineManifest:
        paths = document.get("path_sha256") or {}
        if not isinstance(paths, dict):
            paths = {}
        return cls(
            attempt_id=str(document.get("attempt_id") or ""),
            workspace=str(document.get("workspace") or ""),
            allowlist=tuple(str(p) for p in (document.get("allowlist") or ())),
            path_sha256={str(k): (None if v is None else str(v)) for k, v in paths.items()},
            pre_existing_porcelain=tuple(
                str(line) for line in (document.get("pre_existing_porcelain") or ())
            ),
            head_sha=(
                None
                if document.get("head_sha") is None
                else str(document.get("head_sha"))
            ),
        )


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _porcelain(workspace: Path, profile: AgentProfile) -> tuple[str, ...]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            env=build_child_env(profile),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(line for line in (completed.stdout or "").splitlines() if line.strip())


def _head_sha(workspace: Path, profile: AgentProfile) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            env=build_child_env(profile),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    value = (completed.stdout or "").strip()
    return value or None


def _porcelain_path(line: str) -> str:
    body = line[3:] if len(line) >= 3 else line
    if " -> " in body:
        body = body.split(" -> ", 1)[1]
    return body.strip()


def capture_baseline_manifest(
    *,
    workspace: Path,
    profile: AgentProfile,
    attempt_id: str,
    allowlist: tuple[str, ...] | list[str],
) -> BaselineManifest:
    """Snapshot allowlisted path hashes and all porcelain before coding starts."""
    paths = tuple(allowlist)
    hashes: dict[str, str | None] = {}
    for relative in paths:
        hashes[relative] = _sha256_file(workspace / relative)
    return BaselineManifest(
        attempt_id=attempt_id,
        workspace=str(workspace),
        allowlist=paths,
        path_sha256=hashes,
        pre_existing_porcelain=_porcelain(workspace, profile),
        head_sha=_head_sha(workspace, profile),
    )


def _scoped_new_diff(
    *,
    workspace: Path,
    baseline: BaselineManifest,
    allowlist: tuple[str, ...],
) -> tuple[bool, str, dict[str, str | None]]:
    """Return whether any allowlisted path content changed versus baseline."""
    after: dict[str, str | None] = {}
    changed: list[str] = []
    for relative in allowlist:
        current = _sha256_file(workspace / relative)
        after[relative] = current
        prior = baseline.path_sha256.get(relative)
        if current != prior:
            changed.append(relative)
    if not allowlist:
        return False, "empty allowlist — fail-closed", after
    if not changed:
        return (
            False,
            "no allowlisted path content changed versus baseline "
            f"(pre_existing_porcelain={len(baseline.pre_existing_porcelain)})",
            after,
        )
    # Fail-closed when porcelain names paths outside allowlist AND no scoped
    # ownership is unambiguous? Pre-existing dirt is recorded separately and
    # must never be the sole success signal — already handled by requiring
    # allowlist hash change. Ambiguous ownership: allowlist path changed but
    # also identical to a path that was already dirty before launch with the
    # same hash? That cannot happen if hash changed.
    return True, f"scoped content change in: {', '.join(changed)}", after


def _production_helper_ok(workspace: Path, production_path: str) -> tuple[bool, str]:
    path = workspace / production_path
    if not path.is_file():
        return False, f"{production_path} missing"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"could not read {production_path}: {exc}"
    if _KERNEL_HELPER_RE.search(text) is None:
        return False, f"{production_path} lacks def _kernel_readiness_status("
    missing = [name for needle, name in _KERNEL_READY_MAP if needle not in text]
    # READY mapping is via tool_result_received + isError; require those tokens.
    if "isError" not in text and "is_error" not in text:
        missing.append("isError-guard")
    if "kernel_readiness" not in text:
        missing.append("kernel_readiness-exposure")
    if missing:
        return False, f"helper contract incomplete; missing markers: {', '.join(missing)}"
    return True, "helper contract markers present"


def _tests_updated(
    *,
    workspace: Path,
    baseline: BaselineManifest,
    test_path: str,
) -> tuple[bool, str]:
    prior = baseline.path_sha256.get(test_path)
    current = _sha256_file(workspace / test_path)
    if current is None:
        return False, f"{test_path} missing"
    if current == prior:
        return False, f"{test_path} unchanged versus baseline"
    try:
        text = (workspace / test_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"could not read {test_path}: {exc}"
    needed = ("_kernel_readiness_status", "BLOCKED", "READY", "UNKNOWN")
    missing = [token for token in needed if token not in text]
    if missing:
        return False, f"{test_path} changed but missing test markers: {', '.join(missing)}"
    return True, f"{test_path} updated with readiness cases"


def _tests_without_production_change(
    *,
    workspace: Path,
    baseline: BaselineManifest,
    production_path: str,
    test_path: str,
) -> bool:
    """True when tests changed but production did not — must FAIL."""
    prod_changed = _sha256_file(workspace / production_path) != baseline.path_sha256.get(
        production_path
    )
    tests_changed = _sha256_file(workspace / test_path) != baseline.path_sha256.get(test_path)
    return tests_changed and not prod_changed


def _out_of_allowlist_mutations(
    *,
    workspace: Path,
    profile: AgentProfile,
    baseline: BaselineManifest,
    allowlist: tuple[str, ...],
) -> tuple[str, ...]:
    """Porcelain paths that appeared after baseline and are outside allowlist."""
    allowed = set(allowlist)
    before = {_porcelain_path(line) for line in baseline.pre_existing_porcelain}
    after = {_porcelain_path(line) for line in _porcelain(workspace, profile)}
    novel = after - before
    offenders: list[str] = []
    for path in sorted(novel):
        if not path:
            continue
        if path in allowed:
            continue
        if any(path == a or path.startswith(a.rstrip("/") + "/") for a in allowed):
            continue
        offenders.append(path)
    return tuple(offenders)


def _native_child_bound(
    *,
    evidence_root: Path | None,
    attempt_id: str | None,
) -> tuple[bool, str]:
    if evidence_root is None or not attempt_id:
        return False, "native-child evidence context missing"
    journal = evidence_root / f"{attempt_id}.child-admission.jsonl"
    meta = evidence_root / f"{attempt_id}.prime-daemon.json"
    if meta.is_file():
        try:
            document = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = {}
        registry = document.get("child_registry") if isinstance(document, dict) else None
        if isinstance(registry, list) and registry:
            # Require attributable payload beyond a bare handle.
            for entry in registry:
                if not isinstance(entry, dict):
                    continue
                if entry.get("message") or entry.get("artifact") or entry.get("result"):
                    return True, f"child_registry attributable entries={len(registry)}"
            return False, "child_registry present but no attributable message/artifact/result"
    if journal.is_file() and journal.stat().st_size > 0:
        try:
            lines = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            return False, "child-admission journal unreadable"
        for row in lines:
            if not isinstance(row, dict):
                continue
            if row.get("message") or row.get("artifact") or row.get("result"):
                return True, "child-admission journal has attributable result"
        return False, "child-admission journal non-empty but not attributable"
    return False, "native child artifact absent for this attempt"


def _worker_output_nonempty(
    *,
    evidence_root: Path | None,
    attempt_id: str | None,
    workspace: Path | None,
) -> tuple[bool, str]:
    if evidence_root is None or not attempt_id:
        return False, "worker-output evidence context missing"
    # Session stats from daemon jsonl
    daemon_jsonl = evidence_root / f"{attempt_id}.prime-daemon.jsonl"
    if daemon_jsonl.is_file():
        try:
            for line in daemon_jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("command") != "get_session_stats":
                    continue
                data = row.get("data") or {}
                tool_calls = int(data.get("toolCalls") or 0)
                assistant = int(data.get("assistantMessages") or 0)
                if tool_calls > 0:
                    return True, f"session toolCalls={tool_calls}"
                # Empty assistant text with zero tools is not substantive output.
                if assistant > 0 and tool_calls == 0:
                    # Fall through to session file text check.
                    break
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if workspace is not None:
        session = workspace / ".prime-sessions" / f"{attempt_id}.jsonl"
        if session.is_file():
            try:
                for line in session.read_text(encoding="utf-8").splitlines():
                    row = json.loads(line)
                    msg = row.get("message") or {}
                    if msg.get("role") != "assistant":
                        continue
                    content = msg.get("content")
                    text = ""
                    toolish = False
                    if isinstance(content, list):
                        for part in content:
                            if not isinstance(part, dict):
                                continue
                            if part.get("type") == "text":
                                text += part.get("text") or ""
                            if part.get("type") in {"toolCall", "tool_use", "functionCall"}:
                                toolish = True
                    elif isinstance(content, str):
                        text = content
                    if toolish or text.strip():
                        return True, "assistant produced non-empty output or tool call"
                return False, "assistant output empty and no tool calls"
            except (OSError, json.JSONDecodeError):
                return False, "session transcript unreadable"
    return False, "no worker output evidence"


def evaluate_semantic_acceptance(
    task: ProgramTask,
    *,
    workspace: Path,
    profile: AgentProfile,
    baseline: BaselineManifest | None,
    evidence_root: Path | None = None,
    attempt_id: str | None = None,
    reviewer_verdict: str | None = None,
    require_reviewer: bool | None = None,
) -> AcceptanceResult:
    """Evaluate hardened A1-style semantic gates.

    Pre-existing dirt is recorded on the baseline and never counts as success.
    Missing reviewer when required yields a non-passing check with detail
    VERIFYING/BLOCKED — never PASS.
    """
    allowlist = tuple(task.mutation_paths)
    checks: list[CheckResult] = []

    if baseline is None:
        checks.append(
            CheckResult(
                check_id="baseline-manifest",
                kind=AcceptanceKind.FILE_EXISTS,
                passed=False,
                detail="baseline manifest missing — fail-closed",
            )
        )
        return AcceptanceResult(passed=False, checks=tuple(checks))

    # Record pre-existing dirt explicitly (informational check always "passed"
    # as a recording channel, but success does not depend on it).
    checks.append(
        CheckResult(
            check_id="pre-existing-dirt-recorded",
            kind=AcceptanceKind.GIT_TREE_CHANGED,
            passed=True,
            detail=(
                f"recorded {len(baseline.pre_existing_porcelain)} pre-existing "
                "porcelain path(s); they are not success signals"
            ),
        )
    )

    scoped_ok, scoped_detail, _after = _scoped_new_diff(
        workspace=workspace, baseline=baseline, allowlist=allowlist
    )
    checks.append(
        CheckResult(
            check_id="scoped-diff-vs-baseline",
            kind=AcceptanceKind.GIT_TREE_CHANGED,
            passed=scoped_ok,
            detail=scoped_detail[:_MAX_CAPTURE],
        )
    )

    offenders = _out_of_allowlist_mutations(
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        allowlist=allowlist,
    )
    if task.surface_semantic == "CAPABILITY_CANARY":
        _infra_prefixes = (
            ".prime-config",
            ".prime-sessions",
            "session-artifacts/",
            "artifacts/",
            "__pycache__/",
        )
        offenders = [
            path
            for path in offenders
            if not any(
                path == prefix.rstrip("/")
                or path.startswith(prefix)
                for prefix in _infra_prefixes
            )
        ]
    checks.append(
        CheckResult(
            check_id="allowlist-only-mutations",
            kind=AcceptanceKind.GIT_TREE_CHANGED,
            passed=not offenders,
            detail=(
                "no novel out-of-allowlist mutations"
                if not offenders
                else f"out-of-allowlist novel paths: {', '.join(offenders)}"
            )[:_MAX_CAPTURE],
        )
    )

    # Disposable capability canaries are not the A1 oracle: skip kernel-helper /
    # native-child / worker-output gates that only apply to PRIME_A1 surfaces.
    if task.surface_semantic == "CAPABILITY_CANARY":
        return AcceptanceResult(
            passed=all(check.passed for check in checks),
            checks=tuple(checks),
        )

    production = next(
        (p for p in allowlist if p.endswith("control.py")),
        allowlist[0] if allowlist else "",
    )
    tests = next(
        (p for p in allowlist if "test_" in Path(p).name),
        allowlist[1] if len(allowlist) > 1 else "",
    )

    if production:
        helper_ok, helper_detail = _production_helper_ok(workspace, production)
        checks.append(
            CheckResult(
                check_id="kernel-readiness-helper",
                kind=AcceptanceKind.FILE_MATCHES,
                passed=helper_ok,
                detail=helper_detail[:_MAX_CAPTURE],
            )
        )

    if production and tests:
        if _tests_without_production_change(
            workspace=workspace,
            baseline=baseline,
            production_path=production,
            test_path=tests,
        ):
            checks.append(
                CheckResult(
                    check_id="tests-without-production-change",
                    kind=AcceptanceKind.GIT_TREE_CHANGED,
                    passed=False,
                    detail="tests changed without production allowlist change",
                )
            )
        else:
            tests_ok, tests_detail = _tests_updated(
                workspace=workspace, baseline=baseline, test_path=tests
            )
            checks.append(
                CheckResult(
                    check_id="tests-updated",
                    kind=AcceptanceKind.FILE_MATCHES,
                    passed=tests_ok,
                    detail=tests_detail[:_MAX_CAPTURE],
                )
            )

    child_ok, child_detail = _native_child_bound(
        evidence_root=evidence_root, attempt_id=attempt_id or baseline.attempt_id
    )
    checks.append(
        CheckResult(
            check_id="native-child-bound",
            kind=AcceptanceKind.FILE_EXISTS,
            passed=child_ok,
            detail=child_detail[:_MAX_CAPTURE],
        )
    )

    out_ok, out_detail = _worker_output_nonempty(
        evidence_root=evidence_root,
        attempt_id=attempt_id or baseline.attempt_id,
        workspace=workspace,
    )
    checks.append(
        CheckResult(
            check_id="worker-output-nonempty",
            kind=AcceptanceKind.FILE_MATCHES,
            passed=out_ok,
            detail=out_detail[:_MAX_CAPTURE],
        )
    )

    needs_reviewer = (
        task.requires_independent_verification
        if require_reviewer is None
        else require_reviewer
    )
    if needs_reviewer:
        if reviewer_verdict == "PASS":
            checks.append(
                CheckResult(
                    check_id="independent-reviewer",
                    kind=AcceptanceKind.FILE_MATCHES,
                    passed=True,
                    detail="independent reviewer verdict PASS",
                )
            )
        elif reviewer_verdict in {None, ""}:
            checks.append(
                CheckResult(
                    check_id="independent-reviewer",
                    kind=AcceptanceKind.FILE_MATCHES,
                    passed=False,
                    detail="VERIFYING/BLOCKED: independent reviewer not run — never PASS",
                )
            )
        else:
            checks.append(
                CheckResult(
                    check_id="independent-reviewer",
                    kind=AcceptanceKind.FILE_MATCHES,
                    passed=False,
                    detail=f"independent reviewer verdict {reviewer_verdict} — not PASS",
                )
            )

    material = [c for c in checks if c.check_id != "pre-existing-dirt-recorded"]
    return AcceptanceResult(
        passed=bool(material) and all(c.passed for c in material),
        checks=tuple(checks),
    )


def merge_acceptance_results(*results: AcceptanceResult) -> AcceptanceResult:
    checks: list[CheckResult] = []
    for result in results:
        checks.extend(result.checks)
    # pre-existing-dirt-recorded is documentary; exclude from pass aggregation
    material = [c for c in checks if c.check_id != "pre-existing-dirt-recorded"]
    return AcceptanceResult(
        passed=bool(material) and all(c.passed for c in material),
        checks=tuple(checks),
    )
