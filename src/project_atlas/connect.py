"""AS-CODER-ALPHA-CONNECT-001 — ``atlas connect`` one-command project bind+compile.

Binds an explicit project root to a Vault and runs the Core compile chain:

    ensure vault → discover → ingest → rediscover (SEC-002) → ingest
    → build-indexes → validate

Does not invent authentic pilot estates, does not wake Atlas-OPT, and does not
claim AUTHENTIC_PILOT / RELEASE. Deterministic receipts omit wall-clock times
(NFR-001 / ADR-001).
"""

from __future__ import annotations

import json
import os
import re
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
]

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _yaml_scalar(value: str) -> str:
    """Quote a YAML scalar when unsafe as a plain string."""
    if not value or any(ch in value for ch in ":#{}[],&*?|>!%@`'\"\\") or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def project_slug_from_dirname(name: str) -> str:
    """Derive a safe ``project.id`` slug from a directory name (AT-013)."""
    raw = (name or "").strip().lower()
    slug = _SLUG_NON_ALNUM.sub("-", raw).strip("-")
    if not slug:
        slug = "project"
    if slug[0].isdigit():
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


def resolve_vault_path(project_root: Path, vault: Path | None) -> Path:
    """Resolve vault path: ``--vault`` > bind file > ``<project>/.atlas-vault``."""
    if vault is not None:
        return vault.expanduser().resolve()
    bind = _read_bind(project_root)
    if bind is not None:
        bound = bind.get("vault")
        if isinstance(bound, str) and bound.strip():
            candidate = Path(bound)
            if not candidate.is_absolute():
                candidate = (project_root / candidate).resolve()
            else:
                candidate = candidate.resolve()
            return candidate
    return (project_root / DEFAULT_VAULT_DIRNAME).resolve()


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


def _write_bind(project_root: Path, vault: Path, vault_id: str) -> Path:
    payload = {
        "schema_version": 1,
        "schema": "atlas.connect.bind.v1",
        "package": PACKAGE_ID,
        "project_root": project_root.resolve().as_posix(),
        "vault": _vault_rel_or_abs(project_root, vault),
        "vault_id": vault_id,
        "generated": {"by": GENERATOR_ID},
    }
    path = project_root / BIND_RELATIVE
    _write_atomic(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return path


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
    steps.extend(["materialize_overview", "write_bind", "write_receipt"])

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
        # AS-CODER-ALPHA-OVERVIEW-001: materialize derived overview lenses so
        # Knowledge/Ask-live are not empty after connect (DEMO-FINDING-001).
        from project_atlas.overview import materialize_overview_lenses

        overview = materialize_overview_lenses(vault_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConnectError(str(exc)) from exc

    report["documents_ingested"] = int(second.get("documents_ingested", 0))
    report["projects"] = _list_vault_projects(vault_path)
    report["indexes"] = {
        "projects": index_result.get("projects"),
        "sources": index_result.get("sources"),
    }
    report["overview_answers"] = overview.get("answers_written", [])

    bind_path = _write_bind(
        project_root,
        vault_path,
        str(report["vault_id"] or ""),
    )
    report["bind_path"] = bind_path.as_posix()
    receipt_path = _write_receipt(vault_path, report)
    report["receipt_path"] = receipt_path.as_posix()
    report["status"] = "connected"
    return report
