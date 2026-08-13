"""AS-CODER-ALPHA-CONNECT-001 — ``atlas connect`` one-command project bind+compile.

Binds an explicit project root to a Vault and runs the Core compile chain:

    ensure vault → discover → ingest → rediscover (SEC-002) → ingest
    → build-indexes → validate

Does not invent authentic pilot estates, does not wake Atlas-OPT, and does not
claim AUTHENTIC_PILOT / RELEASE. Deterministic receipts omit wall-clock times
(NFR-001 / ADR-001).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.discovery import discover, write_manifest
from project_atlas.indexes import build_indexes
from project_atlas.ingestion import ingest
from project_atlas.scaffold import ScaffoldError, create_scaffold
from project_atlas.validation import validate
from project_atlas.vault_identity import VaultIdentityError, read_vault_identity

PACKAGE_ID = "AS-CODER-ALPHA-CONNECT-001"
GENERATOR_ID = "atlas-coder-alpha-connect-001"
DEFAULT_VAULT_DIRNAME = ".atlas-vault"
BIND_RELATIVE = Path(".atlas") / "connect.json"
MANIFEST_RELATIVE = Path("generated") / "ops" / "connect-manifest.json"
RECEIPT_RELATIVE = Path("generated") / "ops" / "connect-receipt.json"

# Defense-in-depth globs (DEFAULT_EXCLUDES already drops `.atlas-vault` / `.atlas`
# by path part). Keep patterns for nested / alternate layouts.
_CONNECT_EXCLUDES = [
    ".git/**",
    ".venv/**",
    "node_modules/**",
    "__pycache__/**",
    ".atlas/**",
    ".atlas-vault/**",
    ".atlas-inbox/**",
    # Keep fixture estates out of real-repo dogfood connects.
    "fixtures/**",
    "**/fixtures/**",
    "tests/fixtures/**",
    # Nested package / vendor trees pollute root-project overview purpose.
    "deps/**",
    "advance-005/**",
    "coverage.xml",
]

_SLUG_DASHES = re.compile(r"-+")


def _yaml_scalar(value: str) -> str:
    """Quote a YAML scalar when unsafe as a plain string."""
    if not value or any(ch in value for ch in ":#{}[],&*?|>!%@`'\"\\") or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def project_slug_from_dirname(name: str) -> str:
    """Derive a safe ``project.id`` slug from a directory name (AT-013 / D-044).

    Preserves Unicode letters (e.g. CJK) so distinct non-ASCII names do not
    silently collide on the ASCII fallback ``project``. Empty/symbol-only names
    use a deterministic content hash suffix.
    """
    raw = unicodedata.normalize("NFKC", (name or "").strip())
    chars: list[str] = []
    for ch in raw:
        if ch.isascii():
            chars.append(ch.lower() if ch.isalnum() else "-")
        elif ch.isalnum():
            chars.append(ch)
        else:
            chars.append("-")
    slug = _SLUG_DASHES.sub("-", "".join(chars)).strip("-")
    if not slug:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        slug = f"project-{digest}"
    elif slug[0].isdigit():
        slug = f"p-{slug}"
    return safe_relative_component(slug, label="project.id")


class ConnectError(ValueError):
    """Fail-closed connect error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _refuse_dangerous_root(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ConnectError(f"{label} does not exist: {resolved}")
    if not resolved.is_dir():
        raise ConnectError(f"{label} is not a directory: {resolved}")
    if resolved.parent == resolved:
        raise ConnectError(f"refusing filesystem root as {label}: {resolved}")
    home = Path.home().resolve()
    if resolved == home:
        raise ConnectError(f"refusing home directory as {label}: {resolved}")
    return resolved


def _read_bind(project_root: Path) -> dict[str, Any] | None:
    bind_path = project_root / BIND_RELATIVE
    if not bind_path.is_file():
        return None
    try:
        raw = json.loads(bind_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConnectError(f"unreadable connect bind file: {bind_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConnectError(f"connect bind file must be a JSON object: {bind_path}")
    return raw


def _bind_owns_root(bind: dict[str, Any], project_root: Path) -> bool:
    """True when bind ``project_root`` matches the caller's resolved cwd/root."""
    recorded = bind.get("project_root")
    if not isinstance(recorded, str) or not recorded.strip():
        return False
    try:
        return Path(recorded).expanduser().resolve() == project_root.resolve()
    except OSError:
        return False


def _require_bind_owns_root(bind: dict[str, Any], project_root: Path) -> None:
    """Fail closed when a bind file was copied/stolen from another tree (D-047 IV)."""
    if not _bind_owns_root(bind, project_root):
        raise ConnectError(
            "connect bind project_root does not match current directory; "
            "re-run `atlas connect .` or pass --vault/--project explicitly"
        )


def resolve_vault_path(project_root: Path, vault: Path | None) -> Path:
    """Resolve vault path: ``--vault`` > bind file > ``<project>/.atlas-vault``."""
    if vault is not None:
        return vault.expanduser().resolve()
    root = project_root.expanduser().resolve()
    bind = _read_bind(root)
    if bind is not None:
        _require_bind_owns_root(bind, root)
        bound = bind.get("vault")
        if isinstance(bound, str) and bound.strip():
            candidate = Path(bound)
            if not candidate.is_absolute():
                candidate = (root / candidate).resolve()
            else:
                candidate = candidate.resolve()
            return candidate
    return (root / DEFAULT_VAULT_DIRNAME).resolve()


def _ensure_project_marker(project_root: Path) -> bool:
    """Create a minimal marker when absent so ingest can allocate ``project_uuid``.

    Writes both ``project.id`` (slug used as vault project key) and
    ``project.name`` (display). Does not invent UUIDs here — genesis remains
    ingestion's job (SEC-002). Returns True when a marker was written.
    """
    for name in (".atlas-project.yaml", ".atlas-project.yml"):
        if (project_root / name).is_file():
            return False
    display = project_root.name.strip() or "project"
    project_id = project_slug_from_dirname(display)
    content = (
        "schema_version: 1\n"
        "project:\n"
        f"  id: {_yaml_scalar(project_id)}\n"
        f"  name: {_yaml_scalar(display)}\n"
    )
    _write_atomic(project_root / ".atlas-project.yaml", content.encode("utf-8"))
    return True


def _active_source_count(manifest: dict[str, Any]) -> int:
    """Count discover records that are eligible for ingest (not excluded)."""
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return 0
    count = 0
    for row in sources:
        if not isinstance(row, dict):
            continue
        if row.get("exclusion_reason"):
            continue
        count += 1
    return count


def _vault_rel_or_abs(project_root: Path, vault: Path) -> str:
    try:
        return vault.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return vault.resolve().as_posix()


def _write_bind(
    project_root: Path,
    vault: Path,
    vault_id: str,
    *,
    project_ids: list[str] | None = None,
) -> Path:
    projects = sorted({str(item) for item in (project_ids or []) if str(item).strip()})
    primary: str | None = projects[0] if len(projects) == 1 else None
    payload = {
        "schema_version": 1,
        "schema": "atlas.connect.bind.v1",
        "package": PACKAGE_ID,
        "project_root": project_root.resolve().as_posix(),
        "vault": _vault_rel_or_abs(project_root, vault),
        "vault_id": vault_id,
        "project_ids": projects,
        "project_id": primary,
        "generated": {"by": GENERATOR_ID},
    }
    path = project_root / BIND_RELATIVE
    _write_atomic(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return path


def resolve_bound_vault(cwd: Path | None = None) -> Path:
    """Resolve vault from ``.atlas/connect.json`` under ``cwd`` (fail closed)."""
    root = (cwd or Path.cwd()).expanduser().resolve()
    bind = _read_bind(root)
    if bind is None:
        # Fall back to default vault dir when present after connect.
        # Refuse symlink escape outside the project root (D-047 IV).
        candidate = root / DEFAULT_VAULT_DIRNAME
        if candidate.is_dir():
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                raise ConnectError(
                    "default vault path resolves outside project root; "
                    "refuse symlink escape — pass --vault explicitly after connect"
                )
            return resolved
        raise ConnectError(
            "no connect bind found; run `atlas connect .` or pass --vault explicitly"
        )
    _require_bind_owns_root(bind, root)
    return resolve_vault_path(root, None)


def resolve_bound_project_id(
    cwd: Path | None = None,
    *,
    vault: Path | None = None,
    requested: str | None = None,
) -> str:
    """Resolve a single project id for stranger CLI commands (fail closed).

    Ambiguous multi-project vaults without an explicit ``--project`` raise.
    """
    if requested is not None and str(requested).strip():
        return safe_relative_component(str(requested).strip(), label="project id")
    root = (cwd or Path.cwd()).expanduser().resolve()
    bind = _read_bind(root)
    if bind is not None:
        _require_bind_owns_root(bind, root)
        bound = bind.get("project_id")
        if isinstance(bound, str) and bound.strip():
            return safe_relative_component(bound.strip(), label="project id")
        bound_ids = bind.get("project_ids")
        if isinstance(bound_ids, list):
            ids = [
                safe_relative_component(str(item).strip(), label="project id")
                for item in bound_ids
                if isinstance(item, str) and item.strip()
            ]
            if len(ids) == 1:
                return ids[0]
            if len(ids) > 1:
                raise ConnectError(
                    "ambiguous project_ids in connect bind; pass --project explicitly "
                    f"(candidates: {', '.join(ids)})"
                )
    vault_path = vault or resolve_bound_vault(root)
    projects = _list_vault_projects(vault_path)
    if len(projects) == 1:
        return projects[0]
    if not projects:
        raise ConnectError(
            "no projects found in vault; run `atlas connect .` or pass --project"
        )
    raise ConnectError(
        "ambiguous vault projects; pass --project explicitly "
        f"(candidates: {', '.join(projects)})"
    )


def _write_receipt(vault: Path, report: dict[str, Any]) -> Path:
    path = vault / RECEIPT_RELATIVE
    _write_atomic(
        path,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return path


def _list_vault_projects(vault: Path) -> list[str]:
    projects_root = vault / "projects"
    if not projects_root.is_dir():
        return []
    return sorted(
        path.name
        for path in projects_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def connect_project(
    source: Path,
    *,
    vault: Path | None = None,
    dry_run: bool = False,
    include_portfolio: bool = False,
    skip_validate: bool = False,
    excludes: list[str] | None = None,
    max_file_size: int = 10 * 1024 * 1024,
) -> dict[str, Any]:
    """Bind ``source`` to a Vault and run the Core compile chain."""
    project_root = _refuse_dangerous_root(source, label="project root")
    vault_path = resolve_vault_path(project_root, vault)
    # Vault may live under the project (default ``.atlas-vault``); refuse only
    # when the caller points vault at home/filesystem root.
    if vault_path.parent == vault_path:
        raise ConnectError(f"refusing filesystem root as vault: {vault_path}")
    if vault_path == Path.home().resolve():
        raise ConnectError(f"refusing home directory as vault: {vault_path}")

    merged_excludes = list(dict.fromkeys([*(excludes or []), *_CONNECT_EXCLUDES]))
    steps = [
        "ensure_vault",
        "ensure_project_marker",
        "discover",
        "ingest",
        "rediscover",
        "ingest_baseline",
        "build_indexes",
    ]
    if include_portfolio:
        steps.append("build_portfolio")
    if not skip_validate:
        steps.append("validate")
    steps.extend(
        [
            # Architecture before overview so D-044 A3 coverage reconciliation sees
            # ans-architecture-* on the first connect write (D-047 IV).
            "materialize_architecture",
            "materialize_overview",
            "materialize_state",
            "materialize_changed",
            "materialize_decisions",
            "materialize_unknown",
            "materialize_brief",
            "materialize_obsidian",
            "write_bind",
            "write_receipt",
        ]
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.connect.receipt.v1",
        "package": PACKAGE_ID,
        "status": "planned" if dry_run else "connected",
        "project_root": project_root.as_posix(),
        "vault": vault_path.as_posix(),
        "steps": steps,
        "documents_discovered": 0,
        "documents_ingested": 0,
        "projects": [],
        "overview_answers": [],
        "architecture_answers": [],
        "state_answers": [],
        "changed_answers": [],
        "decisions_answers": [],
        "unknown_answers": [],
        "brief_paths": [],
        "obsidian_notes": [],
        "marker_created": False,
        "vault_created": False,
        "vault_id": None,
        "bind_path": (project_root / BIND_RELATIVE).as_posix(),
        "manifest_path": (vault_path / MANIFEST_RELATIVE).as_posix(),
        "receipt_path": (vault_path / RECEIPT_RELATIVE).as_posix(),
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "release_certified": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }

    if dry_run:
        report["status"] = "dry_run"
        return report

    vault_existed = (vault_path / "index.md").is_file() or (
        vault_path / ".atlas" / "vault.json"
    ).is_file()
    try:
        create_scaffold(vault_path)
    except (ScaffoldError, OSError) as exc:
        raise ConnectError(f"unable to ensure vault: {exc}") from exc
    report["vault_created"] = not vault_existed

    try:
        identity = read_vault_identity(vault_path)
        report["vault_id"] = identity.vault_id
    except VaultIdentityError as exc:
        raise ConnectError(f"vault identity unavailable after scaffold: {exc}") from exc

    report["marker_created"] = _ensure_project_marker(project_root)

    manifest_path = vault_path / MANIFEST_RELATIVE
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        manifest = discover(
            project_root,
            excludes=merged_excludes,
            max_file_size=max_file_size,
        )
        write_manifest(manifest, manifest_path)
        report["documents_discovered"] = _active_source_count(manifest)

        ingest(
            manifest_path,
            vault_path,
            authorized_source_root=project_root,
        )
        # SEC-002: marker genesis may rewrite ``.atlas-project.yaml``.
        manifest = discover(
            project_root,
            excludes=merged_excludes,
            max_file_size=max_file_size,
        )
        write_manifest(manifest, manifest_path)
        report["documents_discovered"] = _active_source_count(manifest)

        second = ingest(
            manifest_path,
            vault_path,
            authorized_source_root=project_root,
        )
        index_result = build_indexes(vault_path)
        if include_portfolio:
            from project_atlas.portfolio import build_portfolio as run_build_portfolio

            run_build_portfolio(vault_path)
        if not skip_validate:
            validate(vault_path)
        # Coder Alpha derived lenses for Knowledge/Ask-live + project brief.
        from project_atlas.overview import materialize_overview_lenses
        from project_atlas.project_architecture import materialize_architecture_lenses
        from project_atlas.project_brief import materialize_project_briefs
        from project_atlas.project_changed import materialize_changed_lenses
        from project_atlas.project_decisions import materialize_decisions_lenses
        from project_atlas.project_state import materialize_state_lenses
        from project_atlas.project_unknown import materialize_unknown_lenses

        architecture = materialize_architecture_lenses(vault_path)
        overview = materialize_overview_lenses(vault_path)
        state = materialize_state_lenses(vault_path)
        changed = materialize_changed_lenses(vault_path, manifest=manifest)
        decisions = materialize_decisions_lenses(vault_path)
        unknown = materialize_unknown_lenses(vault_path)
        # refresh=False: lenses just written above.
        brief = materialize_project_briefs(vault_path, refresh=False)
        from project_atlas.obsidian_projection import materialize_obsidian_projection

        obsidian = materialize_obsidian_projection(vault_path, refresh_brief=False)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConnectError(str(exc)) from exc

    report["documents_ingested"] = int(second.get("documents_ingested", 0))
    report["projects"] = _list_vault_projects(vault_path)
    report["indexes"] = {
        "projects": index_result.get("projects"),
        "sources": index_result.get("sources"),
    }
    report["overview_answers"] = overview.get("answers_written", [])
    report["architecture_answers"] = architecture.get("answers_written", [])
    report["state_answers"] = state.get("answers_written", [])
    report["changed_answers"] = changed.get("answers_written", [])
    report["changed_delta"] = changed.get("delta", {})
    report["decisions_answers"] = decisions.get("answers_written", [])
    report["unknown_answers"] = unknown.get("answers_written", [])
    report["brief_paths"] = brief.get("briefs_written", [])
    report["obsidian_notes"] = obsidian.get("notes_written", [])

    bind_path = _write_bind(
        project_root,
        vault_path,
        str(report["vault_id"] or ""),
        project_ids=list(report["projects"] or []),
    )
    report["bind_path"] = bind_path.as_posix()
    receipt_path = _write_receipt(vault_path, report)
    report["receipt_path"] = receipt_path.as_posix()
    report["status"] = "connected"
    return report
