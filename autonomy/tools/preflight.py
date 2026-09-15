#!/usr/bin/env python3
"""Governed RSI loop preflight, ledger and scope gate.

Mechanical checks for D-ATLAS-RSI-GOVERNED-LOOP-001 and D-ATLAS-AUTONOMY-LADDER-001.
Owner-controlled: ``autonomy/tools/**`` is never writable by any loop role, so the loop
cannot weaken the gate that checks it. Policy values live in ``autonomy/policy.md``
section 4; the floors, the retry cap and the role-separation rule below are hard-coded on
purpose. Output is ASCII-only so it stays encodable on a cp1252 Windows console.

Exit codes: 0 pass, 1 violations, 2 usage or configuration error (fail closed).

    python autonomy/tools/preflight.py sha
    python autonomy/tools/preflight.py preflight --iteration N [--grant-ref origin/main]
    python autonomy/tools/preflight.py scope --iteration N [--role executor]
                                             [--grant-ref origin/main] [--head HEAD]
    python autonomy/tools/preflight.py cert --iteration N [--head SHA] [--require ci]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

POLICY_PATH = "autonomy/policy.md"
LOOP_PATH = "autonomy/loop.yaml"
HALT_PATH = "autonomy/HALT"
HALT_REQUEST_PATH = "autonomy/HALT-REQUEST"
LEDGER_PATH = "autonomy/ledger.jsonl"
DIRECTIVES_PREFIX = "autonomy/directives/"
POLICY_BLOCK_MARKER = "# autonomy-policy v1"
BUDGET_KEYS = ("max_files_touched", "max_diff_lines", "max_wall_clock_minutes", "max_tokens")
KILL_SWITCHES = (HALT_PATH, HALT_REQUEST_PATH)
MAX_AUTONOMY_LEVEL = 4

ROLES = ("executor", "verifier", "instrument", "supervisor")
ROLE_TRAILER = "Atlas-Role"
VERDICTS = ("ACCELERATE", "CONTINUE", "REDESIGN", "DEFER", "STOP", "OWNER_DECISION_REQUIRED")
CLOSING_VERDICTS = ("ACCELERATE", "CONTINUE", "DEFER", "STOP")
NEXT_OPENING_VERDICTS = ("ACCELERATE", "CONTINUE", "DEFER")
OWNER_ONLY_EVENTS = ("resume",)
# REDESIGN reworks the same grant at most this many times; one more REDESIGN stops the loop.
MAX_REDESIGN_RETRIES = 2
MULTI_ITERATION_GRANT_LEVEL = 3

CERTS_PREFIX = "autonomy/certs/"
LANE_NAMES = ("linux", "windows-native")
LANE_MODES = ("ci", "local")
CERT_RESULTS = ("PASS", "FAIL")
HOST_KEYS = ("hostname", "os", "python", "git")
FALLBACK_RULE = {
    "when": "ci_unavailable",
    "run_by": "verifier",
    "lane_mode": "local",
    "expires": "ci_available",
}

# No role, autonomy level or grant exception can open these.
NEVER_WRITABLE = (
    "autonomy/policy.md",
    "autonomy/loop.yaml",
    "autonomy/tools/**",
    ".github/**",
)
# The executor can never write another role's output.
EXECUTOR_NEVER = (
    "autonomy/grants/**",
    "autonomy/verdicts/**",
    "autonomy/certs/**",
    "autonomy/drift/**",
    "autonomy/audits/**",
    "autonomy/proposals/**",
)
# Only the executor changes product code: roles are never collapsed.
NON_EXECUTOR_NEVER = ("src/**", "tests/**")

_POLICY_BLOCK = re.compile(
    r"^```yaml\n" + re.escape(POLICY_BLOCK_MARKER) + r"\n(.*?)^```[ \t]*$", re.S | re.M
)
_FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*$", re.S | re.M)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_RUN_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/actions/runs/[0-9]+(?:/job/[0-9]+)?")


class ConfigError(Exception):
    """The loop's own configuration or ledger is missing or malformed."""


def _opened(tiers: Mapping[int, tuple[str, ...]], level: int) -> tuple[str, ...]:
    return tuple(glob for tier in sorted(tiers) if tier <= level for glob in tiers[tier])


