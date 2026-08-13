"""AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001 — bounded knowledge estate discovery.

D-049: find probable projects and knowledge under an *explicit authorized root*.

Invariant:
    DISCOVER != INGEST != TRUST != AUTHORITY

This module never ingests, never mutates Layer B, never executes discovered
project code, never scans home / filesystem root, and never follows symlink /
junction escapes outside the authorized root.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from project_atlas.connect import root_identity_fingerprint
from project_atlas.source_identity import validate_project_uuid

PACKAGE_ID = "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001"
DIRECTIVE_FAMILY = "D-PROJECT-ATLAS-KNOWLEDGE-ESTATE-DISCOVERY-049"
REPORT_SCHEMA = "estate-discovery-report"
REPORT_RELATIVE = Path("generated") / "ops" / "estate-discovery-report.json"
INCREMENTAL_CACHE_RELATIVE = Path("generated") / "ops" / "estate-discovery-cache.json"

MatchState = Literal[
    "EXACT",
    "STRONG_EVIDENCE",
    "LIKELY",
    "AMBIGUOUS",
    "UNMATCHED",
    "CONFLICTING",
]

LifecycleState = Literal[
    "FOUND",
    "CANDIDATE",
    "CLASSIFIED",
    "PROJECT_MATCHED",
    "POLICY_REVIEW",
    "CONNECTED",
    "INGESTED",
    "VERIFIED",
]

Category = Literal[
    "DISCOVERED_PROJECTS",
    "NEW_KNOWLEDGE",
    "AMBIGUOUS_MATCHES",
    "UNMATCHED_KNOWLEDGE",
    "IGNORED",
    "CONNECTED",
]

IGNORE_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".tmp",
        ".atlas-vault",
        ".atlas",
        "vendor",
        "generated",
        "coverage",
        ".tox",
        ".eggs",
        ".cache",
        "target",
        "out",
    }
)

PROJECT_MARKER_FILES = (".atlas-project.yaml", ".atlas-project.yml")
PROJECT_MARKER_NESTED = (Path(".atlas") / "project.yaml", Path(".atlas") / "project.yml")

PROJECT_MANIFEST_FILES = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "composer.json",
        "gemfile",
        "mix.exs",
    }
)

PROJECT_DOC_NAMES = frozenset(
    {
        "readme",
        "readme.md",
        "readme.txt",
        "agents.md",
        "claude.md",
        "architecture.md",
        "architecture",
    }
)

PROJECT_DIR_SIGNALS = frozenset({".github", ".cursor", "src", "docs", "adr"})
KNOWLEDGE_DIR_SIGNALS = frozenset(
    {
        "notes",
        "research",
        "architecture",
        "decisions",
        "meetings",
        "specs",
        "roadmaps",
        "docs",
        "adr",
    }
)

DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_PROJECT_CANDIDATES = 500
DEFAULT_MAX_KNOWLEDGE_CANDIDATES = 500


class EstateDiscoveryError(ValueError):
    """Fail-closed estate discovery error."""


@dataclass(frozen=True, slots=True)
class MatchEvidence:
    """One explainable evidence row (no fake confidence percentage)."""

    kind: str
    detail: str
    weight: str  # exact | strong | likely | weak | conflict

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail, "weight": self.weight}


@dataclass
class DiscoveryCandidate:
    """A discovered project or knowledge candidate (pre-ingest)."""

    candidate_id: str
    kind: Literal["project", "knowledge", "obsidian_vault"]
    path: str
    display_name: str
    lifecycle: LifecycleState
    match_state: MatchState
    category: Category
    why_matched: list[str] = field(default_factory=list)
    match_evidence: list[dict[str, str]] = field(default_factory=list)
    conflicting_evidence: list[dict[str, str]] = field(default_factory=list)
    required_review: bool = False
    signals: list[str] = field(default_factory=list)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    matched_project_id: str | None = None
    matched_project_uuid: str | None = None
    ignored_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "path": self.path,
            "display_name": self.display_name,
            "lifecycle": self.lifecycle,
            "match_state": self.match_state,
            "category": self.category,
            "why_matched": list(self.why_matched),
            "match_evidence": list(self.match_evidence),
            "conflicting_evidence": list(self.conflicting_evidence),
            "required_review": self.required_review,
            "signals": sorted(self.signals),
            "fingerprint": dict(self.fingerprint),
            "matched_project_id": self.matched_project_id,
            "matched_project_uuid": self.matched_project_uuid,
            "ignored_reason": self.ignored_reason,
        }


@dataclass(frozen=True, slots=True)
class VaultProjectIdentity:
    project_id: str
    project_uuid: str | None
    bind_root: str | None = None
    package_name: str | None = None
    git_remote: str | None = None


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def refuse_dangerous_authorized_root(path: Path) -> Path:
    """Resolve and refuse filesystem root / home as authorized discovery roots."""
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.exists():
        raise EstateDiscoveryError(f"authorized root does not exist: {resolved}")
    if not resolved.is_dir():
        raise EstateDiscoveryError(f"authorized root is not a directory: {resolved}")
    if resolved.parent == resolved:
        raise EstateDiscoveryError(
            f"refusing filesystem root as authorized discovery root: {resolved}"
        )
    home = Path.home().resolve()
    if resolved == home:
        raise EstateDiscoveryError(
            f"refusing home directory as authorized discovery root: {resolved}"
        )
    return resolved


def _under_authorized(path: Path, authorized: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(authorized)
        return True
    except ValueError:
        return False


def _is_symlink_escape(entry: Path, authorized: Path) -> bool:
    if not entry.is_symlink():
        return False
    try:
        target = entry.resolve(strict=False)
    except OSError:
        return True
    return not _under_authorized(target, authorized)


def _candidate_id(kind: str, path: Path) -> str:
    digest = hashlib.sha256(
        f"{kind}:{path.resolve(strict=False).as_posix().casefold()}".encode()
    ).hexdigest()[:16]
    return f"{kind}-{digest}"


def _safe_read_text(path: Path, *, limit: int = 64_000) -> str | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _read_atlas_marker(directory: Path) -> dict[str, Any] | None:
    for name in PROJECT_MARKER_FILES:
        marker = directory / name
        if marker.is_file() and not marker.is_symlink():
            text = _safe_read_text(marker)
            if text is None:
                return {"_unreadable": True, "_marker": name}
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError:
                return {"_invalid": True, "_marker": name}
            return data if isinstance(data, dict) else {"_invalid": True, "_marker": name}
    for rel in PROJECT_MARKER_NESTED:
        marker = directory / rel
        if marker.is_file() and not marker.is_symlink():
            text = _safe_read_text(marker)
            if text is None:
                return {"_unreadable": True, "_marker": rel.as_posix()}
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError:
                return {"_invalid": True, "_marker": rel.as_posix()}
            return (
                data if isinstance(data, dict) else {"_invalid": True, "_marker": rel.as_posix()}
            )
    return None


def _marker_identity(marker: dict[str, Any]) -> tuple[str | None, str | None]:
    if marker.get("_invalid") or marker.get("_unreadable"):
        return None, None
    project = marker.get("project")
    project_id: str | None = None
    if isinstance(project, dict):
        raw_id = project.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            project_id = raw_id.strip()
    raw_uuid = marker.get("project_uuid")
    project_uuid: str | None = None
    if isinstance(raw_uuid, str) and raw_uuid.strip():
        try:
            project_uuid = validate_project_uuid(raw_uuid.strip())
        except ValueError:
            project_uuid = None
    return project_id, project_uuid


def _git_remote_url(directory: Path) -> str | None:
    """Read git remote without executing git (config parse only)."""
    config = directory / ".git" / "config"
    if not config.is_file() or config.is_symlink():
        return None
    text = _safe_read_text(config)
    if text is None:
        return None
    origin_url: str | None = None
    any_url: str | None = None
    section: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip().lower() != "url":
            continue
        url = value.strip()
        if not url:
            continue
        if section == 'remote "origin"':
            origin_url = url
        elif section and section.startswith("remote ") and any_url is None:
            any_url = url
    return origin_url or any_url


def _package_name(directory: Path) -> str | None:
    pkg = directory / "package.json"
    if pkg.is_file() and not pkg.is_symlink():
        text = _safe_read_text(pkg)
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                name = data.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    pyproject = directory / "pyproject.toml"
    if pyproject.is_file() and not pyproject.is_symlink():
        text = _safe_read_text(pyproject)
        if text:
            match = re.search(r"(?m)^\s*name\s*=\s*[\"']([^\"']+)[\"']", text)
            if match:
                return match.group(1).strip()
    return None


def _dir_entries(directory: Path) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    lower_files: set[str] = set()
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                names.add(entry.name)
                if entry.is_file(follow_symlinks=False):
                    lower_files.add(entry.name.casefold())
    except OSError:
        return set(), set()
    return names, lower_files


def _score_project_signals(
    directory: Path, names: set[str], lower_files: set[str]
) -> list[str]:
    signals: list[str] = []
    if ".git" in names:
        git_path = directory / ".git"
        if git_path.exists() and not (
            git_path.is_symlink() and _is_symlink_escape(git_path, directory)
        ):
            signals.append("git_dir")
    if any((directory / m).is_file() for m in PROJECT_MARKER_FILES) or any(
        (directory / m).is_file() for m in PROJECT_MARKER_NESTED
    ):
        signals.append("atlas_project_marker")
    for manifest in PROJECT_MANIFEST_FILES:
        if manifest in lower_files:
            signals.append(f"manifest:{manifest}")
    for doc in PROJECT_DOC_NAMES:
        if doc in lower_files:
            signals.append(f"doc:{doc}")
    folded = {n.casefold(): n for n in names}
    for dirname in PROJECT_DIR_SIGNALS:
        real = folded.get(dirname)
        if real is None:
            continue
        child = directory / real
        if child.is_dir() and not child.is_symlink():
            signals.append(f"dir:{dirname}")
    if any(n.casefold().startswith("docker-compose") for n in names):
        signals.append("docker_compose")
    return signals


def _is_project_candidate(signals: Sequence[str]) -> bool:
    if not signals:
        return False
    if "git_dir" in signals or "atlas_project_marker" in signals:
        return True
    manifests = [s for s in signals if s.startswith("manifest:")]
    docs = [s for s in signals if s.startswith("doc:")]
    dirs = [s for s in signals if s.startswith("dir:")]
    if manifests and (docs or dirs or "docker_compose" in signals):
        return True
    return bool(manifests and "dir:src" in signals)


def _is_obsidian_vault(directory: Path, names: set[str]) -> bool:
    if ".obsidian" not in names:
        return False
    obsidian = directory / ".obsidian"
    return obsidian.is_dir() and not obsidian.is_symlink()


def _knowledge_signals(
    directory: Path, names: set[str], lower_files: set[str]
) -> list[str]:
    signals: list[str] = []
    if _is_obsidian_vault(directory, names):
        signals.append("obsidian_vault")
    folded = {n.casefold(): n for n in names}
    for dirname in KNOWLEDGE_DIR_SIGNALS:
        real = folded.get(dirname)
        if real is None:
            continue
        child = directory / real
        if child.is_dir() and not child.is_symlink():
            signals.append(f"knowledge_dir:{dirname}")
    md_count = sum(1 for f in lower_files if f.endswith(".md"))
    if md_count >= 3:
        signals.append(f"markdown_cluster:{md_count}")
    return signals


def _build_fingerprint(directory: Path, signals: Sequence[str]) -> dict[str, Any]:
    marker = _read_atlas_marker(directory)
    project_id, project_uuid = (None, None)
    if marker is not None:
        project_id, project_uuid = _marker_identity(marker)
    remote = _git_remote_url(directory) if "git_dir" in signals else None
    package = _package_name(directory)
    return {
        "canonical_path": directory.resolve(strict=False).as_posix(),
        "path_fingerprint": root_identity_fingerprint(directory),
        "atlas_project_id": project_id,
        "atlas_project_uuid": project_uuid,
        "git_remote": remote,
        "package_name": package,
        "directory_name": directory.name,
        "marker_invalid": bool(marker and marker.get("_invalid")),
        "marker_unreadable": bool(marker and marker.get("_unreadable")),
    }


def load_vault_project_identities(vault: Path | None) -> list[VaultProjectIdentity]:
    """Read existing Atlas project identities for matching (read-only)."""
    if vault is None:
        return []
    projects_root = vault / "projects"
    if not projects_root.is_dir():
        return []
    by_id: dict[str, VaultProjectIdentity] = {}
    for entry in sorted(projects_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        project_uuid: str | None = None
        for rel in (
            Path("project.md"),
            Path(".atlas") / "project-identity.json",
            Path("identity.json"),
        ):
            path = entry / rel
            if not path.is_file():
                continue
            text = _safe_read_text(path)
            if not text:
                continue
            if path.suffix == ".json":
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    for key in ("project_uuid", "uuid"):
                        raw = data.get(key)
                        if isinstance(raw, str):
                            try:
                                project_uuid = validate_project_uuid(raw.strip())
                                break
                            except ValueError:
                                continue
            else:
                match = re.search(
                    r"(?m)^project_uuid:\s*[\"']?([0-9a-fA-F-]{36})[\"']?",
                    text,
                )
                if match:
                    try:
                        project_uuid = validate_project_uuid(match.group(1))
                    except ValueError:
                        project_uuid = None
            if project_uuid:
                break
        by_id[entry.name] = VaultProjectIdentity(
            project_id=entry.name,
            project_uuid=project_uuid,
        )

    alloc = vault / "generated" / "ops" / "project-uuid-allocations.json"
    if alloc.is_file():
        text = _safe_read_text(alloc)
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                mapping = data.get("allocations") or data.get("owners") or data
                if isinstance(mapping, dict):
                    for uuid_key, owner in mapping.items():
                        if not isinstance(uuid_key, str):
                            continue
                        try:
                            uuid_val = validate_project_uuid(uuid_key.strip())
                        except ValueError:
                            continue
                        owner_id = (
                            owner.get("project_id")
                            if isinstance(owner, dict)
                            else owner
                            if isinstance(owner, str)
                            else None
                        )
                        if not isinstance(owner_id, str):
                            continue
                        existing = by_id.get(owner_id)
                        if existing is None:
                            by_id[owner_id] = VaultProjectIdentity(
                                project_id=owner_id,
                                project_uuid=uuid_val,
                            )
                        elif existing.project_uuid is None:
                            by_id[owner_id] = VaultProjectIdentity(
                                project_id=owner_id,
                                project_uuid=uuid_val,
                                bind_root=existing.bind_root,
                                package_name=existing.package_name,
                                git_remote=existing.git_remote,
                            )
    return [by_id[k] for k in sorted(by_id)]


def _normalize_remote(url: str) -> str:
    value = url.strip().casefold()
    value = re.sub(r"^git\+", "", value)
    value = re.sub(r"\.git$", "", value)
    value = value.removeprefix("ssh://")
    return value


def match_fingerprint(
    fingerprint: dict[str, Any],
    vault_projects: Sequence[VaultProjectIdentity],
) -> tuple[
    MatchState,
    list[MatchEvidence],
    list[MatchEvidence],
    str | None,
    str | None,
]:
    """Explainable project matching — no confidence percentage theatre."""
    if not vault_projects:
        return "UNMATCHED", [], [], None, None

    evidence: list[MatchEvidence] = []
    conflicts: list[MatchEvidence] = []
    atlas_id = fingerprint.get("atlas_project_id")
    atlas_uuid = fingerprint.get("atlas_project_uuid")
    remote = fingerprint.get("git_remote")
    package = fingerprint.get("package_name")
    dirname = fingerprint.get("directory_name")

    uuid_hits = [
        vp
        for vp in vault_projects
        if atlas_uuid and vp.project_uuid and atlas_uuid == vp.project_uuid
    ]
    id_hits = [vp for vp in vault_projects if atlas_id and atlas_id == vp.project_id]

    for hit in uuid_hits:
        evidence.append(
            MatchEvidence(
                "atlas_project_uuid",
                f"marker uuid matches vault project {hit.project_id}",
                "exact",
            )
        )
    for hit in id_hits:
        evidence.append(
            MatchEvidence(
                "atlas_project_id",
                f"marker project.id equals vault project {hit.project_id}",
                "exact",
            )
        )

    # Governed identity precedence: conflicting uuid ownership vs marker id.
    if atlas_uuid and atlas_id and uuid_hits:
        for hit in uuid_hits:
            if hit.project_id != atlas_id:
                conflicts.append(
                    MatchEvidence(
                        "uuid_owner_mismatch",
                        f"uuid owned by {hit.project_id} but marker id is {atlas_id}",
                        "conflict",
                    )
                )
    if len({h.project_id for h in uuid_hits}) > 1:
        conflicts.append(
            MatchEvidence(
                "uuid_multi_owner",
                "same uuid matched multiple vault project ids",
                "conflict",
            )
        )

    if conflicts:
        uuid_out = atlas_uuid if isinstance(atlas_uuid, str) else None
        return "CONFLICTING", evidence, conflicts, None, uuid_out

    if len(uuid_hits) == 1:
        hit = uuid_hits[0]
        return "EXACT", evidence, [], hit.project_id, hit.project_uuid
    if len(id_hits) == 1 and not uuid_hits:
        hit = id_hits[0]
        return "EXACT", evidence, [], hit.project_id, hit.project_uuid
    if len(id_hits) > 1:
        return "AMBIGUOUS", evidence, conflicts, None, None

    strong_hits: list[VaultProjectIdentity] = []
    likely_hits: list[VaultProjectIdentity] = []
    if isinstance(remote, str) and remote:
        norm = _normalize_remote(remote)
        for vp in vault_projects:
            if vp.git_remote and _normalize_remote(vp.git_remote) == norm:
                strong_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "git_remote",
                        f"git remote matches vault project {vp.project_id}",
                        "strong",
                    )
                )
    if isinstance(package, str) and package:
        for vp in vault_projects:
            if vp.package_name and vp.package_name.casefold() == package.casefold():
                strong_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "package_name",
                        f"package name matches vault project {vp.project_id}",
                        "strong",
                    )
                )
            elif vp.project_id.casefold() == package.casefold().replace("_", "-"):
                likely_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "package_name_as_id",
                        f"package name aligns with vault project id {vp.project_id}",
                        "likely",
                    )
                )
    if isinstance(dirname, str) and dirname:
        for vp in vault_projects:
            if vp.project_id.casefold() == dirname.casefold():
                likely_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "directory_name",
                        f"directory name equals vault project id {vp.project_id}",
                        "likely",
                    )
                )

    unique_strong = {h.project_id: h for h in strong_hits}
    unique_likely = {h.project_id: h for h in likely_hits}

    if len(unique_strong) == 1:
        hit = next(iter(unique_strong.values()))
        return "STRONG_EVIDENCE", evidence, [], hit.project_id, hit.project_uuid
    if len(unique_strong) > 1:
        return "AMBIGUOUS", evidence, [], None, None
    if len(unique_likely) == 1:
        hit = next(iter(unique_likely.values()))
        return "LIKELY", evidence, [], hit.project_id, hit.project_uuid
    if len(unique_likely) > 1:
        return "AMBIGUOUS", evidence, [], None, None
    return "UNMATCHED", evidence, [], None, None


def _why_from_evidence(evidence: Sequence[MatchEvidence], match_state: MatchState) -> list[str]:
    if not evidence:
        if match_state == "UNMATCHED":
            return ["no vault project identity matched this candidate"]
        return [f"classified as {match_state}"]
    return [f"{row.kind}: {row.detail}" for row in evidence]


def _category_for(
    *,
    kind: str,
    match_state: MatchState,
    connected: bool,
) -> Category:
    if match_state == "EXACT":
        return "CONNECTED" if connected else "DISCOVERED_PROJECTS"
    if match_state in {"AMBIGUOUS", "CONFLICTING"}:
        return "AMBIGUOUS_MATCHES"
    if kind != "project":
        if match_state == "UNMATCHED":
            return "UNMATCHED_KNOWLEDGE"
        return "NEW_KNOWLEDGE"
    if match_state == "UNMATCHED":
        return "DISCOVERED_PROJECTS"
    return "DISCOVERED_PROJECTS"


def _lifecycle_for(match_state: MatchState, *, connected: bool) -> LifecycleState:
    if connected:
        return "CONNECTED"
    if match_state == "CONFLICTING":
        return "POLICY_REVIEW"
    if match_state in {"EXACT", "STRONG_EVIDENCE", "LIKELY"}:
        return "PROJECT_MATCHED"
    if match_state == "AMBIGUOUS":
        return "POLICY_REVIEW"
    if match_state == "UNMATCHED":
        return "CLASSIFIED"
    return "CANDIDATE"


def discover_estate(
    authorized_root: Path,
    *,
    vault: Path | None = None,
    include_projects: bool = True,
    include_knowledge: bool = True,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_project_candidates: int = DEFAULT_MAX_PROJECT_CANDIDATES,
    max_knowledge_candidates: int = DEFAULT_MAX_KNOWLEDGE_CANDIDATES,
    prior_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bounded filesystem discovery under one authorized root (Lanes A-E, H).

    Does **not** ingest. Symlink escapes are recorded as IGNORED.
    """
    root = refuse_dangerous_authorized_root(authorized_root)
    vault_projects = load_vault_project_identities(vault)
    connected_ids = {vp.project_id for vp in vault_projects}

    projects: list[DiscoveryCandidate] = []
    knowledge: list[DiscoveryCandidate] = []
    ignored: list[dict[str, str]] = []
    unsafe_escapes = 0

    # Lane H: optional prior cache of path → mtime/size for skip hints (correctness first).
    cache_entries: dict[str, Any] = {}
    if isinstance(prior_cache, dict):
        raw_entries = prior_cache.get("entries")
        if isinstance(raw_entries, dict):
            cache_entries = raw_entries

    stack: list[tuple[Path, int]] = [(root, 0)]
    seen_dirs: set[str] = set()

    while stack:
        current, depth = stack.pop()
        try:
            current_resolved = current.resolve(strict=False)
        except OSError:
            ignored.append(
                {
                    "path": current.as_posix(),
                    "reason": "unresolvable_path",
                }
            )
            continue
        key = current_resolved.as_posix().casefold()
        if key in seen_dirs:
            continue
        if not _under_authorized(current_resolved, root):
            unsafe_escapes += 1
            ignored.append(
                {
                    "path": current.as_posix(),
                    "reason": "symlink_or_reparse_escape",
                }
            )
            continue
        seen_dirs.add(key)

        names, lower_files = _dir_entries(current)
        project_signals = _score_project_signals(current, names, lower_files)
        know_signals = _knowledge_signals(current, names, lower_files)

        # Incremental foundation: record coarse fingerprint for later re-scan.
        try:
            st = current.stat()
            cache_key = current_resolved.as_posix()
            cache_entries[cache_key] = {
                "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                "signals": sorted(set(project_signals) | set(know_signals)),
            }
        except OSError:
            pass

        if (
            include_projects
            and _is_project_candidate(project_signals)
            and len(projects) < max_project_candidates
        ):
            fingerprint = _build_fingerprint(current, project_signals)
            match_state, evidence, conflicts, matched_id, matched_uuid = (
                match_fingerprint(fingerprint, vault_projects)
            )
            connected = bool(
                matched_id
                and matched_id in connected_ids
                and match_state == "EXACT"
            )
            required_review = match_state in {"AMBIGUOUS", "CONFLICTING"} or bool(
                fingerprint.get("marker_invalid")
                or fingerprint.get("marker_unreadable")
            )
            projects.append(
                DiscoveryCandidate(
                    candidate_id=_candidate_id("project", current_resolved),
                    kind="project",
                    path=current_resolved.as_posix(),
                    display_name=current.name,
                    lifecycle=_lifecycle_for(match_state, connected=connected),
                    match_state=match_state,
                    category=_category_for(
                        kind="project",
                        match_state=match_state,
                        connected=connected,
                    ),
                    why_matched=_why_from_evidence(evidence, match_state),
                    match_evidence=[e.as_dict() for e in evidence],
                    conflicting_evidence=[c.as_dict() for c in conflicts],
                    required_review=required_review,
                    signals=list(project_signals),
                    fingerprint=fingerprint,
                    matched_project_id=matched_id,
                    matched_project_uuid=matched_uuid,
                )
            )

        if include_knowledge:
            is_obsidian = "obsidian_vault" in know_signals
            # Avoid double-counting pure project roots as knowledge unless Obsidian
            # or knowledge-only clusters without project manifests.
            knowledge_only = bool(know_signals) and (
                is_obsidian
                or not _is_project_candidate(project_signals)
                or any(s.startswith("knowledge_dir:") for s in know_signals)
            )
            if knowledge_only and len(knowledge) < max_knowledge_candidates:
                kind: Literal["knowledge", "obsidian_vault"] = (
                    "obsidian_vault" if is_obsidian else "knowledge"
                )
                knowledge_fp = {
                    "canonical_path": current_resolved.as_posix(),
                    "path_fingerprint": root_identity_fingerprint(current),
                    "directory_name": current.name,
                    "obsidian": is_obsidian,
                }
                # Knowledge does not silently merge into projects.
                knowledge_match: MatchState = "UNMATCHED"
                knowledge.append(
                    DiscoveryCandidate(
                        candidate_id=_candidate_id(kind, current_resolved),
                        kind=kind,
                        path=current_resolved.as_posix(),
                        display_name=current.name,
                        lifecycle="CLASSIFIED",
                        match_state=knowledge_match,
                        category=(
                            "NEW_KNOWLEDGE" if is_obsidian else "UNMATCHED_KNOWLEDGE"
                        ),
                        why_matched=[
                            (
                                "obsidian vault detected (.obsidian); "
                                "discovery only - not ingested"
                            )
                            if is_obsidian
                            else "knowledge signals present; not auto-trusted"
                        ],
                        match_evidence=[
                            {
                                "kind": s,
                                "detail": "knowledge signal",
                                "weight": "likely" if is_obsidian else "weak",
                            }
                            for s in know_signals
                        ],
                        conflicting_evidence=[],
                        required_review=is_obsidian,
                        signals=list(know_signals),
                        fingerprint=knowledge_fp,
                    )
                )

        if depth >= max_depth:
            continue

        folded_ignore = {n.casefold() for n in IGNORE_DIR_NAMES}
        for name in sorted(names, reverse=True):
            if name.casefold() in folded_ignore:
                ignored.append(
                    {
                        "path": (current / name).as_posix(),
                        "reason": f"ignore_policy:{name.casefold()}",
                    }
                )
                continue
            child = current / name
            if child.is_symlink():
                if _is_symlink_escape(child, root):
                    unsafe_escapes += 1
                    ignored.append(
                        {
                            "path": child.as_posix(),
                            "reason": "symlink_or_reparse_escape",
                        }
                    )
                    continue
                # Symlink stays inside root — still do not descend (junction safety).
                ignored.append(
                    {
                        "path": child.as_posix(),
                        "reason": "symlink_not_descended",
                    }
                )
                continue
            if not child.is_dir():
                continue
            stack.append((child, depth + 1))

    # Deterministic ordering
    projects.sort(key=lambda c: (c.path.casefold(), c.candidate_id))
    knowledge.sort(key=lambda c: (c.path.casefold(), c.candidate_id))
    ignored.sort(key=lambda row: (row.get("path", "").casefold(), row.get("reason", "")))

    categories: dict[str, list[dict[str, Any]]] = {
        "DISCOVERED_PROJECTS": [],
        "NEW_KNOWLEDGE": [],
        "AMBIGUOUS_MATCHES": [],
        "UNMATCHED_KNOWLEDGE": [],
        "IGNORED": ignored,
        "CONNECTED": [],
    }
    for cand in projects:
        categories[cand.category].append(cand.to_dict())
    for cand in knowledge:
        categories[cand.category].append(cand.to_dict())

    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": REPORT_SCHEMA,
        "package_id": PACKAGE_ID,
        "directive_family": DIRECTIVE_FAMILY,
        "invariant": "DISCOVER != INGEST != TRUST != AUTHORITY",
        "authorized_root": root.as_posix(),
        "vault": vault.resolve(strict=False).as_posix() if vault is not None else None,
        "generated": {"by": "project-atlas"},
        "security": {
            "symlink_follow": False,
            "code_execution": False,
            "network_discovery": False,
            "whole_disk_scan": False,
            "unsafe_path_escapes_detected": unsafe_escapes,
            "unsafe_path_escapes_allowed": 0,
        },
        "counts": {
            "projects": len(projects),
            "knowledge": len(knowledge),
            "ignored": len(ignored),
            "required_review": sum(
                1 for c in projects + knowledge if c.required_review
            ),
        },
        "categories": categories,
        "candidates": {
            "projects": [c.to_dict() for c in projects],
            "knowledge": [c.to_dict() for c in knowledge],
        },
        "incremental_foundation": {
            "cache_schema": "estate-discovery-cache-v1",
            "entries_recorded": len(cache_entries),
            "note": (
                "Coarse path fingerprints only; re-scan may skip unchanged dirs "
                "in a later wave without weakening truth."
            ),
        },
        "_cache_entries": cache_entries,
    }
    return report


