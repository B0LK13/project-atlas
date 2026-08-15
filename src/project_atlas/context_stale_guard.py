"""AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001 — stamp context/handoff freshness.

Compares live source fingerprints to a frozen context/handoff fingerprint.
Missing evidence is UNKNOWN, never a fabricated FRESH. Telemetry != Truth Core.
Does not rewrite ``connect.py``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-context-stale-guard-001"
SCHEMA_NAME: Final[str] = "atlas.coder-alpha.context-stale-guard.v1"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"
SOURCE_MANIFEST: Final[Path] = Path("sources") / "manifests" / "source-manifest.json"
TRUTH_BOUNDARY: Final[str] = (
    "FRESHNESS != TRUTH CORE / STALE != HEALTH SCORE / "
    "UNKNOWN != FRESH / DEMO_FIXTURE != AUTHENTIC_PILOT"
)

FreshnessStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class ContextStaleGuardError(ValueError):
    """Fail-closed stale-guard error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise ContextStaleGuardError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _posix(relative: str) -> str:
    return relative.replace("\\", "/")


def _iter_manifest_sources(
    payload: dict[str, Any],
    *,
    project_id: str | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return rows
    for item in sources:
        if not isinstance(item, dict):
            continue
        owner = item.get("likely_project") or item.get("project_id")
        if project_id and isinstance(owner, str) and owner != project_id:
            continue
        path = item.get("path")
        digest = item.get("sha256")
        if isinstance(path, str) and path.strip():
            rows.append(
                {
                    "path": _posix(path),
                    "sha256": digest if isinstance(digest, str) else "",
                }
            )
    rows.sort(key=lambda row: row["path"])
    return rows


def _source_root(manifest: dict[str, Any], vault: Path) -> Path | None:
    raw = manifest.get("source_root")
    if not isinstance(raw, str) or not raw.strip():
        receipt = _read_json(vault / "generated" / "ops" / "connect-receipt.json")
        raw = receipt.get("project_root") if receipt else None
    if not isinstance(raw, str) or not raw.strip():
        return None
    if raw.startswith("\\\\") or ".." in Path(raw).parts:
        return None
    root = Path(raw).expanduser()
    try:
        resolved = root.resolve()
    except OSError:
        return None
    return resolved if resolved.is_dir() else None


def live_source_rows(vault: Path, project_id: str) -> tuple[str, list[dict[str, str]]]:
    """Return ``(ok|absent|unreadable, rows)`` for live source fingerprints."""
    vault_path = vault.expanduser().resolve()
    manifest = _read_json(vault_path / CONNECT_MANIFEST)
    origin = "connect-manifest"
    if manifest is None:
        manifest = _read_json(vault_path / SOURCE_MANIFEST)
        origin = "source-manifest"
    if manifest is None:
        return "absent", []
    rows = _iter_manifest_sources(manifest, project_id=project_id)
    if not rows:
        return "unreadable", []
    root = _source_root(manifest, vault_path)
    scoped: list[dict[str, str]] = []
    for row in rows:
        digest = row["sha256"]
        rel = row["path"]
        if root is not None and rel and ".." not in Path(rel).parts and not rel.startswith("/"):
            live_path = root / rel
            if live_path.is_file():
                try:
                    digest = canonical_source_sha256(live_path)
                except OSError:
                    digest = row["sha256"]
            else:
                digest = ""
        scoped.append({"path": rel, "sha256": digest, "origin": origin})
    return "ok", scoped


def fingerprint_rows(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    material = json.dumps(
        [{"path": row["path"], "sha256": row.get("sha256") or ""} for row in rows],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def evaluate_context_freshness(
    vault: Path,
    project_id: str,
    *,
    frozen_fingerprint: str | None = None,
    frozen_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Compare frozen context evidence to live source fingerprints."""
    scoped = _safe_project_id(project_id)
    status_live, live_rows = live_source_rows(vault, scoped)
    live_fp = fingerprint_rows(live_rows)
    if status_live != "ok" or live_fp is None:
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "live_fingerprint": live_fp,
            "frozen_fingerprint": frozen_fingerprint,
            "reason": "source inventory absent or unreadable; not fabricated FRESH",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "fresh_is_authority": False,
                "unknown_is_fresh": False,
                "authentic_pilot": False,
            },
        }

    if frozen_fingerprint is None and not frozen_rows:
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "FRESH",
            "live_fingerprint": live_fp,
            "frozen_fingerprint": live_fp,
            "reason": "no prior pack; live inventory stamped",
            "changed_paths": [],
            "rows": live_rows,
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "fresh_is_authority": False,
                "unknown_is_fresh": False,
                "authentic_pilot": False,
            },
        }

    frozen_fp = frozen_fingerprint
    if frozen_fp is None and frozen_rows is not None:
        frozen_fp = fingerprint_rows(frozen_rows)
    changed: list[str] = []
    if frozen_rows:
        prior = {row["path"]: row.get("sha256") or "" for row in frozen_rows}
        current = {row["path"]: row.get("sha256") or "" for row in live_rows}
        for path in sorted(set(prior) | set(current)):
            if prior.get(path) != current.get(path):
                changed.append(path)
    stale = (frozen_fp is not None and frozen_fp != live_fp) or bool(changed)
    return {
        "schema": SCHEMA_NAME,
        "package": PACKAGE_ID,
        "project_id": scoped,
        "status": "STALE" if stale else "FRESH",
        "live_fingerprint": live_fp,
        "frozen_fingerprint": frozen_fp,
        "reason": "source fingerprint drifted" if stale else "live matches frozen pack",
        "changed_paths": changed,
        "rows": live_rows,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "fresh_is_authority": False,
            "unknown_is_fresh": False,
            "authentic_pilot": False,
        },
    }


def render_freshness_markdown(freshness: dict[str, Any] | None) -> list[str]:
    lines = ["", "## Context freshness"]
    if not freshness:
        lines.append("UNKNOWN — freshness not evaluated")
        lines.append("UNKNOWN != FRESH. Do not treat missing evidence as current.")
        return lines
    status = freshness.get("status") or "UNKNOWN"
    lines.append(f"status={status}")
    lines.append(f"reason={freshness.get('reason') or 'UNKNOWN'}")
    lines.append("FRESHNESS!=TRUTH_CORE. STALE packs must not be used as current.")
    changed = freshness.get("changed_paths") or []
    if isinstance(changed, list) and changed:
        lines.append("changed_paths:")
        lines.extend(f"- `{item}`" for item in changed[:20] if isinstance(item, str))
    return lines