@dataclass(frozen=True)
class Policy:
    level: int
    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    level_gated: dict[int, tuple[str, ...]]
    role_scopes: dict[str, dict[int, tuple[str, ...]]]
    budget: dict[str, int]
    require_signed_grants: bool
    lanes: dict[str, str]
    fallback: dict[str, str] | None

    def scopes_for(self, role: str, iteration: int) -> tuple[str, ...]:
        if role == "executor":
            globs = self.allowed + _opened(self.level_gated, self.level)
        else:
            globs = _opened(self.role_scopes.get(role, {}), self.level)
        return tuple(glob.replace("{n}", str(iteration)) for glob in globs)


@dataclass(frozen=True)
class Grant:
    iteration: int
    policy_sha: str
    base_sha: str
    directive: str
    budget: dict[str, int] = field(default_factory=dict)
    scope_exceptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Change:
    path: str
    status: str  # git --name-status letter with renames disabled: A, M, D, T
    added: int
    deleted: int


def grant_path(iteration: int) -> str:
    return f"autonomy/grants/G-{iteration}.md"


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(glob_to_regex(pattern).match(path) for pattern in patterns)


def _read_bytes(root: Path, rel: str) -> bytes:
    try:
        return (root / rel).read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read {rel}: {exc.strerror or exc}") from exc


def policy_sha(root: Path) -> str:
    data = _read_bytes(root, POLICY_PATH)
    if b"\r" in data:
        raise ConfigError(f"{POLICY_PATH} contains CR bytes; policy_sha is defined over LF bytes")
    return hashlib.sha256(data).hexdigest()


def _str_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ConfigError(f"{name} must be a list of non-empty strings")
    return tuple(value)


