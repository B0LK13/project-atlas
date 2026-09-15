"""ATLAS-GOLDEN-ESTATE-SKILL-001 — read-only golden estate curator.

Default mode is DISCOVER_ONLY. Source projects are evidence.
This module never moves, deletes, renames, or modifies source trees.
COPY / GOLDENIZE require explicit owner authorization and are refused
in this implementation (owner-only frontier).
"""

from __future__ import annotations

import argparse
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
CANONICAL_REPORT_PATH_SEPARATOR: Final[str] = "/"
INACCESSIBLE_REASON: Final[str] = "INACCESSIBLE_PATH"

# Closed exclusion taxonomy. INACCESSIBLE != SAFE != GOLDEN.
# SKIPPED != SCANNED. PARTIAL_DISCOVERY != COMPLETE_DISCOVERY.
EXCLUSION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "LONG_PATH",
        "SYMLINK",
        "SYMLINK_OR_JUNCTION_ESCAPE",
        INACCESSIBLE_REASON,
    }
)


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


def canonicalize_report_path(value: str | Path) -> str:
    """OS-independent report-relative identity. Never a native FS path.

    INTERNAL_FILESYSTEM_PATH = PLATFORM_NATIVE
    REPORT_RELATIVE_IDENTITY = POSIX_STYLE
    """
    text = os.fspath(value).replace("\\", CANONICAL_REPORT_PATH_SEPARATOR)
    while "//" in text:
        text = text.replace("//", CANONICAL_REPORT_PATH_SEPARATOR)
    if text.startswith("./"):
        text = text[2:]
    return text


