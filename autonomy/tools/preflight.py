#!/usr/bin/env python3
"""Governed RSI loop preflight and scope gate (D-ATLAS-RSI-GOVERNED-LOOP-001).

Owner-controlled: ``autonomy/tools/**`` is outside every agent-writable scope, so the
loop can never weaken the gate that checks it. Rules live in ``autonomy/policy.md``
section 4; this module only evaluates them. Output is ASCII-only so it stays
encodable on a cp1252 Windows console.

Exit codes: 0 pass, 1 violations, 2 usage or configuration error (fail closed).

    python autonomy/tools/preflight.py sha
    python autonomy/tools/preflight.py preflight --iteration N [--grant-ref origin/main]
    python autonomy/tools/preflight.py scope --iteration N [--grant-ref REF] [--head HEAD]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

POLICY_PATH = "autonomy/policy.md"
LOOP_PATH = "autonomy/loop.yaml"
HALT_PATH = "autonomy/HALT"
LEDGER_PATH = "autonomy/ledger.jsonl"
DIRECTIVES_PREFIX = "autonomy/directives/"
POLICY_BLOCK_MARKER = "# autonomy-policy v1"
BUDGET_KEYS = ("max_files_touched", "max_diff_lines", "max_wall_clock_minutes", "max_tokens")

# Paths no grant exception can ever open, whatever policy.md or a grant says.
NEVER_GRANTABLE = (
    "autonomy/policy.md",
    "autonomy/loop.yaml",
    "autonomy/grants/**",
    "autonomy/verdicts/**",
    "autonomy/tools/**",
    ".github/**",
)

_POLICY_BLOCK = re.compile(
    r"^```yaml\n" + re.escape(POLICY_BLOCK_MARKER) + r"\n(.*?)^```[ \t]*$", re.S | re.M
)
_FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*$", re.S | re.M)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")


class ConfigError(Exception):
    """The loop's own configuration is missing or malformed."""