def _level(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an autonomy level 0-{MAX_AUTONOMY_LEVEL}")
    level: int = value
    if not 0 <= level <= MAX_AUTONOMY_LEVEL:
        raise ConfigError(f"{name} must be an autonomy level 0-{MAX_AUTONOMY_LEVEL}")
    return level


def _level_map(value: Any, name: str) -> dict[int, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must map autonomy levels to glob lists")
    return {
        _level(level, f"{name} key"): _str_list(globs, f"{name}.{level}")
        for level, globs in value.items()
    }


def _budget(value: Any, name: str, *, required: bool) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping")
    unknown = sorted(str(key) for key in set(value) - set(BUDGET_KEYS))
    if unknown:
        raise ConfigError(f"{name} has unknown keys: {', '.join(unknown)}")
    if required and set(value) != set(BUDGET_KEYS):
        raise ConfigError(f"{name} must define {', '.join(BUDGET_KEYS)}")
    for key, amount in value.items():
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ConfigError(f"{name}.{key} must be a non-negative integer")
    return dict(value)


def load_policy(root: Path) -> Policy:
    text = _read_bytes(root, POLICY_PATH).decode("utf-8")
    blocks = _POLICY_BLOCK.findall(text)
    if len(blocks) != 1:
        raise ConfigError(f"{POLICY_PATH} must contain exactly one '{POLICY_BLOCK_MARKER}' block")
    try:
        data = yaml.safe_load(blocks[0])
    except yaml.YAMLError as exc:
        raise ConfigError(f"{POLICY_PATH} policy block is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{POLICY_PATH} policy block must be a mapping")
    roles_raw = data.get("role_scopes", {})
    other_roles = set(ROLES) - {"executor"}
    if not isinstance(roles_raw, dict) or not set(roles_raw) <= other_roles:
        raise ConfigError("policy role_scopes keys must be verifier, instrument or supervisor")
    signed = data.get("require_signed_grants")
    if not isinstance(signed, bool):
        raise ConfigError("policy require_signed_grants must be true or false")
    lanes = data.get("lanes")
    required = lanes.get("required") if isinstance(lanes, dict) else None
    if (
        not isinstance(required, dict)
        or set(required) != set(LANE_NAMES)
        or not all(isinstance(check, str) and check for check in required.values())
    ):
        raise ConfigError(f"policy lanes.required must name CI checks for {', '.join(LANE_NAMES)}")
    fallback = lanes.get("fallback") if isinstance(lanes, dict) else None
    if fallback is not None and (
        not isinstance(fallback, dict)
        or any(fallback.get(key) != value for key, value in FALLBACK_RULE.items())
        or not isinstance(fallback.get("host"), str)
    ):
        rule = ", ".join(f"{key}: {value}" for key, value in FALLBACK_RULE.items())
        raise ConfigError(f"policy lanes.fallback must set host and {rule}")
    return Policy(
        level=_level(data.get("autonomy_level"), "policy autonomy_level"),
        allowed=_str_list(data.get("allowed_scopes"), "policy allowed_scopes"),
        forbidden=_str_list(data.get("forbidden_scopes"), "policy forbidden_scopes"),
        level_gated=_level_map(data.get("level_gated_scopes", {}), "policy level_gated_scopes"),
        role_scopes={
            role: _level_map(tiers, f"policy role_scopes.{role}")
            for role, tiers in roles_raw.items()
        },
        budget=_budget(data.get("budget"), "policy budget", required=True),
        require_signed_grants=signed,
        lanes=dict(required),
        fallback=dict(fallback) if fallback is not None else None,
    )


def load_loop(root: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(_read_bytes(root, LOOP_PATH).decode("utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{LOOP_PATH} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ConfigError(f"{LOOP_PATH} must be a mapping with version: 1")
    per_grant = data.get("max_iterations_per_grant")
    if isinstance(per_grant, bool) or not isinstance(per_grant, int) or per_grant < 1:
        raise ConfigError(f"{LOOP_PATH} max_iterations_per_grant must be a positive integer")
    sha = data.get("policy_sha")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ConfigError(f"{LOOP_PATH} policy_sha must be 64 lowercase hex characters")
    if data.get("halt_file") != HALT_PATH:
        raise ConfigError(f"{LOOP_PATH} halt_file must be {HALT_PATH}")
    return data


def load_grant(root: Path, iteration: int) -> Grant:
    rel = grant_path(iteration)
    match = _FRONTMATTER.match(_read_bytes(root, rel).decode("utf-8"))
    if match is None:
        raise ConfigError(f"{rel} must start with a '---' frontmatter block")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{rel} frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{rel} frontmatter must be a mapping")
    if data.get("grant") != f"G-{iteration}" or data.get("iteration") != iteration:
        raise ConfigError(f"{rel} must declare grant: G-{iteration} and iteration: {iteration}")
    sha = data.get("policy_sha")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ConfigError(f"{rel} policy_sha must be 64 lowercase hex characters")
    base = data.get("base_sha")
    if not isinstance(base, str) or not _GIT_SHA.fullmatch(base):
        raise ConfigError(f"{rel} base_sha must be a full 40-character commit SHA")
    directive = data.get("directive")
    if (
        not isinstance(directive, str)
        or not directive.startswith(DIRECTIVES_PREFIX)
        or "\\" in directive
        or any(part in {"", ".", ".."} for part in Path(directive).parts)
    ):
        raise ConfigError(f"{rel} directive must be a normalized path under {DIRECTIVES_PREFIX}")
    return Grant(
        iteration=iteration,
        policy_sha=sha,
        base_sha=base,
        directive=directive,
        budget=_budget(data.get("budget", {}), f"{rel} budget", required=False),
        scope_exceptions=_str_list(data.get("scope_exceptions", []), f"{rel} scope_exceptions"),
    )


def load_ledger(root: Path) -> list[dict[str, Any]]:
    """Parse the append-only ledger. Any malformed line is treated as tampering."""
    data = _read_bytes(root, LEDGER_PATH)
    if b"\r" in data or (data and not data.endswith(b"\n")):
        raise ConfigError(f"{LEDGER_PATH} must be LF-terminated lines: ledger tampering suspected")
    try:
        lines = data.decode("utf-8").split("\n")[:-1]
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{LEDGER_PATH} is not UTF-8: ledger tampering suspected") from exc
    events: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise ConfigError(
                f"{LEDGER_PATH} line {number} is not JSON: ledger tampering suspected"
            ) from exc
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise ConfigError(f"{LEDGER_PATH} line {number} has no event name: tampering suspected")
        if event["event"] == "verdict":
            n = event.get("iteration")
            if event.get("verdict") not in VERDICTS or isinstance(n, bool) or not isinstance(n, int):
                raise ConfigError(f"{LEDGER_PATH} line {number} is not a valid verdict event")
        events.append(event)
    return events


def _verdicts_for(events: list[dict[str, Any]], iteration: int) -> list[str]:
    return [e["verdict"] for e in events if e["event"] == "verdict" and e["iteration"] == iteration]


def check_ledger(events: list[dict[str, Any]], iteration: int) -> list[str]:
    """Ledger-derived stop, pause, sequencing and retry-cap rules (policy section 8.1)."""
    problems: list[str] = []
    since_resume = events
    for index, event in enumerate(events):
        if event["event"] == "resume":
            since_resume = events[index + 1 :]
    if any(e["event"] == "verdict" and e["verdict"] == "STOP" for e in since_resume):
        problems.append("a STOP verdict is recorded with no later owner resume: the loop is stopped")
    verdicts = _verdicts_for(events, iteration)
    closing = [verdict for verdict in verdicts if verdict in CLOSING_VERDICTS]
    if closing:
        problems.append(f"iteration {iteration} is already closed by verdict {closing[-1]}")
    elif verdicts and verdicts[-1] == "OWNER_DECISION_REQUIRED":
        problems.append(f"iteration {iteration} is paused awaiting an owner decision")
    redesigns = verdicts.count("REDESIGN")
    if redesigns > MAX_REDESIGN_RETRIES:
        problems.append(
            f"retry cap: iteration {iteration} has {redesigns} REDESIGN verdicts "
            f"(max {MAX_REDESIGN_RETRIES} retries); create {HALT_REQUEST_PATH}"
        )
    if iteration > 1:
        previous = _verdicts_for(events, iteration - 1)
        opened = any(verdict in NEXT_OPENING_VERDICTS for verdict in previous)
        if not opened:
            # STOP closes n; a later owner resume is the documented recovery that opens n+1.
            opened = "STOP" in previous and "STOP" not in _verdicts_for(
                since_resume, iteration - 1
            )
        if not opened:
            problems.append(
                f"iteration {iteration - 1} has no CONTINUE, ACCELERATE or DEFER verdict in the ledger"
            )
    return problems


def check_preflight(root: Path, iteration: int) -> list[str]:
    """Filesystem half of preflight; no git access."""
    halted = [f"{path} exists: the loop is stopped" for path in KILL_SWITCHES if (root / path).exists()]
    if halted:
        return halted
    if iteration < 1:
        return ["iteration must be 1 or greater"]
    try:
        actual = policy_sha(root)
        policy = load_policy(root)
        loop = load_loop(root)
        events = load_ledger(root)
    except ConfigError as exc:
        return [str(exc)]
    if not (root / grant_path(iteration)).is_file():
        return [f"missing grant {grant_path(iteration)}: no iteration without a grant"]
    try:
        grant = load_grant(root, iteration)
    except ConfigError as exc:
        return [str(exc)]
    problems: list[str] = []
    if loop["policy_sha"] != actual:
        problems.append(f"{LOOP_PATH} policy_sha {loop['policy_sha']} != policy.md {actual}")
    if grant.policy_sha != actual:
        problems.append(f"{grant_path(iteration)} policy_sha {grant.policy_sha} != {actual}")
    if loop["max_iterations_per_grant"] != 1 and policy.level < MULTI_ITERATION_GRANT_LEVEL:
        problems.append(
            f"max_iterations_per_grant > 1 requires autonomy level {MULTI_ITERATION_GRANT_LEVEL}"
        )
    if not (root / grant.directive).is_file():
        problems.append(f"directive {grant.directive} named by the grant does not exist")
    problems.extend(check_ledger(events, iteration))
    return problems


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)


def _git_ok(root: Path, *args: str) -> bytes:
    result = _git(root, *args)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ConfigError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _blob(root: Path, ref: str, rel: str) -> bytes | None:
    result = _git(root, "show", f"{ref}:{rel}")
    return result.stdout if result.returncode == 0 else None


def _remote_tracking(grant_ref: str, remotes: list[str]) -> tuple[str, str] | None:
    """Return ``(remote, branch)`` for a remote-tracking grant ref, else None."""
    rest = grant_ref
    if rest.startswith("refs/remotes/"):
        rest = rest[len("refs/remotes/") :]
    for remote in sorted(remotes, key=len, reverse=True):
        prefix = f"{remote}/"
        if rest.startswith(prefix):
            name = rest[len(prefix) :]
            if name:
                return remote, name
    return None


def refresh_grant_ref(root: Path, grant_ref: str) -> str:
    """Fetch a remote-tracking grant ref before judging HALT and pins.

    A name ``<remote>/<branch>`` or ``refs/remotes/<remote>/<branch>`` is
    refreshed from that remote and returned as the unambiguous remotes ref so a
    local branch of the same name cannot shadow the fetched tip. Fetch failure
    is fail-closed. Local branches and raw SHAs are unchanged.
    """
    remotes = [line for line in _git_ok(root, "remote").decode("utf-8").splitlines() if line]
    parsed = _remote_tracking(grant_ref, remotes)
    if parsed is None:
        return grant_ref
    remote, name = parsed
    _git_ok(
        root,
        "fetch",
        "--no-tags",
        "--update-head-ok",
        remote,
        f"+refs/heads/{name}:refs/remotes/{remote}/{name}",
    )
    return f"refs/remotes/{remote}/{name}"


def check_git_preflight(root: Path, policy: Policy, grant: Grant, grant_ref: str) -> list[str]:
    grant_ref = refresh_grant_ref(root, grant_ref)
    problems: list[str] = []
    grant_rel = grant_path(grant.iteration)
    for rel in (grant_rel, POLICY_PATH, grant.directive):
        remote_blob = _blob(root, grant_ref, rel)
        if remote_blob is None:
            problems.append(f"{rel} is missing on {grant_ref}: only the granted copy counts")
        elif remote_blob != _read_bytes(root, rel):
            problems.append(
                f"{rel} differs from {grant_ref}: only the committed grant-ref copy counts"
            )
    for rel in KILL_SWITCHES:
        if _blob(root, grant_ref, rel) is not None:
            problems.append(f"{rel} exists on {grant_ref}: the loop is stopped")
    ancestor = _git(root, "merge-base", "--is-ancestor", grant.base_sha, "HEAD")
    if ancestor.returncode == 1:
        problems.append(f"base_sha {grant.base_sha} is not an ancestor of HEAD")
    elif ancestor.returncode != 0:
        problems.append(f"base_sha {grant.base_sha} cannot be resolved")
    if policy.require_signed_grants:
        status = _git_ok(root, "log", "-1", "--format=%G?", grant_ref, "--", grant_rel)
        if status.strip() != b"G":
            problems.append(f"{grant_rel} is not signed on {grant_ref}")
    return problems


def merge_base(root: Path, base_ref: str, head: str) -> str:
    return _git_ok(root, "merge-base", base_ref, head).decode("ascii").strip()


def git_changes(root: Path, base_ref: str, head: str) -> list[Change]:
    base = merge_base(root, base_ref, head)
    stats: dict[str, tuple[int, int]] = {}
    numstat = _git_ok(root, "diff", "--no-renames", "--numstat", "-z", base, head)
    for record in numstat.split(b"\0"):
        if not record:
            continue
        raw_added, raw_deleted, raw_path = record.split(b"\t", 2)
        stats[raw_path.decode("utf-8", "surrogateescape")] = (
            int(raw_added) if raw_added != b"-" else 0,
            int(raw_deleted) if raw_deleted != b"-" else 0,
        )
    names = _git_ok(root, "diff", "--no-renames", "--name-status", "-z", base, head)
    tokens = [token for token in names.split(b"\0") if token]
    changes: list[Change] = []
    for status, name in zip(tokens[0::2], tokens[1::2], strict=True):
        path = name.decode("utf-8", "surrogateescape")
        added, deleted = stats.get(path, (0, 0))
        changes.append(Change(path, status.decode("ascii")[:1], added, deleted))
    return changes


def ledger_append(root: Path, base_ref: str, head: str) -> bytes | None:
    """Bytes appended to the ledger since the merge base, or None if history was rewritten."""
    base = merge_base(root, base_ref, head)
    before = _blob(root, base, LEDGER_PATH) or b""
    after = _blob(root, head, LEDGER_PATH)
    if after is None or not after.startswith(before):
        return None
    return after[len(before) :]


def check_ledger_append(appended: bytes, role: str) -> list[str]:
    if not appended:
        return []
    if b"\r" in appended:
        return [f"{LEDGER_PATH}: appended bytes must be LF-only JSONL"]
    if not appended.endswith(b"\n"):
        return [f"{LEDGER_PATH}: appended bytes must be LF-terminated JSONL"]
    try:
        text = appended.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{LEDGER_PATH}: appended bytes are not UTF-8"]
    problems: list[str] = []
    for number, line in enumerate(text.split("\n")[:-1], start=1):
        if not line:
            problems.append(f"{LEDGER_PATH}: appended line {number} is blank")
            continue
        try:
            event = json.loads(line)
        except ValueError:
            problems.append(f"{LEDGER_PATH}: appended line {number} is not JSON")
            continue
        name = event.get("event") if isinstance(event, dict) else None
        if name in OWNER_ONLY_EVENTS:
            problems.append(f"{LEDGER_PATH}: appended {name!r} event is owner-only")
        elif role == "executor" and name != "packet":
            problems.append(f"{LEDGER_PATH}: the executor may append only packet events, not {name!r}")
    return problems


def check_scope(
    policy: Policy, grant: Grant, changes: list[Change], role: str = "executor"
) -> list[str]:
    """Judge every changed path and the size budget per policy.md sections 4.1-4.2."""
    if role not in ROLES:
        raise ConfigError(f"unknown role {role!r}: expected one of {', '.join(ROLES)}")
    opened = policy.scopes_for(role, grant.iteration)
    problems: list[str] = []
    for change in changes:
        path = change.path
        if path == grant.directive:
            problems.append(
                f"{path}: granted directive is pinned; propose D-{grant.iteration + 1} instead"
            )
        elif path in KILL_SWITCHES:
            if change.status != "A":
                problems.append(f"{path}: may be created, never modified or removed")
        elif matches_any(path, NEVER_WRITABLE):
            problems.append(f"{path}: never writable by any loop role")
        elif role == "executor":
            if matches_any(path, EXECUTOR_NEVER):
                problems.append(f"{path}: never writable by the executor")
            elif matches_any(path, grant.scope_exceptions):
                pass
            elif matches_any(path, policy.forbidden):
                problems.append(f"{path}: forbidden scope")
            elif not matches_any(path, opened):
                problems.append(f"{path}: outside executor scopes at autonomy level {policy.level}")
        elif matches_any(path, NON_EXECUTOR_NEVER) or not matches_any(path, opened):
            problems.append(f"{path}: outside {role} scopes at autonomy level {policy.level}")
        if path == LEDGER_PATH and change.deleted:
            problems.append(f"{LEDGER_PATH}: append-only, {change.deleted} line(s) removed")
    budget = {**policy.budget, **grant.budget}
    files = len(changes)
    lines = sum(change.added + change.deleted for change in changes)
    if files > budget["max_files_touched"]:
        problems.append(f"budget: {files} files > max_files_touched {budget['max_files_touched']}")
    if lines > budget["max_diff_lines"]:
        problems.append(f"budget: {lines} diff lines > max_diff_lines {budget['max_diff_lines']}")
    return problems


def commit_roles(root: Path, base_ref: str, head: str) -> list[tuple[str, tuple[str, ...]]]:
    """(sha, declared Atlas-Role values) for every non-merge commit in merge-base..head."""
    base = merge_base(root, base_ref, head)
    fmt = f"--format=%H%x1f%(trailers:key={ROLE_TRAILER},valueonly,separator=%x2C)%x1e"
    out = _git_ok(root, "log", "--no-merges", fmt, f"{base}..{head}").decode("utf-8", "replace")
    records: list[tuple[str, tuple[str, ...]]] = []
    for record in out.split("\x1e"):
        if not record.strip():
            continue
        sha, _, declared = record.strip().partition("\x1f")
        roles = tuple(value.strip() for value in declared.split(",") if value.strip())
        records.append((sha, roles))
    return records


def check_roles(records: list[tuple[str, tuple[str, ...]]], role: str) -> list[str]:
    problems: list[str] = []
    for sha, roles in records:
        if roles != (role,):
            declared = ", ".join(roles) or "none"
            problems.append(
                f"role separation: commit {sha[:12]} declares {ROLE_TRAILER} {declared}, "
                f"expected {role}"
            )
    return problems


def cert_path(iteration: int, *, ci_recert: bool = False) -> str:
    return f"{CERTS_PREFIX}C-{iteration}{'-ci' if ci_recert else ''}.md"


def load_cert(root: Path, rel: str) -> dict[str, Any]:
    match = _FRONTMATTER.match(_read_bytes(root, rel).decode("utf-8"))
    if match is None:
        raise ConfigError(f"{rel} must start with a '---' frontmatter block")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{rel} frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{rel} frontmatter must be a mapping")
    return data


def _check_lane(lane: Any, where: str, mode: str) -> tuple[list[str], list[int]]:
    if not isinstance(lane, dict):
        return [f"{where} must be a mapping"], []
    problems: list[str] = []
    if mode == "ci":
        url = lane.get("run_url")
        if not isinstance(url, str) or not _RUN_URL.fullmatch(url):
            problems.append(f"{where}.run_url must be a GitHub Actions run URL")
    else:
        host = lane.get("host")
        if not isinstance(host, dict) or not all(
            isinstance(host.get(key), str) and host[key].strip() for key in HOST_KEYS
        ):
            problems.append(f"{where}.host must fingerprint the host with {', '.join(HOST_KEYS)}")
    commands = lane.get("commands")
    if not isinstance(commands, list) or not commands:
        return [*problems, f"{where}.commands must list at least one command"], []
    exits: list[int] = []
    for index, command in enumerate(commands):
        at = f"{where}.commands[{index}]"
        if not isinstance(command, dict):
            problems.append(f"{at} must be a mapping")
            continue
        cmd = command.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            problems.append(f"{at}.cmd must record the exact command")
        code = command.get("exit")
        if isinstance(code, bool) or not isinstance(code, int):
            problems.append(f"{at}.exit must be an integer exit code")
        else:
            exits.append(code)
        duration = command.get("duration_seconds")
        if isinstance(duration, bool) or not isinstance(duration, int | float) or duration < 0:
            problems.append(f"{at}.duration_seconds must be a non-negative number")
    return problems, exits


def check_cert(
    policy: Policy, cert: Mapping[str, Any], iteration: int, rel: str, *, ci_recert: bool = False
) -> list[str]:
    """Structure of one verifier cert per policy.md section 4.4."""
    problems: list[str] = []
    if cert.get("cert") != f"C-{iteration}" or cert.get("iteration") != iteration:
        problems.append(f"must declare cert: C-{iteration} and iteration: {iteration}")
    if cert.get("role") != "verifier":
        problems.append("must declare role: verifier")
    head = cert.get("head_sha")
    if not isinstance(head, str) or not _GIT_SHA.fullmatch(head):
        problems.append("head_sha must be a quoted full 40-character commit SHA")
    mode = cert.get("lane_mode")
    if mode not in LANE_MODES:
        problems.append(f"lane_mode must be one of {', '.join(LANE_MODES)}")
        return [f"{rel}: {problem}" for problem in problems]
    if ci_recert and mode != "ci":
        problems.append("a CI re-certification must declare lane_mode: ci")
    if mode == "local":
        if policy.fallback is None:
            problems.append("lane_mode: local is not allowed: policy lanes.fallback is not set")
        if cert.get("expires") != FALLBACK_RULE["expires"]:
            problems.append(f"a fallback cert must declare expires: {FALLBACK_RULE['expires']}")
        evidence = cert.get("ci_unavailable_evidence")
        if not isinstance(evidence, str) or not _RUN_URL.fullmatch(evidence):
            problems.append("a fallback cert must cite ci_unavailable_evidence as an Actions run URL")
    lanes = cert.get("lanes")
    exits: list[int] = []
    if not isinstance(lanes, dict) or set(lanes) != set(LANE_NAMES):
        problems.append(f"lanes must certify exactly {', '.join(LANE_NAMES)}")
    else:
        for name in LANE_NAMES:
            lane_problems, lane_exits = _check_lane(lanes[name], f"lanes.{name}", mode)
            problems.extend(lane_problems)
            exits.extend(lane_exits)
    result = cert.get("result")
    if result not in CERT_RESULTS:
        problems.append(f"result must be one of {', '.join(CERT_RESULTS)}")
    elif (result == "PASS") != (bool(exits) and all(code == 0 for code in exits)):
        problems.append(f"result {result} does not match the recorded exit codes")
    return [f"{rel}: {problem}" for problem in problems]


def check_certification(
    root: Path, policy: Policy, iteration: int, head: str | None, require: str | None
) -> tuple[str | None, list[str]]:
    """Effective lane mode of C-<n> (and its CI re-certification) and any problems."""
    primary = cert_path(iteration)
    recert = cert_path(iteration, ci_recert=True)
    if not (root / primary).is_file():
        return None, [f"missing cert {primary}: no gate without a verifier cert"]
    certs = [(primary, load_cert(root, primary))]
    if (root / recert).is_file():
        certs.append((recert, load_cert(root, recert)))
    problems: list[str] = []
    for rel, cert in certs:
        problems.extend(check_cert(policy, cert, iteration, rel, ci_recert=rel == recert))
    if problems:
        return None, problems
    if len(certs) == 2:
        original, recertified = certs[0][1], certs[1][1]
        if original["lane_mode"] != "local":
            problems.append(f"{recert}: only a lane_mode: local cert is re-certified")
        if recertified["head_sha"] != original["head_sha"]:
            problems.append(
                f"{recert}: re-certifies {recertified['head_sha']} but {primary} "
                f"certified {original['head_sha']}"
            )
    effective_rel, effective = certs[-1]
    if head is not None and effective["head_sha"] != head:
        problems.append(f"{effective_rel}: certifies {effective['head_sha']}, not {head}")
    if effective["result"] != "PASS":
        problems.append(f"{effective_rel}: result {effective['result']}: the head is not certified")
    if require == "ci" and effective["lane_mode"] != "ci":
        problems.append(f"{effective_rel}: fallback cert only; CI re-certification {recert} required")
    mode: str = effective["lane_mode"]
    return mode, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governed RSI loop preflight and scope gate.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sha", help="print the SHA-256 pin of autonomy/policy.md")
    for name in ("preflight", "scope"):
        sub = commands.add_parser(name)
        sub.add_argument("--iteration", type=int, required=True)
        sub.add_argument("--grant-ref", default="origin/main")
        if name == "scope":
            sub.add_argument("--head", default="HEAD")
            sub.add_argument("--role", choices=ROLES, default="executor")
    cert = commands.add_parser("cert", help="validate the verifier cert for an iteration")
    cert.add_argument("--iteration", type=int, required=True)
    cert.add_argument("--head", default=None, help="commit the cert must certify")
    cert.add_argument("--require", choices=("ci",), default=None)
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    try:
        if args.command == "sha":
            print(policy_sha(root))
            return 0
        if args.command == "preflight":
            problems = check_preflight(root, args.iteration)
            if not problems:
                problems = check_git_preflight(
                    root, load_policy(root), load_grant(root, args.iteration), args.grant_ref
                )
        elif args.command == "cert":
            head = None
            if args.head is not None:
                resolved = _git_ok(root, "rev-parse", "--verify", f"{args.head}^{{commit}}")
                head = resolved.decode("ascii").strip()
            mode, problems = check_certification(
                root, load_policy(root), args.iteration, head, args.require
            )
            if mode is not None and not problems:
                print(f"lane_mode {mode}")
        else:
            policy = load_policy(root)
            grant = load_grant(root, args.iteration)
            changes = git_changes(root, args.grant_ref, args.head)
            problems = check_scope(policy, grant, changes, args.role)
            problems.extend(check_roles(commit_roles(root, args.grant_ref, args.head), args.role))
            if any(change.path == LEDGER_PATH for change in changes):
                appended = ledger_append(root, args.grant_ref, args.head)
                if appended is None:
                    problems.append(f"{LEDGER_PATH}: head does not extend the base content")
                else:
                    problems.extend(check_ledger_append(appended, args.role))
            if _git_ok(root, "status", "--porcelain", "--untracked-files=no").strip():
                problems.append("working tree has uncommitted changes: the gate judges commits")
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"FAIL {problem}")
    print("PASS" if not problems else f"{len(problems)} violation(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