def report_relpath(path: Path, root: Path) -> str:
    """Relative identity for serialized report fields. Uses '/' on every OS."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return canonicalize_report_path(path.name)
    return canonicalize_report_path(rel.as_posix())


def _record_inaccessible(
    exclusions: list[dict[str, Any]], path: Path, root: Path
) -> None:
    rel = report_relpath(path, root)
    if any(
        item.get("path") == rel and item.get("reason") == INACCESSIBLE_REASON
        for item in exclusions
    ):
        return
    exclusions.append(
        {
            "path": rel,
            "reason": INACCESSIBLE_REASON,
            "action": "skip",
            "inspected": False,
        }
    )


def _safe_lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except OSError:
        return None


def _safe_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def _safe_is_dir(path: Path) -> bool | None:
    try:
        return path.is_dir()
    except OSError:
        return None


def _safe_is_file(path: Path) -> bool | None:
    try:
        return path.is_file()
    except OSError:
        return None


def _safe_exists(path: Path) -> bool | None:
    try:
        return path.exists()
    except OSError:
        return None


def _safe_iterdir(path: Path) -> list[Path] | None:
    try:
        return list(path.iterdir())
    except OSError:
        return None


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
    root_dir = _safe_is_dir(resolved)
    if root_dir is None:
        _fail("SOURCE_ROOT_INACCESSIBLE", "requested source root cannot be inspected")
    if root_dir is False:
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


def _is_reparse(st: os.stat_result) -> bool:
    if stat.S_ISLNK(st.st_mode):
        return True
    # Windows reparse/junction bit (IO_REPARSE_TAG) when available.
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _is_symlink_or_junction(path: Path) -> bool:
    st = _safe_lstat(path)
    if st is None:
        return False
    return _is_reparse(st)


def _escapes(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return True
    return root not in resolved.parents and resolved != root


def _read_text_limited(path: Path, limit: int = 4096) -> str | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return None
    return raw.decode("utf-8", errors="replace")


def _secret_hit(path: Path) -> dict[str, str] | None:
    if SECRET_NAME_RE.search(path.name):
        return {"kind": "filename", "pattern": "sensitive-name", "path": str(path.name)}
    is_file = _safe_is_file(path)
    if is_file is None:
        raise OSError("secret-scan metadata inaccessible")
    st = _safe_stat(path) if is_file else None
    if is_file and st is not None and st.st_size < 65536:
        text = _read_text_limited(path)
        if text is None:
            raise OSError("secret-scan content inaccessible")
        if SECRET_TEXT_RE.search(text):
            return {"kind": "content", "pattern": "secret-shaped", "path": str(path.name)}
    if is_file and st is None:
        raise OSError("secret-scan stat inaccessible")
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
    exists = _safe_exists(path / ".git")
    return bool(exists)


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
    exclusions: list[dict[str, Any]] = []
    generated: list[str] = []
    seen_ids: dict[str, str] = {}

    def visit(current: Path, *, parent_git: bool) -> None:
        if len(str(current)) > WINDOWS_LONG_PATH:
            exclusions.append(
                {
                    "path": report_relpath(current, root),
                    "reason": "LONG_PATH",
                    "action": "skip",
                }
            )
            return

        st = _safe_lstat(current)
        if st is None:
            if current == root:
                _fail(
                    "SOURCE_ROOT_INACCESSIBLE",
                    "requested source root cannot be inspected",
                )
            _record_inaccessible(exclusions, current, root)
            return
        if _is_reparse(st):
            if _escapes(current, root):
                exclusions.append(
                    {
                        "path": report_relpath(current, root),
                        "reason": "SYMLINK_OR_JUNCTION_ESCAPE",
                        "action": "fail_closed_skip",
                    }
                )
                return
            exclusions.append(
                {
                    "path": report_relpath(current, root),
                    "reason": "SYMLINK",
                    "action": "skip_follow",
                }
            )
            return

        is_dir = _safe_is_dir(current)
        if is_dir is None:
            if current == root:
                _fail(
                    "SOURCE_ROOT_INACCESSIBLE",
                    "requested source root cannot be inspected",
                )
            _record_inaccessible(exclusions, current, root)
            return
        if is_dir is False:
            return
        if current.name in SKIP_DIR_NAMES and current != root:
            if current.name in {"node_modules", "dist", "build", "generated", ".venv"}:
                generated.append(report_relpath(current, root))
            return

        git_here = _is_git_repo(current)
        marker = current / ".atlas-project.yaml"
        readme = current / "README.md"
        signals = current / ".atlas-estate" / "signals"
        marker_file = _safe_is_file(marker)
        readme_file = _safe_is_file(readme)
        if marker_file is None:
            _record_inaccessible(exclusions, marker, root)
            marker_file = False
        if readme_file is None:
            _record_inaccessible(exclusions, readme, root)
            readme_file = False
        is_project = git_here or marker_file or (readme_file and current != root)

        if is_project:
            inspection_complete = True
            identity = current.name
            if marker_file:
                text = _read_text_limited(marker)
                if text is None:
                    _record_inaccessible(exclusions, marker, root)
                    inspection_complete = False
                else:
                    match = re.search(r"(?m)^id:\s*(\S+)", text)
                    if match:
                        identity = match.group(1)
            rel = report_relpath(current, root)
            duplicate = identity in seen_ids
            seen_ids.setdefault(identity, rel)
            secret_findings: list[dict[str, str]] = []
            exclusion_mark = len(exclusions)
            secret_children = _safe_iterdir(current)
            if secret_children is None:
                _record_inaccessible(exclusions, current, root)
                inspection_complete = False
            else:
                for child in secret_children:
                    if child.name in SKIP_DIR_NAMES:
                        continue
                    child_st = _safe_lstat(child)
                    if child_st is None:
                        _record_inaccessible(exclusions, child, root)
                        inspection_complete = False
                        continue
                    if _is_reparse(child_st):
                        continue
                    if SECRET_NAME_RE.search(child.name):
                        secret_findings.append(
                            {
                                "kind": "filename",
                                "pattern": "sensitive-name",
                                "path": str(child.name),
                            }
                        )
                        continue
                    if not stat.S_ISREG(child_st.st_mode):
                        continue
                    try:
                        hit = _secret_hit(child)
                    except OSError:
                        _record_inaccessible(exclusions, child, root)
                        inspection_complete = False
                        continue
                    if hit:
                        secret_findings.append(hit)
            packages_dir = _safe_is_dir(current / "packages")
            apps_dir = _safe_is_dir(current / "apps")
            if packages_dir is None:
                _record_inaccessible(exclusions, current / "packages", root)
                packages_dir = False
                inspection_complete = False
            if apps_dir is None:
                _record_inaccessible(exclusions, current / "apps", root)
                apps_dir = False
                inspection_complete = False
            test_signal = _safe_is_file(signals / "test_failed")
            build_signal = _safe_is_file(signals / "build_failed")
            if test_signal is None:
                _record_inaccessible(exclusions, signals / "test_failed", root)
                test_signal = False
                inspection_complete = False
            if build_signal is None:
                _record_inaccessible(exclusions, signals / "build_failed", root)
                build_signal = False
                inspection_complete = False
            try:
                stale = _stale_docs(current, exclusions, root)
            except OSError:
                _record_inaccessible(exclusions, current, root)
                stale = False
                inspection_complete = False
            if len(exclusions) > exclusion_mark:
                inspection_complete = False
            malice = _malicious_build(current)
            if malice is None:
                _record_inaccessible(exclusions, current / "build.sh", root)
                inspection_complete = False
                malice = False
            records.append(
                {
                    "path": rel,
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
                    "monorepo": bool(packages_dir or apps_dir),
                    "dirty_worktree": _dirty(current) if git_here else False,
                    "missing_readme": not readme_file,
                    "stale_docs": stale,
                    "test_failure_signal": bool(test_signal),
                    "build_failure_signal": bool(build_signal),
                    "secret_findings": secret_findings,
                    "duplicate_identity": duplicate,
                    "duplicate_of": seen_ids.get(identity) if duplicate else None,
                    "remote": _remote_url(current) if git_here else None,
                    "malicious_build_script": malice,
                    "executed_build": False,
                    "source_mutated": False,
                    "inspection_complete": inspection_complete,
                }
            )

        next_parent_git = parent_git or git_here
        children = _safe_iterdir(current)
        if children is None:
            _record_inaccessible(exclusions, current, root)
            if is_project:
                records[-1]["inspection_complete"] = False
            return
        for child in children:
            if child.name in SKIP_DIR_NAMES:
                if child.name in {"node_modules", "dist", "build", "generated", ".venv"}:
                    generated.append(report_relpath(child, root))
                continue
            visit(child, parent_git=next_parent_git)

    visit(root, parent_git=False)
    return [
        {
            "projects": records,
            "exclusions": exclusions,
            "generated_directories": [
                canonicalize_report_path(item) for item in generated
            ],
        }
    ]


def _malicious_build(project: Path) -> bool | None:
    named = _safe_is_file(project / "malicious-build.sh")
    if named is None:
        return None
    if named is True:
        return True
    build = project / "build.sh"
    build_file = _safe_is_file(build)
    if build_file is None:
        return None
    if build_file is True:
        text = _read_text_limited(build)
        if text is None:
            return None
        return "rm -rf" in text
    return False


def _stale_docs(
    project: Path,
    exclusions: list[dict[str, Any]] | None = None,
    root: Path | None = None,
) -> bool:
    readme = project / "README.md"
    readme_file = _safe_is_file(readme)
    if readme_file is None:
        if exclusions is not None and root is not None:
            _record_inaccessible(exclusions, readme, root)
        return False
    if readme_file is False:
        return False
    newest_src = 0.0
    for folder in (project / "src", project / "lib", project / "app"):
        folder_dir = _safe_is_dir(folder)
        if folder_dir is None:
            if exclusions is not None and root is not None:
                _record_inaccessible(exclusions, folder, root)
            continue
        if folder_dir is False:
            continue
        try:
            items = list(folder.rglob("*"))
        except OSError:
            if exclusions is not None and root is not None:
                _record_inaccessible(exclusions, folder, root)
            continue
        for item in items:
            st = _safe_lstat(item)
            if st is None:
                if exclusions is not None and root is not None:
                    _record_inaccessible(exclusions, item, root)
                continue
            if _is_reparse(st):
                continue
            if not stat.S_ISREG(st.st_mode):
                file_flag = _safe_is_file(item)
                if file_flag is None:
                    if exclusions is not None and root is not None:
                        _record_inaccessible(exclusions, item, root)
                    continue
                if file_flag is False:
                    continue
            meta = _safe_stat(item)
            if meta is None:
                if exclusions is not None and root is not None:
                    _record_inaccessible(exclusions, item, root)
                continue
            newest_src = max(newest_src, meta.st_mtime)
    if newest_src <= 0:
        return False
    readme_meta = _safe_stat(readme)
    if readme_meta is None:
        if exclusions is not None and root is not None:
            _record_inaccessible(exclusions, readme, root)
        return False
    return readme_meta.st_mtime + 1 < newest_src


def qualify(project: dict[str, Any]) -> dict[str, Any]:
    """Objective signals only. No subjective trust score."""
    project = {
        **project,
        "path": canonicalize_report_path(str(project.get("path") or "")),
        "duplicate_of": (
            canonicalize_report_path(str(project["duplicate_of"]))
            if project.get("duplicate_of")
            else None
        ),
    }
    blockers: list[str] = []
    if project.get("secret_findings"):
        blockers.append("SECRET_PRESENT")
    if project.get("malicious_build_script"):
        blockers.append("MALICIOUS_BUILD_SCRIPT")
    if project.get("duplicate_identity"):
        blockers.append("DUPLICATE_IDENTITY")
    if project.get("nested_repo"):
        blockers.append("NESTED_REPO")
    if project.get("inspection_complete") is False:
        blockers.append(INACCESSIBLE_REASON)
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
                "inspection_complete",
            )
        },
    }


def recommend(qualifications: list[dict[str, Any]]) -> dict[str, Any]:
    golden = [
        canonicalize_report_path(item["path"])
        for item in qualifications
        if item["golden_candidate"]
    ]
    challenge = [
        canonicalize_report_path(item["path"])
        for item in qualifications
        if item["challenge_candidate"]
    ]
    excluded = [
        canonicalize_report_path(item["path"])
        for item in qualifications
        if item["excluded"]
    ]
    return {
        "recommended_golden_set": golden,
        "recommended_challenge_set": challenge,
        "security_exclusions": excluded,
        "owner_gate": "STOP",
        "copy_authorized": False,
        "goldenize_authorized": False,
        "note": "Default execution stops at OWNER_GATE. No copies or moves.",
    }


def _inaccessible_covers_project(project_path: str, inaccessible_paths: set[str]) -> bool:
    rel = canonicalize_report_path(project_path)
    covered = {
        canonicalize_report_path(item)
        for item in inaccessible_paths
        if canonicalize_report_path(item)
    }
    if not covered:
        return False
    if rel in {"", "."}:
        return True
    return any(exc == rel or exc.startswith(f"{rel}/") for exc in covered)


def estimate_disk(
    root: Path, exclusions: list[dict[str, Any]] | None = None
) -> dict[str, int]:
    total = 0
    files = 0

    def onerror(err: OSError) -> None:
        raw = getattr(err, "filename", None)
        path = Path(raw) if raw else root
        if exclusions is not None:
            _record_inaccessible(exclusions, path, root)

    for dirpath, dirnames, filenames in os.walk(
        root, followlinks=False, onerror=onerror
    ):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            st = _safe_lstat(path)
            if st is None:
                if exclusions is not None:
                    _record_inaccessible(exclusions, path, root)
                continue
            if _is_reparse(st):
                continue
            meta = _safe_stat(path)
            if meta is None:
                if exclusions is not None:
                    _record_inaccessible(exclusions, path, root)
                continue
            total += meta.st_size
            files += 1
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
    for item in projects:
        item["path"] = canonicalize_report_path(str(item.get("path") or ""))
        if item.get("duplicate_of"):
            item["duplicate_of"] = canonicalize_report_path(str(item["duplicate_of"]))
    disk = estimate_disk(root, walked["exclusions"])
    generated = [
        canonicalize_report_path(item) for item in walked["generated_directories"]
    ]
    for item in walked["exclusions"]:
        item["path"] = canonicalize_report_path(str(item.get("path") or ""))
    inaccessible_paths = {
        canonicalize_report_path(str(item.get("path") or ""))
        for item in walked["exclusions"]
        if item.get("reason") == INACCESSIBLE_REASON
    }
    for item in projects:
        if _inaccessible_covers_project(str(item.get("path") or ""), inaccessible_paths):
            item["inspection_complete"] = False
    qualifications = [qualify(item) for item in projects]
    rec = recommend(qualifications)
    inaccessible = [
        item
        for item in walked["exclusions"]
        if item.get("reason") == INACCESSIBLE_REASON
    ]
    golden_set = {str(item) for item in rec["recommended_golden_set"]}
    inaccessible_is_golden = any(
        path in golden_set
        or any(
            golden == path
            or golden.startswith(f"{path}/")
            or path.startswith(f"{golden}/")
            for golden in golden_set
        )
        for path in inaccessible_paths
        if path
    )
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
        "generated_directories": generated,
        "disk_estimate": disk,
        "recommendation": rec,
        "discovery": {
            "complete": not inaccessible,
            "partial": bool(inaccessible),
            "inaccessible_count": len(inaccessible),
            "inaccessible_is_safe": False,
            "inaccessible_is_golden": inaccessible_is_golden,
            "skipped_is_scanned": False,
            "partial_discovery_is_complete_discovery": False,
        },
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