@dataclass(frozen=True)
class Policy:
    phase: int
    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    phase_gated: dict[int, tuple[str, ...]]
    budget: dict[str, int]
    require_signed_grants: bool


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
    phase = data.get("phase")
    if isinstance(phase, bool) or not isinstance(phase, int) or not 0 <= phase <= 4:
        raise ConfigError("policy phase must be an integer 0-4")
    gated_raw = data.get("phase_gated_scopes", {})
    if not isinstance(gated_raw, dict) or not all(isinstance(k, int) for k in gated_raw):
        raise ConfigError("policy phase_gated_scopes must map integer phases to globs")
    signed = data.get("require_signed_grants")
    if not isinstance(signed, bool):
        raise ConfigError("policy require_signed_grants must be true or false")
    return Policy(
        phase=phase,
        allowed=_str_list(data.get("allowed_scopes"), "policy allowed_scopes"),
        forbidden=_str_list(data.get("forbidden_scopes"), "policy forbidden_scopes"),
        phase_gated={
            k: _str_list(v, f"policy phase_gated_scopes.{k}") for k, v in gated_raw.items()
        },
        budget=_budget(data.get("budget"), "policy budget", required=True),
        require_signed_grants=signed,
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
    if not isinstance(directive, str) or not directive.startswith(DIRECTIVES_PREFIX):
        raise ConfigError(f"{rel} directive must be a path under {DIRECTIVES_PREFIX}")
    return Grant(
        iteration=iteration,
        policy_sha=sha,
        base_sha=base,
        directive=directive,
        budget=_budget(data.get("budget", {}), f"{rel} budget", required=False),
        scope_exceptions=_str_list(data.get("scope_exceptions", []), f"{rel} scope_exceptions"),
    )


def check_preflight(root: Path, iteration: int) -> list[str]:
    """Filesystem half of preflight; no git access."""
    if (root / HALT_PATH).exists():
        return [f"{HALT_PATH} exists: the loop is stopped"]
    try:
        actual = policy_sha(root)
        policy = load_policy(root)
        loop = load_loop(root)
    except ConfigError as exc:
        return [str(exc)]
    if not (root / grant_path(iteration)).is_file():
        return [f"missing grant {grant_path(iteration)}: no iteration without an owner grant"]
    try:
        grant = load_grant(root, iteration)
    except ConfigError as exc:
        return [str(exc)]
    problems: list[str] = []
    if loop["policy_sha"] != actual:
        problems.append(f"{LOOP_PATH} policy_sha {loop['policy_sha']} != policy.md {actual}")
    if grant.policy_sha != actual:
        problems.append(f"{grant_path(iteration)} policy_sha {grant.policy_sha} != {actual}")
    if loop["max_iterations_per_grant"] != 1 and policy.phase < 4:
        problems.append("max_iterations_per_grant > 1 requires policy phase 4")
    if not (root / grant.directive).is_file():
        problems.append(f"directive {grant.directive} named by the grant does not exist")
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


def check_git_preflight(root: Path, policy: Policy, grant: Grant, grant_ref: str) -> list[str]:
    problems: list[str] = []
    grant_rel = grant_path(grant.iteration)
    for rel in (grant_rel, POLICY_PATH):
        if _blob(root, grant_ref, rel) != _read_bytes(root, rel):
            problems.append(f"{rel} differs from {grant_ref}: only the owner-committed copy counts")
    if _blob(root, grant_ref, HALT_PATH) is not None:
        problems.append(f"{HALT_PATH} exists on {grant_ref}: the loop is stopped")
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
        added, deleted, raw_path = record.split(b"\t", 2)
        stats[raw_path.decode("utf-8", "surrogateescape")] = (
            int(added) if added != b"-" else 0,
            int(deleted) if deleted != b"-" else 0,
        )
    names = _git_ok(root, "diff", "--no-renames", "--name-status", "-z", base, head)
    tokens = [token for token in names.split(b"\0") if token]
    changes: list[Change] = []
    for status, raw_path in zip(tokens[0::2], tokens[1::2], strict=True):
        path = raw_path.decode("utf-8", "surrogateescape")
        added, deleted = stats.get(path, (0, 0))
        changes.append(Change(path, status.decode("ascii")[:1], added, deleted))
    return changes


def ledger_is_append_only(root: Path, base_ref: str, head: str) -> bool:
    base = merge_base(root, base_ref, head)
    before = _blob(root, base, LEDGER_PATH) or b""
    after = _blob(root, head, LEDGER_PATH)
    return after is not None and after.startswith(before)


def check_scope(policy: Policy, grant: Grant, changes: list[Change]) -> list[str]:
    """Judge every changed path and the size budget per policy.md sections 4.1-4.2."""
    opened = policy.allowed + tuple(
        glob
        for phase, globs in policy.phase_gated.items()
        if phase <= policy.phase
        for glob in globs
    )
    problems: list[str] = []
    for change in changes:
        if change.path == HALT_PATH:
            if change.status != "A":
                problems.append(f"{HALT_PATH}: may be created, never modified or removed")
        elif matches_any(change.path, NEVER_GRANTABLE):
            problems.append(f"{change.path}: never-grantable scope")
        elif matches_any(change.path, grant.scope_exceptions):
            pass
        elif matches_any(change.path, policy.forbidden):
            problems.append(f"{change.path}: forbidden scope")
        elif not matches_any(change.path, opened):
            problems.append(f"{change.path}: outside allowed scopes at phase {policy.phase}")
        if change.path == LEDGER_PATH and change.deleted:
            problems.append(f"{LEDGER_PATH}: append-only, {change.deleted} line(s) removed")
    budget = {**policy.budget, **grant.budget}
    files = len(changes)
    lines = sum(change.added + change.deleted for change in changes)
    if files > budget["max_files_touched"]:
        problems.append(f"budget: {files} files > max_files_touched {budget['max_files_touched']}")
    if lines > budget["max_diff_lines"]:
        problems.append(f"budget: {lines} diff lines > max_diff_lines {budget['max_diff_lines']}")
    return problems


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
        else:
            policy = load_policy(root)
            grant = load_grant(root, args.iteration)
            changes = git_changes(root, args.grant_ref, args.head)
            problems = check_scope(policy, grant, changes)
            ledger_changed = any(change.path == LEDGER_PATH for change in changes)
            if ledger_changed and not ledger_is_append_only(root, args.grant_ref, args.head):
                problems.append(f"{LEDGER_PATH}: head does not extend the base content")
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
