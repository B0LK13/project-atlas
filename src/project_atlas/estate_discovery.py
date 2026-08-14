"""AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001 — bounded knowledge estate discovery.

D-049 / D-063: find probable projects and knowledge under an explicit authorized
root. Discovery sits ABOVE the accepted Coder Alpha identity layer and must
never weaken:

    one project_uuid → one durable project identity
    DISCOVER != INGEST != TRUST != AUTHORITY
    discovery match != proof of ownership
    heuristic similarity != identity

CONNECTED requires durable bind / source-root ownership evidence — never
merely ``project.id`` presence in ``vault/projects/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from project_atlas.connect import (
    BIND_RELATIVE,
    MANIFEST_RELATIVE,
    root_identity_fingerprint,
)
from project_atlas.source_identity import (
    load_allocation_project_uuids,
    load_allocation_uuid_owners,
    validate_project_uuid,
)

PACKAGE_ID = "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001"
DIRECTIVE_FAMILY = "D-PROJECT-ATLAS-KNOWLEDGE-ESTATE-DISCOVERY-049"
REPORT_SCHEMA = "estate-discovery-report"
REPORT_RELATIVE = Path("generated") / "ops" / "estate-discovery-report.json"
INCREMENTAL_CACHE_RELATIVE = Path("generated") / "ops" / "estate-discovery-cache.json"
DURABLE_SOURCE_MANIFEST = Path("sources") / "manifests" / "source-manifest.json"
CONNECT_RECEIPT_RELATIVE = Path("generated") / "ops" / "connect-receipt.json"

# Windows FILE_ATTRIBUTE_REPARSE_POINT
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

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

KnowledgeRelation = Literal[
    "KNOWLEDGE_DISCOVERED",
    "KNOWLEDGE_PROJECT_MATCHED",
    "KNOWLEDGE_AMBIGUOUS",
    "KNOWLEDGE_UNMATCHED",
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
        "cache",
        "target",
        "out",
    }
)

PROJECT_MARKER_FILES = (".atlas-project.yaml", ".atlas-project.yml")
PROJECT_MARKER_NESTED = (
    Path(".atlas") / "project.yaml",
    Path(".atlas") / "project.yml",
)
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
    weight: str  # exact | strong | likely | weak | conflict | invalid

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
    why_connected: list[str] = field(default_factory=list)
    match_evidence: list[dict[str, str]] = field(default_factory=list)
    conflicting_evidence: list[dict[str, str]] = field(default_factory=list)
    required_review: bool = False
    required_action: str | None = None
    signals: list[str] = field(default_factory=list)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    matched_project_id: str | None = None
    matched_project_uuid: str | None = None
    knowledge_relation: KnowledgeRelation | None = None
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
            "why_connected": list(self.why_connected),
            "match_evidence": list(self.match_evidence),
            "conflicting_evidence": list(self.conflicting_evidence),
            "required_review": self.required_review,
            "required_action": self.required_action,
            "signals": sorted(self.signals),
            "fingerprint": dict(self.fingerprint),
            "matched_project_id": self.matched_project_id,
            "matched_project_uuid": self.matched_project_uuid,
            "knowledge_relation": self.knowledge_relation,
            "ignored_reason": self.ignored_reason,
        }


@dataclass(frozen=True, slots=True)
class VaultProjectIdentity:
    """Governed vault project identity for discovery matching (read-only)."""

    project_id: str
    project_uuid: str | None
    bind_root: str | None = None
    package_name: str | None = None
    git_remote: str | None = None
    bind_proven: bool = False
    identity_sources: tuple[str, ...] = ()


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


ROOT_MODE_BOUNDED_DIRECTORY = "bounded-directory"
ROOT_MODE_OWNER_AUTHORIZED_VOLUME = "owner-authorized-volume"
ROOT_MODE_BOUNDED_TOKEN = "BOUNDED_DIRECTORY"
ROOT_MODE_VOLUME_TOKEN = "OWNER_AUTHORIZED_VOLUME_ROOT"
VOLUME_KIND_NONE = "NONE"
VOLUME_KIND_NON_SYSTEM_WINDOWS = "NON_SYSTEM_WINDOWS_VOLUME"

_WIN_DRIVE_LETTER = re.compile(r"^([A-Za-z]):")


@dataclass(frozen=True)
class AuthorizedRootDecision:
    """Resolved discovery-root policy (D-078). Never a connect/ingest grant."""

    resolved: Path
    authorized_root_mode: str
    volume_root_authorized: bool
    volume_root_kind: str


def normalize_root_mode(value: str) -> str:
    """Map CLI/API tokens to the two explicit root modes. No --force aliases."""
    key = value.strip().lower().replace("_", "-")
    if key in {ROOT_MODE_BOUNDED_DIRECTORY, "bounded"}:
        return ROOT_MODE_BOUNDED_DIRECTORY
    if key in {ROOT_MODE_OWNER_AUTHORIZED_VOLUME, "owner-authorized-volume-root"}:
        return ROOT_MODE_OWNER_AUTHORIZED_VOLUME
    raise EstateDiscoveryError(f"UNKNOWN_ROOT_MODE: unsupported root mode {value!r}")


def is_filesystem_root(path: Path) -> bool:
    resolved = path.expanduser().resolve(strict=False)
    return resolved.parent == resolved


def is_unc_root(path: Path) -> bool:
    """True for UNC/network roots. Not a local Windows drive volume."""
    raw = os.fspath(path).replace("/", "\\")
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    if raw.startswith("\\\\") and not _WIN_DRIVE_LETTER.match(raw.lstrip("\\")):
        # \\server\share … — not \\?\C:\ (already stripped)
        rest = raw[2:]
        return not rest.startswith("?\\")
    try:
        anchor = path.expanduser().resolve(strict=False).anchor.replace("/", "\\")
    except (OSError, RuntimeError):
        return True
    return bool(
        anchor.startswith("\\\\")
        and not _WIN_DRIVE_LETTER.match(anchor.lstrip("\\"))
    )


def _windows_volume_letter(path: Path) -> str | None:
    for candidate in (os.fspath(path), getattr(path, "anchor", ""), str(path)):
        text = str(candidate).replace("/", "\\")
        if text.startswith("\\\\?\\"):
            text = text[4:]
        match = _WIN_DRIVE_LETTER.match(text)
        if match:
            return match.group(1).upper()
    return None


def is_windows_drive_volume_root(
    path: Path, *, host_os: str | None = None
) -> bool:
    """True for a local Windows drive-volume root (D:\\), never UNC or /."""
    host = host_os if host_os is not None else os.name
    if host != "nt":
        return False
    if is_unc_root(path):
        return False
    resolved = path.expanduser().resolve(strict=False)
    if not is_filesystem_root(resolved):
        return False
    return _windows_volume_letter(resolved) is not None


def windows_system_drive_letter(
    *, environ: dict[str, str] | None = None
) -> str | None:
    env = environ if environ is not None else dict(os.environ)
    for key in ("SystemDrive", "SYSTEMDRIVE"):
        raw = env.get(key)
        if isinstance(raw, str) and raw.strip():
            letter = raw.strip().rstrip(":\\/")
            if len(letter) == 1 and letter.isalpha():
                return letter.upper()
    for key in ("SystemRoot", "SYSTEMROOT", "WINDIR", "windir"):
        raw = env.get(key)
        if isinstance(raw, str) and raw.strip():
            match = _WIN_DRIVE_LETTER.match(raw.replace("/", "\\"))
            if match:
                return match.group(1).upper()
    return None


def is_windows_system_volume_root(
    path: Path,
    *,
    host_os: str | None = None,
    environ: dict[str, str] | None = None,
) -> bool:
    """True when path is the Windows system volume root.

    If the host is Windows and the system drive cannot be determined, fail
    closed (treat as system) so C:\\ cannot be silently classified as a
    dedicated dev volume.
    """
    if not is_windows_drive_volume_root(path, host_os=host_os):
        return False
    letter = _windows_volume_letter(path)
    system = windows_system_drive_letter(environ=environ)
    if system is None:
        host = host_os if host_os is not None else os.name
        return host == "nt"
    return letter == system


def authorize_discovery_root(
    path: Path,
    *,
    root_mode: str = ROOT_MODE_BOUNDED_DIRECTORY,
    host_os: str | None = None,
    environ: dict[str, str] | None = None,
) -> AuthorizedRootDecision:
    """SAFE DEFAULT + explicit Windows non-system volume capability (D-078).

    Volume authorization permits traversal/discovery only. It does not
    connect, ingest, mint identity, or write owner files.
    """
    mode = normalize_root_mode(root_mode)
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.exists():
        raise EstateDiscoveryError(
            f"AUTHORIZED_ROOT_DOES_NOT_EXIST: authorized root does not exist: {resolved}"
        )
    if not resolved.is_dir():
        raise EstateDiscoveryError(
            f"AUTHORIZED_ROOT_NOT_A_DIRECTORY: authorized root is not a directory: {resolved}"
        )
    home = Path.home().resolve()
    if _paths_equal(resolved, home):
        raise EstateDiscoveryError(
            "HOME_DIRECTORY_NOT_ALLOWED: refusing home directory as "
            f"authorized discovery root: {resolved}"
        )

    unc = is_unc_root(path) or is_unc_root(resolved)
    win_vol = is_windows_drive_volume_root(resolved, host_os=host_os)
    sys_vol = is_windows_system_volume_root(
        resolved, host_os=host_os, environ=environ
    )
    fs_root = is_filesystem_root(resolved)

    if mode == ROOT_MODE_OWNER_AUTHORIZED_VOLUME:
        if unc:
            raise EstateDiscoveryError(
                "UNC_VOLUME_ROOT_NOT_ALLOWED: owner-authorized-volume does not "
                f"apply to UNC/network roots: {resolved}"
            )
        if not win_vol:
            if fs_root:
                raise EstateDiscoveryError(
                    "FILESYSTEM_ROOT_NOT_ALLOWED: refusing filesystem root as "
                    f"authorized discovery root: {resolved}"
                )
            raise EstateDiscoveryError(
                "VOLUME_MODE_REQUIRES_WINDOWS_VOLUME_ROOT: "
                "--root-mode owner-authorized-volume requires a Windows "
                f"drive-volume root (for example D:\\); refusing {resolved}"
            )
        if sys_vol:
            raise EstateDiscoveryError(
                "SYSTEM_VOLUME_ROOT_NOT_ALLOWED: refusing Windows system "
                f"volume root: {resolved}"
            )
        return AuthorizedRootDecision(
            resolved=resolved,
            authorized_root_mode=ROOT_MODE_VOLUME_TOKEN,
            volume_root_authorized=True,
            volume_root_kind=VOLUME_KIND_NON_SYSTEM_WINDOWS,
        )

    if fs_root or win_vol:
        raise EstateDiscoveryError(
            "FILESYSTEM_ROOT_NOT_ALLOWED: refusing filesystem root as "
            f"authorized discovery root: {resolved}"
        )
    return AuthorizedRootDecision(
        resolved=resolved,
        authorized_root_mode=ROOT_MODE_BOUNDED_TOKEN,
        volume_root_authorized=False,
        volume_root_kind=VOLUME_KIND_NONE,
    )


def refuse_dangerous_authorized_root(path: Path) -> Path:
    """Default bounded-directory policy (filesystem root / home refused)."""
    return authorize_discovery_root(
        path, root_mode=ROOT_MODE_BOUNDED_DIRECTORY
    ).resolved


def _casefold_paths() -> bool:
    """True when the host filesystem treats paths as case-insensitive."""
    return os.name == "nt" or sys.platform == "darwin"


def canonical_path_key(path: Path) -> str:
    """Platform-correct path identity key for candidate IDs (P7).

    Linux (case-sensitive): preserve case so Foo/ and foo/ stay distinct.
    Windows / macOS: casefold so case aliases collapse to one candidate.
    Unicode is NFC-normalized for deterministic keys.
    """
    resolved = path.expanduser().resolve(strict=False)
    text = unicodedata.normalize("NFC", resolved.as_posix())
    if _casefold_paths():
        return text.casefold()
    return text


def _paths_equal(a: Path, b: Path) -> bool:
    return canonical_path_key(a) == canonical_path_key(b)


def _under_authorized(path: Path, authorized: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(authorized.resolve(strict=False))
        return True
    except ValueError:
        return False
    except (OSError, RuntimeError):
        # Symlink loops / unresolvable paths are not "inside" the root.
        return False


def _is_reparse_or_symlink(entry: Path) -> bool:
    """True for symlinks and Windows reparse/junction points (P6)."""
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True
    if os.name == "nt":
        try:
            st = os.lstat(entry)
        except OSError:
            return True
        attrs = int(getattr(st, "st_file_attributes", 0) or 0)
        if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    return False


def _reparse_escape(entry: Path, authorized: Path) -> bool:
    """True when a reparse/symlink target resolves outside authorized root.

    Symlink loops and unresolvable reparse targets are treated as escapes
    (ignored, not crashed) — D-064 overnight IV.
    """
    if not _is_reparse_or_symlink(entry):
        return False
    try:
        target = entry.resolve(strict=False)
    except (OSError, RuntimeError):
        return True
    return not _under_authorized(target, authorized)


def _candidate_id(kind: str, path: Path) -> str:
    digest = hashlib.sha256(f"{kind}:{canonical_path_key(path)}".encode()).hexdigest()[
        :16
    ]
    return f"{kind}-{digest}"


def _safe_read_text(path: Path, *, limit: int = 64_000) -> str | None:
    """Best-effort UTF-8 read. Returns None when unreadable / binary."""
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
        return None


def _read_json_object(path: Path) -> dict[str, Any] | None:
    text = _safe_read_text(path, limit=2_000_000)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _unwrap_git_config_quotes(url: str) -> str:
    """Strip one matching git-config quote pair; do not invent a full parser."""
    raw = url.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        return raw[1:-1].strip()
    return raw


def sanitize_git_remote_url(url: str) -> str:
    """Strip credential userinfo from git remotes (D-064 / D-067 secret hygiene).

    Discovery may use remotes as fingerprint evidence, but must never echo
    passwords / tokens embedded in URLs into reports, CLI, API, or Web.
    Quoted git-config values (``url = "https://user:pass@host/repo.git"``)
    are unwrapped before ``urlsplit`` so userinfo is not left in-place.
    """
    from urllib.parse import urlsplit, urlunsplit

    raw = _unwrap_git_config_quotes(url)
    if not raw:
        return raw
    if "://" in raw:
        parts = urlsplit(raw)
        if parts.username is None and parts.password is None:
            return raw
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        return urlunsplit(
            (parts.scheme, host, parts.path, parts.query, parts.fragment)
        )
    # scp-like forms rarely embed passwords; leave unchanged.
    return raw


def _git_remote_url(directory: Path) -> str | None:
    """Read git remote without executing git (config parse only)."""
    config = directory / ".git" / "config"
    if not config.is_file() or _is_reparse_or_symlink(config):
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
    chosen = origin_url or any_url
    if chosen is None:
        return None
    return sanitize_git_remote_url(chosen)


def _package_name(directory: Path) -> str | None:
    pkg = directory / "package.json"
    if pkg.is_file() and not _is_reparse_or_symlink(pkg):
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
    if pyproject.is_file() and not _is_reparse_or_symlink(pyproject):
        text = _safe_read_text(pyproject)
        if text:
            match = re.search(r"(?m)^\s*name\s*=\s*[\"']([^\"']+)[\"']", text)
            if match:
                return match.group(1).strip()
    return None


def _normalize_remote(url: str) -> str:
    value = url.strip().casefold()
    value = re.sub(r"^git\+", "", value)
    value = re.sub(r"\.git$", "", value)
    value = value.removeprefix("ssh://")
    return value


def _read_atlas_marker(directory: Path) -> dict[str, Any]:
    """Return marker payload plus status metadata (never silent invalid)."""
    for name in PROJECT_MARKER_FILES:
        marker = directory / name
        if marker.is_file() and not _is_reparse_or_symlink(marker):
            return _parse_marker_file(marker, name)
    for rel in PROJECT_MARKER_NESTED:
        marker = directory / rel
        if marker.is_file() and not _is_reparse_or_symlink(marker):
            return _parse_marker_file(marker, rel.as_posix())
    return {
        "marker_status": "absent",
        "uuid_status": "absent",
        "atlas_project_id": None,
        "atlas_project_uuid": None,
    }


def _parse_marker_file(marker: Path, label: str) -> dict[str, Any]:
    text = _safe_read_text(marker)
    if text is None:
        return {
            "marker_status": "unreadable",
            "uuid_status": "absent",
            "atlas_project_id": None,
            "atlas_project_uuid": None,
            "_marker": label,
        }
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return {
            "marker_status": "invalid",
            "uuid_status": "absent",
            "atlas_project_id": None,
            "atlas_project_uuid": None,
            "_marker": label,
        }
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return {
            "marker_status": "invalid",
            "uuid_status": "absent",
            "atlas_project_id": None,
            "atlas_project_uuid": None,
            "_marker": label,
        }
    project = data.get("project")
    project_id: str | None = None
    if isinstance(project, dict):
        raw_id = project.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            project_id = raw_id.strip()
    raw_uuid = data.get("project_uuid")
    uuid_status = "absent"
    project_uuid: str | None = None
    if raw_uuid is not None and not (isinstance(raw_uuid, str) and not raw_uuid.strip()):
        if not isinstance(raw_uuid, str):
            uuid_status = "invalid"
        else:
            try:
                project_uuid = validate_project_uuid(raw_uuid.strip())
                uuid_status = "ok"
            except ValueError:
                uuid_status = "invalid"
    return {
        "marker_status": "ok",
        "uuid_status": uuid_status,
        "atlas_project_id": project_id,
        "atlas_project_uuid": project_uuid,
        "_marker": label,
    }


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
        if child.is_dir() and not _is_reparse_or_symlink(child):
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
    return obsidian.is_dir() and not _is_reparse_or_symlink(obsidian)


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
        if child.is_dir() and not _is_reparse_or_symlink(child):
            signals.append(f"knowledge_dir:{dirname}")
    md_count = sum(1 for f in lower_files if f.endswith(".md"))
    if md_count >= 3:
        signals.append(f"markdown_cluster:{md_count}")
    return signals


def _build_fingerprint(directory: Path, signals: Sequence[str]) -> dict[str, Any]:
    marker = _read_atlas_marker(directory)
    remote = _git_remote_url(directory) if "git_dir" in signals else None
    package = _package_name(directory)
    return {
        "canonical_path": directory.resolve(strict=False).as_posix(),
        "path_key": canonical_path_key(directory),
        "path_fingerprint": root_identity_fingerprint(directory),
        "atlas_project_id": marker.get("atlas_project_id"),
        "atlas_project_uuid": marker.get("atlas_project_uuid"),
        "marker_status": marker.get("marker_status", "absent"),
        "uuid_status": marker.get("uuid_status", "absent"),
        "git_remote": remote,
        "package_name": package,
        "directory_name": directory.name,
    }


def _live_root_metadata(root: Path | None) -> tuple[str | None, str | None]:
    if root is None or not root.is_dir():
        return None, None
    return _git_remote_url(root), _package_name(root)


def _collect_bind_roots_from_estate(
    authorized_root: Path | None,
) -> dict[str, dict[str, Any]]:
    """Find ``.atlas/connect.json`` binds under the authorized estate (read-only)."""
    found: dict[str, dict[str, Any]] = {}
    if authorized_root is None or not authorized_root.is_dir():
        return found
    # Shallow-ish walk for bind files only (bounded).
    stack: list[tuple[Path, int]] = [(authorized_root, 0)]
    seen: set[str] = set()
    while stack:
        current, depth = stack.pop()
        key = canonical_path_key(current)
        if key in seen:
            continue
        seen.add(key)
        bind_path = current / BIND_RELATIVE
        if bind_path.is_file() and not _is_reparse_or_symlink(bind_path):
            payload = _read_json_object(bind_path)
            if payload is not None:
                found[key] = payload
        if depth >= DEFAULT_MAX_DEPTH:
            continue
        names, _ = _dir_entries(current)
        for name in names:
            if name.casefold() in {n.casefold() for n in IGNORE_DIR_NAMES}:
                continue
            child = current / name
            if _is_reparse_or_symlink(child):
                continue
            if child.is_dir():
                stack.append((child, depth + 1))
    return found


def load_vault_project_identities(
    vault: Path | None,
    *,
    authorized_root: Path | None = None,
) -> list[VaultProjectIdentity]:
    """Load governed Atlas identity for matching (P3).

    Source of truth:
    - ``receipts/source-lineage/project-*-allocation.json`` (UUID ownership)
    - ``vault/projects/*`` presence
    - ``generated/ops/connect-manifest.json`` / connect-receipt (last bind root)
    - ``sources/manifests/source-manifest.json`` (multi-project ownership)
    - live ``.atlas/connect.json`` under authorized estate (bind proof)

    Does not invent a discovery-only truth store.
    """
    if vault is None:
        return []
    vault = vault.expanduser().resolve(strict=False)
    projects_root = vault / "projects"
    if not projects_root.is_dir():
        return []

    by_id: dict[str, VaultProjectIdentity] = {}
    for entry in sorted(projects_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        by_id[entry.name] = VaultProjectIdentity(
            project_id=entry.name,
            project_uuid=None,
            identity_sources=("vault/projects",),
        )

    # Canonical UUID ownership from allocation receipts.
    try:
        uuid_owners = load_allocation_uuid_owners(vault)
        id_to_uuid = load_allocation_project_uuids(vault)
    except ValueError:
        # Unreadable/conflicting receipts: leave UUIDs unset; matching will
        # fail closed on conflicts when fingerprint provides UUID evidence.
        uuid_owners = {}
        id_to_uuid = {}

    for project_id, project_uuid in id_to_uuid.items():
        existing = by_id.get(project_id)
        alloc_sources: tuple[str, ...] = ("allocation_receipt",)
        if existing is not None:
            merged_sources = tuple(
                dict.fromkeys([*existing.identity_sources, *alloc_sources])
            )
            by_id[project_id] = VaultProjectIdentity(
                project_id=project_id,
                project_uuid=project_uuid,
                bind_root=existing.bind_root,
                package_name=existing.package_name,
                git_remote=existing.git_remote,
                bind_proven=existing.bind_proven,
                identity_sources=merged_sources,
            )
        else:
            by_id[project_id] = VaultProjectIdentity(
                project_id=project_id,
                project_uuid=project_uuid,
                identity_sources=alloc_sources,
            )
    _ = uuid_owners  # cardinality already enforced by load helpers

    # Last-writer connect-manifest + receipt for bind root.
    bind_by_project: dict[str, str] = {}
    connect_manifest = _read_json_object(vault / MANIFEST_RELATIVE)
    if connect_manifest is not None:
        source_root = connect_manifest.get("source_root")
        if isinstance(source_root, str) and source_root.strip():
            # Infer primary project from sources' likely_project majority.
            counts: dict[str, int] = {}
            for src in connect_manifest.get("sources") or []:
                if not isinstance(src, dict):
                    continue
                pid = src.get("likely_project")
                if isinstance(pid, str) and pid.strip():
                    counts[pid.strip()] = counts.get(pid.strip(), 0) + 1
            if counts:
                primary = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                bind_by_project[primary] = source_root.strip()

    receipt = _read_json_object(vault / CONNECT_RECEIPT_RELATIVE)
    if receipt is not None:
        root = receipt.get("project_root")
        pid = receipt.get("project_id")
        if isinstance(root, str) and isinstance(pid, str) and pid.strip():
            bind_by_project[pid.strip()] = root.strip()
        projects = receipt.get("projects")
        if isinstance(root, str) and isinstance(projects, list) and len(projects) == 1:
            only = projects[0]
            if isinstance(only, str) and only.strip():
                bind_by_project.setdefault(only.strip(), root.strip())

    # Durable multi-project source-manifest ownership roots.
    durable = _read_json_object(vault / DURABLE_SOURCE_MANIFEST)
    if durable is not None:
        durable_root = durable.get("source_root")
        if isinstance(durable_root, str) and durable_root.strip():
            for src in durable.get("sources") or []:
                if not isinstance(src, dict):
                    continue
                pid = src.get("likely_project")
                if isinstance(pid, str) and pid.strip():
                    bind_by_project.setdefault(pid.strip(), durable_root.strip())

    # Live binds under authorized estate.
    estate_binds = _collect_bind_roots_from_estate(authorized_root)
    for bind in estate_binds.values():
        recorded_root = bind.get("project_root")
        pid = bind.get("project_id")
        if not isinstance(recorded_root, str) or not isinstance(pid, str):
            continue
        if not recorded_root.strip() or not pid.strip():
            continue
        try:
            recorded_path = Path(recorded_root).expanduser().resolve(strict=False)
        except OSError:
            continue
        # Bind vault must resolve to this vault when possible.
        bound_vault = bind.get("vault")
        if isinstance(bound_vault, str) and bound_vault.strip():
            try:
                bv = Path(bound_vault)
                if not bv.is_absolute():
                    bv = recorded_path / bv
                if bv.resolve(strict=False) != vault:
                    continue
            except OSError:
                continue
        # Bind must still own the recorded root (copied-bind protection).
        if not _paths_equal(recorded_path, Path(recorded_root).expanduser()):
            # Still accept after normalize when expanduser/resolve differs only
            # by symlink resolution within the same key.
            pass
        bind_by_project[pid.strip()] = recorded_path.as_posix()

    # Apply bind roots + live package/git metadata from those roots.
    for project_id, root_text in bind_by_project.items():
        existing = by_id.get(project_id)
        if existing is None:
            continue
        try:
            root_path = Path(root_text).expanduser().resolve(strict=False)
        except OSError:
            continue
        remote, package = _live_root_metadata(root_path)
        bind_sources: tuple[str, ...] = tuple(
            dict.fromkeys(
                [*existing.identity_sources, "bind_or_source_ownership"]
            )
        )
        by_id[project_id] = VaultProjectIdentity(
            project_id=project_id,
            project_uuid=existing.project_uuid or id_to_uuid.get(project_id),
            bind_root=root_path.as_posix(),
            package_name=package,
            git_remote=remote,
            bind_proven=True,
            identity_sources=bind_sources,
        )

    return [by_id[k] for k in sorted(by_id)]


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
    """Explainable project matching with Coder Alpha identity matrix (P1/P4)."""
    evidence: list[MatchEvidence] = []
    conflicts: list[MatchEvidence] = []

    marker_status = str(fingerprint.get("marker_status") or "absent")
    uuid_status = str(fingerprint.get("uuid_status") or "absent")
    atlas_id = fingerprint.get("atlas_project_id")
    atlas_uuid = fingerprint.get("atlas_project_uuid")
    remote = fingerprint.get("git_remote")
    package = fingerprint.get("package_name")
    dirname = fingerprint.get("directory_name")

    if marker_status in {"invalid", "unreadable"}:
        conflicts.append(
            MatchEvidence(
                f"marker_{marker_status}",
                f"project marker is {marker_status}; refusing healthy EXACT",
                "invalid",
            )
        )
        return "CONFLICTING", evidence, conflicts, None, None

    if uuid_status == "invalid":
        conflicts.append(
            MatchEvidence(
                "invalid_project_uuid",
                "explicit project_uuid is invalid UUIDv4; not treated as absent",
                "invalid",
            )
        )
        # Still surface ID conflicts if present.
        if isinstance(atlas_id, str) and atlas_id:
            for vp in vault_projects:
                if vp.project_id == atlas_id and vp.project_uuid:
                    conflicts.append(
                        MatchEvidence(
                            "same_id_invalid_uuid",
                            f"marker id {atlas_id} has invalid uuid while "
                            f"governed uuid is present for that id",
                            "conflict",
                        )
                    )
        return "CONFLICTING", evidence, conflicts, None, None

    if not vault_projects:
        return "UNMATCHED", evidence, conflicts, None, None

    id_hits = [
        vp
        for vp in vault_projects
        if isinstance(atlas_id, str) and atlas_id and vp.project_id == atlas_id
    ]
    uuid_hits = [
        vp
        for vp in vault_projects
        if isinstance(atlas_uuid, str)
        and atlas_uuid
        and vp.project_uuid
        and vp.project_uuid == atlas_uuid
    ]

    # P1-B: same id, different uuid (both present and governed).
    if isinstance(atlas_id, str) and atlas_id and isinstance(atlas_uuid, str) and atlas_uuid:
        for vp in id_hits:
            if vp.project_uuid and vp.project_uuid != atlas_uuid:
                conflicts.append(
                    MatchEvidence(
                        "same_id_different_uuid",
                        f"marker id {atlas_id} has uuid {atlas_uuid} but "
                        f"governed allocation uuid is {vp.project_uuid}",
                        "conflict",
                    )
                )
        # P1-C: different id, same uuid.
        for vp in uuid_hits:
            if vp.project_id != atlas_id:
                conflicts.append(
                    MatchEvidence(
                        "different_id_same_uuid",
                        f"uuid owned by governed project {vp.project_id} but "
                        f"marker id is {atlas_id}",
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
        return "CONFLICTING", evidence, conflicts, None, (
            atlas_uuid if isinstance(atlas_uuid, str) else None
        )

    def _remote_conflicts_for(matched_id: str) -> list[MatchEvidence]:
        rows: list[MatchEvidence] = []
        if not isinstance(remote, str) or not remote:
            return rows
        norm = _normalize_remote(remote)
        for vp in vault_projects:
            if not vp.git_remote:
                continue
            if _normalize_remote(vp.git_remote) != norm:
                continue
            if vp.project_id != matched_id:
                rows.append(
                    MatchEvidence(
                        "git_remote_vs_marker_id",
                        f"git remote matches {vp.project_id} but marker/"
                        f"matched id is {matched_id}",
                        "conflict",
                    )
                )
        return rows

    if len(uuid_hits) == 1:
        hit = uuid_hits[0]
        remote_conflicts = _remote_conflicts_for(hit.project_id)
        if remote_conflicts:
            return "CONFLICTING", evidence, remote_conflicts, None, hit.project_uuid
        evidence.append(
            MatchEvidence(
                "atlas_project_uuid",
                f"marker uuid matches governed project {hit.project_id}",
                "exact",
            )
        )
        if isinstance(atlas_id, str) and atlas_id and atlas_id == hit.project_id:
            evidence.append(
                MatchEvidence(
                    "atlas_project_id",
                    f"marker project.id equals governed project {hit.project_id}",
                    "exact",
                )
            )
        elif not atlas_id:
            evidence.append(
                MatchEvidence(
                    "atlas_project_id_absent",
                    "marker project.id absent; EXACT via governed uuid ownership",
                    "exact",
                )
            )
        return "EXACT", evidence, [], hit.project_id, hit.project_uuid

    if len(id_hits) == 1 and uuid_status == "absent":
        hit = id_hits[0]
        remote_conflicts = _remote_conflicts_for(hit.project_id)
        if remote_conflicts:
            return "CONFLICTING", evidence, remote_conflicts, None, hit.project_uuid
        evidence.append(
            MatchEvidence(
                "atlas_project_id",
                f"marker project.id equals governed project {hit.project_id}",
                "exact",
            )
        )
        evidence.append(
            MatchEvidence(
                "uuid_absent",
                "marker project_uuid absent; matched by governed project.id only",
                "weak",
            )
        )
        return "EXACT", evidence, [], hit.project_id, hit.project_uuid

    if len(id_hits) > 1:
        return "AMBIGUOUS", evidence, conflicts, None, None

    # Heuristic layers — never EXACT.
    strong_hits: list[VaultProjectIdentity] = []
    likely_hits: list[VaultProjectIdentity] = []

    if isinstance(remote, str) and remote:
        norm = _normalize_remote(remote)
        for vp in vault_projects:
            if vp.git_remote and _normalize_remote(vp.git_remote) == norm:
                if isinstance(atlas_id, str) and atlas_id and atlas_id != vp.project_id:
                    conflicts.append(
                        MatchEvidence(
                            "git_remote_vs_marker_id",
                            f"git remote matches {vp.project_id} but marker id "
                            f"is {atlas_id}",
                            "conflict",
                        )
                    )
                else:
                    strong_hits.append(vp)
                    evidence.append(
                        MatchEvidence(
                            "git_remote",
                            f"git remote matches bind/source root of {vp.project_id}",
                            "strong",
                        )
                    )

    if conflicts:
        return "CONFLICTING", evidence, conflicts, None, None

    if isinstance(package, str) and package:
        for vp in vault_projects:
            if vp.package_name and vp.package_name.casefold() == package.casefold():
                strong_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "package_name",
                        f"package name matches bind/source root of {vp.project_id}",
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

    # Canonical/root evidence: candidate path equals governed bind_root.
    cand_path = fingerprint.get("canonical_path")
    if isinstance(cand_path, str) and cand_path:
        for vp in vault_projects:
            if vp.bind_root and _paths_equal(Path(cand_path), Path(vp.bind_root)):
                strong_hits.append(vp)
                evidence.append(
                    MatchEvidence(
                        "canonical_bind_root",
                        f"candidate path equals governed bind/source root "
                        f"for {vp.project_id}",
                        "strong",
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


def prove_connected(
    candidate_path: Path,
    matched_project_id: str | None,
    match_state: MatchState,
    vault_projects: Sequence[VaultProjectIdentity],
    *,
    vault: Path | None = None,
) -> tuple[bool, list[str]]:
    """CONNECTED only with durable bind / source-root ownership (P2)."""
    if match_state != "EXACT" and match_state != "STRONG_EVIDENCE":
        return False, []
    if not matched_project_id:
        return False, []
    vp = next((p for p in vault_projects if p.project_id == matched_project_id), None)
    if vp is None:
        return False, []

    why: list[str] = []
    # Governed bind_root equality.
    if vp.bind_proven and vp.bind_root:
        try:
            if _paths_equal(candidate_path, Path(vp.bind_root)):
                why.append(
                    f"candidate root equals governed bind/source root for "
                    f"{matched_project_id}"
                )
                return True, why
        except OSError:
            pass

    # Live connect bind on the candidate itself.
    bind_path = candidate_path / BIND_RELATIVE
    if bind_path.is_file() and not _is_reparse_or_symlink(bind_path):
        bind = _read_json_object(bind_path)
        if bind is not None:
            recorded = bind.get("project_root")
            pid = bind.get("project_id")
            if (
                isinstance(recorded, str)
                and isinstance(pid, str)
                and pid == matched_project_id
            ):
                try:
                    if _paths_equal(Path(recorded), candidate_path):
                        if vault is not None:
                            bound_vault = bind.get("vault")
                            if isinstance(bound_vault, str) and bound_vault.strip():
                                bv = Path(bound_vault)
                                if not bv.is_absolute():
                                    bv = candidate_path / bv
                                if bv.resolve(strict=False) != vault.resolve(
                                    strict=False
                                ):
                                    return False, [
                                        "connect bind vault does not match "
                                        "discovery vault"
                                    ]
                        why.append(
                            "live .atlas/connect.json bind proves current "
                            f"root ownership for {matched_project_id}"
                        )
                        return True, why
                except OSError:
                    pass

    # Same id in vault/projects alone is NOT connected.
    return False, [
        f"matched {matched_project_id} but no durable bind/source-root "
        "ownership proves this candidate root is currently connected"
    ]


def _why_from_evidence(
    evidence: Sequence[MatchEvidence], match_state: MatchState
) -> list[str]:
    if not evidence:
        if match_state == "UNMATCHED":
            return ["no vault project identity matched this candidate"]
        return [f"classified as {match_state}"]
    return [f"{row.kind}: {row.detail}" for row in evidence]


def _required_action(match_state: MatchState, *, connected: bool) -> str | None:
    if connected:
        return None
    if match_state == "CONFLICTING":
        return (
            "Resolve identity conflict (UUID/id ownership) before connect; "
            "do not unify projects"
        )
    if match_state == "AMBIGUOUS":
        return "Choose the correct project identity explicitly, then connect"
    if match_state in {"EXACT", "STRONG_EVIDENCE", "LIKELY"}:
        return "Review match evidence; connect only if accepted"
    if match_state == "UNMATCHED":
        return "New project candidate — connect to create governed identity"
    return None


def _category_for(
    *,
    kind: str,
    match_state: MatchState,
    connected: bool,
    knowledge_relation: KnowledgeRelation | None = None,
) -> Category:
    if connected:
        return "CONNECTED"
    if match_state in {"AMBIGUOUS", "CONFLICTING"}:
        return "AMBIGUOUS_MATCHES"
    if kind != "project":
        if knowledge_relation == "KNOWLEDGE_PROJECT_MATCHED":
            return "NEW_KNOWLEDGE"
        if knowledge_relation == "KNOWLEDGE_AMBIGUOUS":
            return "AMBIGUOUS_MATCHES"
        if knowledge_relation == "KNOWLEDGE_UNMATCHED" or match_state == "UNMATCHED":
            return "UNMATCHED_KNOWLEDGE"
        return "NEW_KNOWLEDGE"
    return "DISCOVERED_PROJECTS"


def _lifecycle_for(
    match_state: MatchState, *, connected: bool, marker_bad: bool
) -> LifecycleState:
    if connected:
        return "CONNECTED"
    if marker_bad or match_state in {"CONFLICTING", "AMBIGUOUS"}:
        return "POLICY_REVIEW"
    if match_state in {"EXACT", "STRONG_EVIDENCE", "LIKELY"}:
        return "PROJECT_MATCHED"
    if match_state == "UNMATCHED":
        return "CLASSIFIED"
    return "CANDIDATE"


def _associate_knowledge(
    knowledge_path: Path,
    project_candidates: Sequence[DiscoveryCandidate],
    *,
    is_obsidian: bool,
    vault_projects: Sequence[VaultProjectIdentity],
) -> tuple[KnowledgeRelation, MatchState, list[MatchEvidence], str | None]:
    """Classify knowledge→project relationship without ingest (P5)."""
    evidence: list[MatchEvidence] = []
    # Structural nesting under a discovered project root.
    parents = [
        p
        for p in project_candidates
        if _under_authorized(knowledge_path, Path(p.path))
        and not _paths_equal(knowledge_path, Path(p.path))
    ]
    # Prefer deepest project parent.
    parents.sort(key=lambda p: len(Path(p.path).parts), reverse=True)
    if len(parents) == 1:
        parent = parents[0]
        evidence.append(
            MatchEvidence(
                "nested_under_project",
                f"knowledge path is nested under project candidate "
                f"{parent.display_name}",
                "strong",
            )
        )
        return (
            "KNOWLEDGE_PROJECT_MATCHED",
            parent.match_state if parent.match_state != "UNMATCHED" else "LIKELY",
            evidence,
            parent.matched_project_id or parent.display_name,
        )
    if len(parents) > 1:
        evidence.append(
            MatchEvidence(
                "nested_under_multiple_projects",
                "knowledge path nests under multiple project candidates",
                "conflict",
            )
        )
        return "KNOWLEDGE_AMBIGUOUS", "AMBIGUOUS", evidence, None

    # Obsidian: never silently assign whole personal vault.
    if is_obsidian:
        name_hits = [
            vp
            for vp in vault_projects
            if vp.project_id.casefold() in knowledge_path.name.casefold()
        ]
        if len(name_hits) == 1:
            evidence.append(
                MatchEvidence(
                    "obsidian_name_hint",
                    f"vault directory name hints project {name_hits[0].project_id}; "
                    "review required — not auto-trusted",
                    "likely",
                )
            )
            return (
                "KNOWLEDGE_AMBIGUOUS",
                "LIKELY",
                evidence,
                name_hits[0].project_id,
            )
        evidence.append(
            MatchEvidence(
                "obsidian_unassigned",
                "Obsidian vault discovered; not silently assigned to a project",
                "weak",
            )
        )
        return "KNOWLEDGE_UNMATCHED", "UNMATCHED", evidence, None

    return "KNOWLEDGE_DISCOVERED", "UNMATCHED", evidence, None


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
    root_mode: str = ROOT_MODE_BOUNDED_DIRECTORY,
    host_os: str | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Bounded filesystem discovery under one authorized root.

    ``prior_cache`` is recorded for Lane H foundation only — never used to skip
    identity re-evaluation (P11: STALE_CACHE_TRUTH = 0).
    ``root_mode`` default is bounded-directory. Owner-authorized Windows
    non-system volume roots require an explicit mode; they never connect
    or ingest.
    """
    _ = prior_cache  # intentionally unused for skip decisions
    policy = authorize_discovery_root(
        authorized_root,
        root_mode=root_mode,
        host_os=host_os,
        environ=environ,
    )
    root = policy.resolved
    vault_resolved = vault.expanduser().resolve(strict=False) if vault else None
    vault_projects = load_vault_project_identities(
        vault_resolved, authorized_root=root
    )

    projects: list[DiscoveryCandidate] = []
    knowledge: list[DiscoveryCandidate] = []
    ignored: list[dict[str, str]] = []
    permission_errors: list[dict[str, str]] = []
    unsafe_escapes = 0
    project_limit_reached = False
    knowledge_limit_reached = False
    depth_limit_reached = False
    cache_entries: dict[str, Any] = {}

    stack: list[tuple[Path, int]] = [(root, 0)]
    seen_dirs: set[str] = set()

    while stack:
        current, depth = stack.pop()
        try:
            current_resolved = current.resolve(strict=False)
        except (OSError, RuntimeError):
            ignored.append({"path": current.as_posix(), "reason": "unresolvable_path"})
            continue
        key = canonical_path_key(current_resolved)
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

        try:
            names, lower_files = _dir_entries(current)
        except OSError as exc:
            permission_errors.append(
                {"path": current.as_posix(), "reason": type(exc).__name__}
            )
            continue
        if not names and not current.is_dir():
            permission_errors.append(
                {"path": current.as_posix(), "reason": "not_a_directory"}
            )
            continue

        project_signals = _score_project_signals(current, names, lower_files)
        know_signals = _knowledge_signals(current, names, lower_files)

        try:
            st = current.stat()
            cache_entries[current_resolved.as_posix()] = {
                "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                "signals": sorted(set(project_signals) | set(know_signals)),
            }
        except OSError:
            pass

        if (
            include_projects
            and _is_project_candidate(project_signals)
        ):
            if len(projects) >= max_project_candidates:
                project_limit_reached = True
            else:
                fingerprint = _build_fingerprint(current, project_signals)
                match_state, evidence, conflicts, matched_id, matched_uuid = (
                    match_fingerprint(fingerprint, vault_projects)
                )
                connected, why_connected = prove_connected(
                    current_resolved,
                    matched_id,
                    match_state,
                    vault_projects,
                    vault=vault_resolved,
                )
                marker_bad = fingerprint.get("marker_status") in {
                    "invalid",
                    "unreadable",
                } or fingerprint.get("uuid_status") == "invalid"
                required_review = (
                    match_state in {"AMBIGUOUS", "CONFLICTING"}
                    or marker_bad
                    or (
                        match_state in {"EXACT", "STRONG_EVIDENCE", "LIKELY"}
                        and not connected
                    )
                )
                projects.append(
                    DiscoveryCandidate(
                        candidate_id=_candidate_id("project", current_resolved),
                        kind="project",
                        path=current_resolved.as_posix(),
                        display_name=current.name,
                        lifecycle=_lifecycle_for(
                            match_state, connected=connected, marker_bad=marker_bad
                        ),
                        match_state=match_state,
                        category=_category_for(
                            kind="project",
                            match_state=match_state,
                            connected=connected,
                        ),
                        why_matched=_why_from_evidence(evidence, match_state),
                        why_connected=why_connected if connected else [],
                        match_evidence=[e.as_dict() for e in evidence],
                        conflicting_evidence=[c.as_dict() for c in conflicts],
                        required_review=required_review,
                        required_action=_required_action(
                            match_state, connected=connected
                        ),
                        signals=list(project_signals),
                        fingerprint=fingerprint,
                        matched_project_id=matched_id,
                        matched_project_uuid=matched_uuid,
                    )
                )

        if include_knowledge:
            is_obsidian = "obsidian_vault" in know_signals
            knowledge_only = bool(know_signals) and (
                is_obsidian
                or not _is_project_candidate(project_signals)
                or any(s.startswith("knowledge_dir:") for s in know_signals)
            )
            if knowledge_only:
                if len(knowledge) >= max_knowledge_candidates:
                    knowledge_limit_reached = True
                else:
                    kind: Literal["knowledge", "obsidian_vault"] = (
                        "obsidian_vault" if is_obsidian else "knowledge"
                    )
                    relation, k_state, k_evidence, k_match = _associate_knowledge(
                        current_resolved,
                        projects,
                        is_obsidian=is_obsidian,
                        vault_projects=vault_projects,
                    )
                    # Standalone knowledge dirs with only knowledge_dir signal.
                    if (
                        relation == "KNOWLEDGE_DISCOVERED"
                        and not is_obsidian
                        and not k_evidence
                    ):
                        relation = "KNOWLEDGE_UNMATCHED"
                    knowledge.append(
                        DiscoveryCandidate(
                            candidate_id=_candidate_id(kind, current_resolved),
                            kind=kind,
                            path=current_resolved.as_posix(),
                            display_name=current.name,
                            lifecycle=(
                                "POLICY_REVIEW"
                                if relation == "KNOWLEDGE_AMBIGUOUS" or is_obsidian
                                else "CLASSIFIED"
                            ),
                            match_state=k_state,
                            category=_category_for(
                                kind=kind,
                                match_state=k_state,
                                connected=False,
                                knowledge_relation=relation,
                            ),
                            why_matched=_why_from_evidence(k_evidence, k_state),
                            match_evidence=[e.as_dict() for e in k_evidence],
                            conflicting_evidence=[],
                            required_review=(
                                is_obsidian or relation == "KNOWLEDGE_AMBIGUOUS"
                            ),
                            required_action=(
                                "Review Obsidian/knowledge relationship; "
                                "discovery does not ingest"
                                if is_obsidian or relation != "KNOWLEDGE_UNMATCHED"
                                else None
                            ),
                            signals=list(know_signals),
                            fingerprint={
                                "canonical_path": current_resolved.as_posix(),
                                "path_key": key,
                                "path_fingerprint": root_identity_fingerprint(current),
                                "directory_name": current.name,
                                "obsidian": is_obsidian,
                            },
                            matched_project_id=k_match,
                            knowledge_relation=relation,
                        )
                    )

        if depth >= max_depth:
            # Honest bound: incompleteness only if a non-ignored, non-reparse
            # directory child would have been descended (D-067 HIGH 2).
            # Policy-ignored names are excluded without traversal.
            folded_at_bound = {n.casefold() for n in IGNORE_DIR_NAMES}
            for name in names:
                if name.casefold() in folded_at_bound:
                    continue
                child = current / name
                if _is_reparse_or_symlink(child):
                    continue
                try:
                    is_dir = child.is_dir()
                except OSError:
                    continue
                if is_dir:
                    depth_limit_reached = True
                    break
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
            if _is_reparse_or_symlink(child):
                if _reparse_escape(child, root):
                    unsafe_escapes += 1
                    ignored.append(
                        {
                            "path": child.as_posix(),
                            "reason": "symlink_or_reparse_escape",
                        }
                    )
                else:
                    # Inside-target reparse: default no-descend (P6).
                    ignored.append(
                        {
                            "path": child.as_posix(),
                            "reason": "reparse_or_symlink_not_descended",
                        }
                    )
                continue
            try:
                is_dir = child.is_dir()
            except OSError:
                permission_errors.append(
                    {"path": child.as_posix(), "reason": "permission_denied"}
                )
                continue
            if not is_dir:
                continue
            stack.append((child, depth + 1))

    projects.sort(key=lambda c: (c.path.casefold(), c.candidate_id))
    knowledge.sort(key=lambda c: (c.path.casefold(), c.candidate_id))
    ignored.sort(
        key=lambda row: (row.get("path", "").casefold(), row.get("reason", ""))
    )

    # Second pass: associate knowledge that was scanned before parent projects
    # were appended (depth-first). Recompute nesting for honesty.
    if include_knowledge and projects:
        refreshed: list[DiscoveryCandidate] = []
        for item in knowledge:
            relation, k_state, k_evidence, k_match = _associate_knowledge(
                Path(item.path),
                projects,
                is_obsidian=item.kind == "obsidian_vault",
                vault_projects=vault_projects,
            )
            if relation == "KNOWLEDGE_DISCOVERED" and item.kind != "obsidian_vault":
                relation = "KNOWLEDGE_UNMATCHED"
            item.knowledge_relation = relation
            item.match_state = k_state
            item.matched_project_id = k_match
            item.why_matched = _why_from_evidence(k_evidence, k_state)
            item.match_evidence = [e.as_dict() for e in k_evidence]
            item.category = _category_for(
                kind=item.kind,
                match_state=k_state,
                connected=False,
                knowledge_relation=relation,
            )
            item.required_review = (
                item.kind == "obsidian_vault" or relation == "KNOWLEDGE_AMBIGUOUS"
            )
            refreshed.append(item)
        knowledge = refreshed

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

    truncation_causes: list[str] = []
    if depth_limit_reached:
        truncation_causes.append("max_depth_reached")
    if project_limit_reached and knowledge_limit_reached:
        truncation_causes.append("project_and_knowledge_limits_reached")
    elif project_limit_reached:
        truncation_causes.append("project_limit_reached")
    elif knowledge_limit_reached:
        truncation_causes.append("knowledge_limit_reached")
    if permission_errors:
        truncation_causes.append("permission_errors")
    scan_complete = not truncation_causes
    truncation_reason: str | None = (
        ",".join(truncation_causes) if truncation_causes else None
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": REPORT_SCHEMA,
        "package_id": PACKAGE_ID,
        "directive_family": DIRECTIVE_FAMILY,
        "invariant": "DISCOVER != INGEST != TRUST != AUTHORITY",
        "discovery_identity_source_of_truth": "EXISTING_GOVERNED_ATLAS_STATE",
        "authorized_root": root.as_posix(),
        "authorized_root_mode": policy.authorized_root_mode,
        "volume_root_authorized": policy.volume_root_authorized,
        "volume_root_kind": policy.volume_root_kind,
        "vault": vault_resolved.as_posix() if vault_resolved is not None else None,
        "generated": {"by": "project-atlas"},
        "security": {
            "symlink_follow": False,
            "reparse_follow": False,
            "code_execution": False,
            "network_discovery": False,
            "whole_disk_scan": False,
            "volume_root_authorized": policy.volume_root_authorized,
            "unsafe_path_escapes_detected": unsafe_escapes,
            "unsafe_path_escapes_allowed": 0,
            "casefold_path_identity": _casefold_paths(),
        },
        "scan": {
            "scan_complete": scan_complete,
            "truncation_reason": truncation_reason,
            "truncation_causes": list(truncation_causes),
            "depth_limit_reached": depth_limit_reached,
            "project_limit_reached": project_limit_reached,
            "knowledge_limit_reached": knowledge_limit_reached,
            "max_depth": max_depth,
            "max_project_candidates": max_project_candidates,
            "max_knowledge_candidates": max_knowledge_candidates,
            "permission_errors": permission_errors,
            "dirs_visited": len(seen_dirs),
        },
        "counts": {
            "projects": len(projects),
            "knowledge": len(knowledge),
            "ignored": len(ignored),
            "required_review": sum(
                1 for c in (*projects, *knowledge) if c.required_review
            ),
            "connected": sum(1 for c in projects if c.category == "CONNECTED"),
        },
        "categories": categories,
        "candidates": {
            "projects": [c.to_dict() for c in projects],
            "knowledge": [c.to_dict() for c in knowledge],
        },
        "incremental_foundation": {
            "cache_schema": "estate-discovery-cache-v1",
            "entries_recorded": len(cache_entries),
            "cache_used_for_skip": False,
            "note": (
                "Cache is foundation-only and never authority; identity is "
                "always recomputed from live filesystem + governed vault state."
            ),
        },
        "_cache_entries": cache_entries,
    }
    return report


def write_discovery_report(report: dict[str, Any], output: Path) -> Path:
    payload = {k: v for k, v in report.items() if not k.startswith("_")}
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(output, content)
    return output


def write_discovery_cache(report: dict[str, Any], output: Path) -> Path:
    entries = report.get("_cache_entries")
    if not isinstance(entries, dict):
        entries = {}
    payload = {
        "schema_version": 1,
        "schema": "estate-discovery-cache-v1",
        "package_id": PACKAGE_ID,
        "authorized_root": report.get("authorized_root"),
        "cache_used_for_skip": False,
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
    """Actionable review rows (P12)."""
    rows: list[dict[str, Any]] = []
    candidates = report.get("candidates")
    if not isinstance(candidates, dict):
        return []
    for bucket in ("projects", "knowledge"):
        items = candidates.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not item.get("required_review"):
                continue
            rows.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "kind": item.get("kind"),
                    "path": item.get("path"),
                    "display_name": item.get("display_name"),
                    "match_state": item.get("match_state"),
                    "lifecycle": item.get("lifecycle"),
                    "category": item.get("category"),
                    "why_matched": item.get("why_matched") or [],
                    "why_connected": item.get("why_connected") or [],
                    "match_evidence": item.get("match_evidence") or [],
                    "conflicting_evidence": item.get("conflicting_evidence") or [],
                    "required_action": item.get("required_action"),
                    "matched_project_id": item.get("matched_project_id"),
                    "knowledge_relation": item.get("knowledge_relation"),
                    "required_review": True,
                }
            )
    rows.sort(
        key=lambda r: (
            str(r.get("path", "")).casefold(),
            str(r.get("candidate_id", "")),
        )
    )
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


def _fingerprint_identity_tuple(fp: dict[str, Any]) -> tuple[Any, ...]:
    return (
        fp.get("atlas_project_id"),
        fp.get("atlas_project_uuid"),
        fp.get("marker_status"),
        fp.get("uuid_status"),
        fp.get("git_remote"),
        fp.get("package_name"),
        fp.get("path_key") or fp.get("canonical_path"),
    )


def connect_discovered_candidate(
    report: dict[str, Any],
    candidate_id: str,
    *,
    vault: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Connect an accepted project candidate with TOCTOU revalidation (P13)."""
    from project_atlas.connect import ConnectError, connect_project

    cand = find_candidate(report, candidate_id)
    if cand is None:
        raise EstateDiscoveryError(f"unknown candidate_id: {candidate_id}")
    kind = cand.get("kind")
    if kind != "project":
        raise EstateDiscoveryError(
            f"refusing to connect non-project candidate ({kind}); "
            "knowledge/obsidian require explicit policy acceptance "
            "(DISCOVER != INGEST)"
        )
    if cand.get("match_state") == "CONFLICTING":
        raise EstateDiscoveryError(
            "refusing to connect CONFLICTING candidate; resolve identity "
            "review first (no silent project unification)"
        )
    if cand.get("match_state") == "AMBIGUOUS":
        raise EstateDiscoveryError(
            "refusing to connect AMBIGUOUS candidate; resolve which project "
            "identity applies first"
        )

    path_raw = cand.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise EstateDiscoveryError("candidate missing path")
    source = Path(path_raw)
    if not source.is_dir():
        raise EstateDiscoveryError(f"candidate path no longer exists: {source}")

    authorized = report.get("authorized_root")
    if isinstance(authorized, str) and authorized.strip():
        try:
            auth = Path(authorized).resolve(strict=False)
            if not _under_authorized(source.resolve(strict=False), auth):
                raise EstateDiscoveryError(
                    "candidate path is outside report authorized_root"
                )
        except OSError as exc:
            raise EstateDiscoveryError(
                f"unable to validate authorized_root containment: {exc}"
            ) from exc

    # TOCTOU: recompute live fingerprint + match; stale report cannot bypass.
    names, lower_files = _dir_entries(source)
    signals = _score_project_signals(source, names, lower_files)
    live_fp = _build_fingerprint(source, signals)
    raw_report_fp = cand.get("fingerprint")
    report_fp: dict[str, Any] = (
        raw_report_fp if isinstance(raw_report_fp, dict) else {}
    )
    vault_projects = load_vault_project_identities(
        vault,
        authorized_root=Path(authorized) if isinstance(authorized, str) else source,
    )
    live_state, _ev, live_conflicts, _mid, _muuid = match_fingerprint(
        live_fp, vault_projects
    )
    if live_state == "CONFLICTING":
        raise EstateDiscoveryError(
            "refusing connect: live identity revalidation is CONFLICTING "
            f"({live_conflicts[0].detail if live_conflicts else 'conflict'})"
        )
    if live_state == "AMBIGUOUS":
        raise EstateDiscoveryError(
            "refusing connect: live identity revalidation is AMBIGUOUS"
        )
    if _fingerprint_identity_tuple(live_fp) != _fingerprint_identity_tuple(report_fp):
        raise EstateDiscoveryError(
            "refusing connect: candidate identity changed since discovery "
            "report (stale report is not authority)"
        )
    if live_state != cand.get("match_state"):
        raise EstateDiscoveryError(
            f"refusing connect: live match_state {live_state} differs from "
            f"report {cand.get('match_state')}"
        )

    try:
        result = connect_project(source, vault=vault, dry_run=dry_run)
    except ConnectError as exc:
        raise EstateDiscoveryError(str(exc)) from exc
    return {
        "package_id": PACKAGE_ID,
        "candidate_id": candidate_id,
        "connect": result if isinstance(result, dict) else {"result": str(result)},
        "revalidated": True,
        "invariant": "DISCOVER != INGEST != TRUST != AUTHORITY",
        "note": "connect invoked explicitly after discovery; discovery alone never ingests",
    }


def format_discovery_human(report: dict[str, Any]) -> str:
    """Stranger-friendly summary: what should the user care about?"""
    lines: list[str] = []
    root = report.get("authorized_root", "?")
    lines.append(f"Atlas knowledge estate discovery under: {root}")
    mode = report.get("authorized_root_mode", ROOT_MODE_BOUNDED_TOKEN)
    lines.append(f"authorized_root_mode: {mode}")
    if report.get("volume_root_authorized"):
        kind = report.get("volume_root_kind") or VOLUME_KIND_NON_SYSTEM_WINDOWS
        lines.append(f"volume_root_authorized: true ({kind})")
        lines.append(
            "This is an explicit owner-authorized Windows volume scan, "
            "not an ordinary bounded-directory scan."
        )
    else:
        lines.append("volume_root_authorized: false")
    lines.append("DISCOVER != INGEST != TRUST != AUTHORITY")
    lines.append("")
    counts_raw = report.get("counts")
    counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
    scan_raw = report.get("scan")
    scan: dict[str, Any] = scan_raw if isinstance(scan_raw, dict) else {}
    lines.append(
        f"Found {counts.get('projects', 0)} project candidate(s), "
        f"{counts.get('knowledge', 0)} knowledge candidate(s), "
        f"{counts.get('required_review', 0)} needing review, "
        f"{counts.get('connected', 0)} connected."
    )
    if not scan.get("scan_complete", True):
        lines.append("SCAN INCOMPLETE")
        if scan.get("depth_limit_reached"):
            lines.append(
                f"Depth limit reached (max_depth={scan.get('max_depth')})."
            )
            lines.append("Some files/directories were not inspected.")
        reason = scan.get("truncation_reason")
        if isinstance(reason, str) and reason and reason != "max_depth_reached":
            lines.append(f"Truncation: {reason}")
        lines.append("Results are not a complete estate inventory.")
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
            why_c = row.get("why_connected")
            if isinstance(why_c, list) and why_c:
                lines.append(f"      connected: {why_c[0]}")
            if row.get("required_review"):
                action = row.get("required_action") or "REQUIRED"
                lines.append(f"      review: {action}")
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
    "DEFAULT_MAX_DEPTH",
    "DIRECTIVE_FAMILY",
    "IGNORE_DIR_NAMES",
    "INCREMENTAL_CACHE_RELATIVE",
    "PACKAGE_ID",
    "REPORT_RELATIVE",
    "ROOT_MODE_BOUNDED_DIRECTORY",
    "ROOT_MODE_OWNER_AUTHORIZED_VOLUME",
    "AuthorizedRootDecision",
    "DiscoveryCandidate",
    "EstateDiscoveryError",
    "VaultProjectIdentity",
    "authorize_discovery_root",
    "canonical_path_key",
    "connect_discovered_candidate",
    "discover_estate",
    "find_candidate",
    "format_discovery_human",
    "is_filesystem_root",
    "is_unc_root",
    "is_windows_drive_volume_root",
    "is_windows_system_volume_root",
    "load_discovery_cache",
    "load_vault_project_identities",
    "match_fingerprint",
    "normalize_root_mode",
    "prove_connected",
    "refuse_dangerous_authorized_root",
    "review_candidates",
    "sanitize_git_remote_url",
    "write_discovery_cache",
    "write_discovery_report",
]
