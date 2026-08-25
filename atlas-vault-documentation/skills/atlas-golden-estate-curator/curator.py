"""ATLAS-GOLDEN-ESTATE-SKILL-001 — read-only golden estate curator.

Default mode is DISCOVER_ONLY. Source projects are evidence.
This module never moves, deletes, renames, or modifies source trees.
COPY / GOLDENIZE require explicit owner authorization and are refused
in this implementation (owner-only frontier).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

PACKAGE_ID: Final[str] = "ATLAS-GOLDEN-ESTATE-SKILL-001"
SKILL_ID: Final[str] = "atlas-golden-estate-curator"
SKILL_VERSION: Final[str] = "1.0.0"
DEFAULT_MODE: Final[str] = "DISCOVER_ONLY"
SOURCE_PROJECTS_ARE_EVIDENCE: Final[bool] = True

SAFE_PHASES: Final[frozenset[str]] = frozenset(
    {"DISCOVER", "INVENTORY", "QUALIFY", "RECOMMEND", "OWNER_GATE"}
)
OWNER_GATED_PHASES: Final[frozenset[str]] = frozenset(
    {
        "COPY",
        "BASELINE_FREEZE",
        "GOLDENIZE",
        "INDEPENDENT_VERIFY",
        "FREEZE_ESTATE",
    }
)
FORBIDDEN_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "MOVE",
        "DELETE",
        "RENAME",
        "SOURCE_MODIFY",
        "GIT_CLEAN",
        "GIT_RESET",
        "HISTORY_REWRITE",
        "AUTO_COMMIT",
        "AUTO_PUSH",
        "AUTO_MERGE",
    }
)

SKIP_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "generated",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".atlas-estate-output",
    }
)
SECRET_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(^|\.)(env|pem|p12|pfx|keystore|id_rsa|credentials|secret)(\.|$)"
)
SECRET_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(aws_secret_access_key|begin (rsa |openssh )?private key|xox[baprs]-)"
)
WINDOWS_LONG_PATH: Final[int] = 240


class CuratorError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise CuratorError(code, message)


def reject_mutation(action: str) -> None:
    name = action.strip().upper().replace("-", "_")
    if name in FORBIDDEN_ACTIONS or name in OWNER_GATED_PHASES:
        _fail(
            "MUTATION_FORBIDDEN",
            f"{name} is forbidden in DISCOVER_ONLY; COPY/GOLDENIZE require owner authorization",
        )
    _fail("UNKNOWN_ACTION", f"unsupported action {action!r}")


def _is_unc(raw: str) -> bool:
    value = raw.replace("/", "\\")
    return value.startswith("\\\\") or raw.startswith("//")


def resolve_source_root(source_root: Path | str) -> Path:
    raw = os.fspath(source_root)
    if _is_unc(raw):
        _fail("UNC_PATH_REJECTED", "UNC / SMB paths are fail-closed on this curator")
    if ".." in Path(raw).parts:
        _fail("PATH_TRAVERSAL", "source root must not contain '..'")
    try:
        resolved = Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        _fail("UNRESOLVABLE_ROOT", str(exc))
    if not resolved.is_dir():
        _fail("SOURCE_ROOT_NOT_DIR", f"source root is not a directory: {resolved}")
    if len(str(resolved)) > WINDOWS_LONG_PATH:
        # Discover may continue with a warning classification, but the root
        # itself being over-long is fail-closed for inventory integrity.
        _fail("LONG_PATH_REJECTED", "source root exceeds Windows MAX_PATH-safe length")
    return resolved


def resolve_output_path(output: Path | str, *, source_root: Path) -> Path:
    dest = Path(output).expanduser().resolve(strict=False)
    if dest == source_root or source_root in dest.parents:
        _fail(
            "OUTPUT_INSIDE_SOURCE",
            "report output must be outside the source root (source is evidence)",
        )
    return dest


def _is_symlink_or_junction(path: Path) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    # Windows reparse/junction bit (IO_REPARSE_TAG) when available.
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _escapes(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return True
    return root not in resolved.parents and resolved != root


def _read_text_limited(path: Path, limit: int = 4096) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def _secret_hit(path: Path) -> dict[str, str] | None:
    if SECRET_NAME_RE.search(path.name):
        return {"kind": "filename", "pattern": "sensitive-name", "path": str(path.name)}
    if path.is_file() and path.stat().st_size < 65536:
        text = _read_text_limited(path)
        if SECRET_TEXT_RE.search(text):
            return {"kind": "content", "pattern": "secret-shaped", "path": str(path.name)}
    return None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _dirty(path: Path) -> bool:
    result = _git(path, "status", "--porcelain")
    return result.returncode == 0 and bool(result.stdout.strip())


def _remote_url(path: Path) -> str | None:
    result = _git(path, "config", "--get", "remote.origin.url")
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


def _walk_projects(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    generated: list[str] = []
    seen_ids: dict[str, str] = {}

    def visit(current: Path, *, parent_git: bool) -> None:
        if len(str(current)) > WINDOWS_LONG_PATH:
            exclusions.append(
                {"path": str(current.name), "reason": "LONG_PATH", "action": "skip"}
            )
            return
        if _is_symlink_or_junction(current):
            if _escapes(current, root):
                exclusions.append(
                    {
                        "path": current.name,
                        "reason": "SYMLINK_OR_JUNCTION_ESCAPE",
                        "action": "fail_closed_skip",
                    }
                )
                return
            exclusions.append(
                {"path": current.name, "reason": "SYMLINK", "action": "skip_follow"}
            )
            return
        if not current.is_dir():
            return
        if current.name in SKIP_DIR_NAMES and current != root:
            if current.name in {"node_modules", "dist", "build", "generated", ".venv"}:
                generated.append(str(current.relative_to(root)))
            return

        git_here = _is_git_repo(current)
        marker = current / ".atlas-project.yaml"
        readme = current / "README.md"
        signals = current / ".atlas-estate" / "signals"
        is_project = git_here or marker.is_file() or (readme.is_file() and current != root)

        if is_project:
            identity = current.name
            if marker.is_file():
                text = _read_text_limited(marker)
                match = re.search(r"(?m)^id:\s*(\S+)", text)
                if match:
                    identity = match.group(1)
            duplicate = identity in seen_ids
            seen_ids.setdefault(identity, str(current.relative_to(root)))
            secret_findings: list[dict[str, str]] = []
            for child in current.iterdir():
                if child.name in SKIP_DIR_NAMES:
                    continue
                if child.is_file():
                    hit = _secret_hit(child)
                    if hit:
                        secret_findings.append(hit)
            records.append(
                {
                    "path": str(current.relative_to(root)),
                    "name": current.name,
                    "identity": identity,
                    "kind": (
                        "nested-repo"
                        if git_here and parent_git
                        else "git"
                        if git_here
                        else "non-git"
                    ),
                    "git": git_here,
                    "nested_repo": bool(git_here and parent_git),
                    "monorepo": (current / "packages").is_dir()
                    or (current / "apps").is_dir(),
                    "dirty_worktree": _dirty(current) if git_here else False,
                    "missing_readme": not readme.is_file(),
                    "stale_docs": _stale_docs(current),
                    "test_failure_signal": (signals / "test_failed").is_file(),
                    "build_failure_signal": (signals / "build_failed").is_file(),
                    "secret_findings": secret_findings,
                    "duplicate_identity": duplicate,
                    "duplicate_of": seen_ids.get(identity) if duplicate else None,
                    "remote": _remote_url(current) if git_here else None,
                    "malicious_build_script": _malicious_build(current),
                    "executed_build": False,
                    "source_mutated": False,
                }
            )

        next_parent_git = parent_git or git_here
        try:
            children = list(current.iterdir())
        except OSError:
            return
        for child in children:
            if child.name in SKIP_DIR_NAMES:
                if child.name in {"node_modules", "dist", "build", "generated", ".venv"}:
                    generated.append(str(child.relative_to(root)))
                continue
            visit(child, parent_git=next_parent_git)

    visit(root, parent_git=False)
    return [
        {"projects": records, "exclusions": exclusions, "generated_directories": generated}
    ]


def _malicious_build(project: Path) -> bool:
    if (project / "malicious-build.sh").is_file():
        return True
    build = project / "build.sh"
    return build.is_file() and "rm -rf" in _read_text_limited(build)


def _stale_docs(project: Path) -> bool:
    readme = project / "README.md"
    if not readme.is_file():
        return False
    newest_src = 0.0
    for folder in (project / "src", project / "lib", project / "app"):
        if not folder.is_dir():
            continue
        for item in folder.rglob("*"):
            if item.is_file() and not _is_symlink_or_junction(item):
                try:
                    newest_src = max(newest_src, item.stat().st_mtime)
                except OSError:
                    continue
    if newest_src <= 0:
        return False
    try:
        return readme.stat().st_mtime + 1 < newest_src
    except OSError:
        return False


def qualify(project: dict[str, Any]) -> dict[str, Any]:
    """Objective signals only. No subjective trust score."""
    blockers: list[str] = []
    if project.get("secret_findings"):
        blockers.append("SECRET_PRESENT")
    if project.get("malicious_build_script"):
        blockers.append("MALICIOUS_BUILD_SCRIPT")
    if project.get("duplicate_identity"):
        blockers.append("DUPLICATE_IDENTITY")
    if project.get("nested_repo"):
        blockers.append("NESTED_REPO")
    challenge = any(
        [
            project.get("dirty_worktree"),
            project.get("missing_readme"),
            project.get("stale_docs"),
            project.get("test_failure_signal"),
            project.get("build_failure_signal"),
            project.get("kind") == "non-git",
        ]
    )
    # QUALIFICATION.md: challenge signals (including stale_docs) cannot
    # remain golden_candidate. Blockers are exclusive exclusions.
    golden = project.get("kind") == "git" and not challenge and not blockers
    return {
        "identity": project.get("identity"),
        "path": project.get("path"),
        "golden_candidate": golden,
        "challenge_candidate": challenge and not blockers,
        "excluded": bool(blockers),
        "blockers": blockers,
        "signals": {
            key: project.get(key)
            for key in (
                "kind",
                "dirty_worktree",
                "missing_readme",
                "stale_docs",
                "test_failure_signal",
                "build_failure_signal",
                "monorepo",
                "nested_repo",
            )
        },
    }


def recommend(qualifications: list[dict[str, Any]]) -> dict[str, Any]:
    golden = [item["path"] for item in qualifications if item["golden_candidate"]]
    challenge = [item["path"] for item in qualifications if item["challenge_candidate"]]
    excluded = [item["path"] for item in qualifications if item["excluded"]]
    return {
        "recommended_golden_set": golden,
        "recommended_challenge_set": challenge,
        "security_exclusions": excluded,
        "owner_gate": "STOP",
        "copy_authorized": False,
        "goldenize_authorized": False,
        "note": "Default execution stops at OWNER_GATE. No copies or moves.",
    }


def estimate_disk(root: Path) -> dict[str, int]:
    total = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if _is_symlink_or_junction(path):
                continue
            try:
                total += path.stat().st_size
                files += 1
            except OSError:
                continue
    return {"bytes": total, "files": files}


def curate(
    source_root: Path | str,
    *,
    mode: str = DEFAULT_MODE,
    phase: str = "RECOMMEND",
    output: Path | str | None = None,
    owner_authorize_copy: bool = False,
) -> dict[str, Any]:
    requested = phase.strip().upper()
    if requested in FORBIDDEN_ACTIONS:
        reject_mutation(requested)
    if requested in OWNER_GATED_PHASES:
        _fail(
            "OWNER_GATE_REQUIRED",
            f"{requested} is owner-gated; this skill stops at OWNER_GATE "
            f"(owner_authorize_copy={owner_authorize_copy} is not sufficient here)",
        )
    if requested not in SAFE_PHASES:
        _fail("UNKNOWN_PHASE", f"unsupported phase {phase!r}")
    if mode.strip().upper() != DEFAULT_MODE:
        _fail("UNSUPPORTED_MODE", f"only {DEFAULT_MODE} is implemented")

    root = resolve_source_root(source_root)
    walked = _walk_projects(root)[0]
    projects = walked["projects"]
    qualifications = [qualify(item) for item in projects]
    rec = recommend(qualifications)
    disk = estimate_disk(root)
    report = {
        "schema": "atlas.golden-estate-curator.report.v1",
        "package": PACKAGE_ID,
        "skill_id": SKILL_ID,
        "skill_version": SKILL_VERSION,
        "mode": DEFAULT_MODE,
        "phase_reached": requested,
        "source_root": str(root),
        "source_projects_are_evidence": SOURCE_PROJECTS_ARE_EVIDENCE,
        "source_mutations": 0,
        "files_moved": 0,
        "files_deleted": 0,
        "inventory": projects,
        "qualification": qualifications,
        "candidate_table": qualifications,
        "exclusions": walked["exclusions"],
        "generated_directories": walked["generated_directories"],
        "disk_estimate": disk,
        "recommendation": rec,
        "windows_d_drive": {
            "authentic_test": "LOCAL_WINDOWS_REQUIRED",
            "cloud_certified": False,
        },
        "owner_gate": "STOP",
        "copy": False,
        "goldenize": False,
    }
    if output is not None:
        dest = resolve_output_path(output, source_root=root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = str(dest)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-golden-estate-curator",
        description="Read-only Atlas golden estate curator (DISCOVER_ONLY).",
    )
    parser.add_argument("--source-root", required=True, help="Root to scan. Evidence only.")
    parser.add_argument("--mode", default=DEFAULT_MODE, help="Only DISCOVER_ONLY is implemented.")
    parser.add_argument(
        "--phase",
        default="RECOMMEND",
        help="DISCOVER|INVENTORY|QUALIFY|RECOMMEND|OWNER_GATE. COPY/GOLDENIZE fail closed.",
    )
    parser.add_argument("--output", default=None, help="JSON report path outside the source root.")
    parser.add_argument(
        "--action",
        default=None,
        help="Forbidden mutation actions (MOVE/DELETE/...) always fail closed.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--owner-authorize-copy",
        action="store_true",
        help="Even if set, COPY/GOLDENIZE remain unimplemented and fail closed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action:
            reject_mutation(str(args.action))
        report = curate(
            args.source_root,
            mode=str(args.mode),
            phase=str(args.phase),
            output=args.output,
            owner_authorize_copy=bool(args.owner_authorize_copy),
        )
    except CuratorError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "detail": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