def write_discovery_report(report: dict[str, Any], output: Path) -> Path:
    """Atomically write the discovery report (JSON, sort_keys)."""
    payload = {k: v for k, v in report.items() if not k.startswith("_")}
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(output, content)
    return output


def write_discovery_cache(report: dict[str, Any], output: Path) -> Path:
    """Persist Lane H incremental cache sidecar (not authority)."""
    entries = report.get("_cache_entries")
    if not isinstance(entries, dict):
        entries = {}
    payload = {
        "schema_version": 1,
        "schema": "estate-discovery-cache-v1",
        "package_id": PACKAGE_ID,
        "authorized_root": report.get("authorized_root"),
        "entries": entries,
        "generated": {"by": "project-atlas"},
    }
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(output, content)
    return output


def load_discovery_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    text = _safe_read_text(path, limit=8_000_000)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def review_candidates(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return candidates that require human review (ambiguity / conflict / impact)."""
    rows: list[dict[str, Any]] = []
    candidates = report.get("candidates")
    if not isinstance(candidates, dict):
        return []
    for bucket in ("projects", "knowledge"):
        items = candidates.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("required_review"):
                rows.append(item)
    rows.sort(key=lambda r: (str(r.get("path", "")).casefold(), str(r.get("candidate_id", ""))))
    return rows


def find_candidate(report: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    candidates = report.get("candidates")
    if not isinstance(candidates, dict):
        return None
    for bucket in ("projects", "knowledge"):
        items = candidates.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
                return item
    return None


def connect_discovered_candidate(
    report: dict[str, Any],
    candidate_id: str,
    *,
    vault: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Connect an accepted *project* candidate via existing connect_project.

    Knowledge / Obsidian candidates never auto-ingest here — fail closed to
    preserve DISCOVER != INGEST for knowledge surfaces.
    """
    from project_atlas.connect import ConnectError, connect_project

    cand = find_candidate(report, candidate_id)
    if cand is None:
        raise EstateDiscoveryError(f"unknown candidate_id: {candidate_id}")
    kind = cand.get("kind")
    if kind != "project":
        raise EstateDiscoveryError(
            f"refusing to connect non-project candidate ({kind}); "
            "knowledge/obsidian require explicit policy acceptance (DISCOVER != INGEST)"
        )
    if cand.get("match_state") == "CONFLICTING":
        raise EstateDiscoveryError(
            "refusing to connect CONFLICTING candidate; resolve identity review first "
            "(no silent project unification)"
        )
    path_raw = cand.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise EstateDiscoveryError("candidate missing path")
    source = Path(path_raw)
    try:
        result = connect_project(source, vault=vault, dry_run=dry_run)
    except ConnectError as exc:
        raise EstateDiscoveryError(str(exc)) from exc
    return {
        "package_id": PACKAGE_ID,
        "candidate_id": candidate_id,
        "connect": result if isinstance(result, dict) else {"result": str(result)},
        "invariant": "DISCOVER != INGEST != TRUST != AUTHORITY",
        "note": "connect invoked explicitly after discovery; discovery alone never ingests",
    }


def format_discovery_human(report: dict[str, Any]) -> str:
    """Stranger-friendly summary: what should the user care about?"""
    lines: list[str] = []
    root = report.get("authorized_root", "?")
    lines.append(f"Atlas knowledge estate discovery under: {root}")
    lines.append("DISCOVER != INGEST != TRUST != AUTHORITY")
    lines.append("")
    counts_raw = report.get("counts")
    counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
    lines.append(
        f"Found {counts.get('projects', 0)} project candidate(s), "
        f"{counts.get('knowledge', 0)} knowledge candidate(s), "
        f"{counts.get('required_review', 0)} needing review."
    )
    categories_raw = report.get("categories")
    categories: dict[str, Any] = (
        categories_raw if isinstance(categories_raw, dict) else {}
    )
    order = (
        "DISCOVERED_PROJECTS",
        "CONNECTED",
        "AMBIGUOUS_MATCHES",
        "NEW_KNOWLEDGE",
        "UNMATCHED_KNOWLEDGE",
    )
    for cat in order:
        rows = categories.get(cat)
        if not isinstance(rows, list) or not rows:
            continue
        lines.append("")
        lines.append(f"{cat} ({len(rows)})")
        for row in rows[:50]:
            if not isinstance(row, dict):
                continue
            why = row.get("why_matched")
            why0 = why[0] if isinstance(why, list) and why else ""
            lines.append(
                f"  - {row.get('display_name')} [{row.get('match_state')}] "
                f"{row.get('path')}"
            )
            if why0:
                lines.append(f"      why: {why0}")
            if row.get("required_review"):
                lines.append("      review: REQUIRED")
    ignored = categories.get("IGNORED")
    if isinstance(ignored, list) and ignored:
        lines.append("")
        lines.append(
            f"IGNORED ({len(ignored)}) - policy / safety (not listed in full)"
        )
    lines.append("")
    lines.append(
        "Next: atlas discover review   OR   "
        "atlas discover connect --candidate <id>"
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DIRECTIVE_FAMILY",
    "INCREMENTAL_CACHE_RELATIVE",
    "PACKAGE_ID",
    "REPORT_RELATIVE",
    "DiscoveryCandidate",
    "EstateDiscoveryError",
    "VaultProjectIdentity",
    "connect_discovered_candidate",
    "discover_estate",
    "find_candidate",
    "format_discovery_human",
    "load_discovery_cache",
    "load_vault_project_identities",
    "match_fingerprint",
    "refuse_dangerous_authorized_root",
    "review_candidates",
    "write_discovery_cache",
    "write_discovery_report",
]
