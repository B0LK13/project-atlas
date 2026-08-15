"""AS-CODER-ALPHA-NEXT-STALE-EVIDENCE-001 — What Next must not look current after drift.

Compares live source fingerprints to the last connect-manifest. Cached
``generated/answers`` used by What Next are not live Truth Core.

Honesty:
- STALE evidence != current next work
- missing/unreadable inventory or source_root => UNKNOWN, never FRESH
- NEXT LENS != AUTHORITY
- does not import ``context_stale_guard`` (independent of #380)
- does not rewrite ``connect.py`` / ``cli.py``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-NEXT-STALE-EVIDENCE-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-next-stale-evidence-001"
SCHEMA_NAME: Final[str] = "atlas.coder-alpha.next-stale-evidence.v1"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"
TRUTH_BOUNDARY: Final[str] = (
    "NEXT LENS != AUTHORITY / STALE EVIDENCE != CURRENT / "
    "UNKNOWN != FRESH / ANSWER CACHE != TRUTH CORE"
)

DriftStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class NextStaleEvidenceError(ValueError):
    """Fail-closed next stale-evidence error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise NextStaleEvidenceError(str(exc)) from exc


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


def evaluate_next_source_drift(vault: Path, project_id: str) -> dict[str, Any]:
    """Return FRESH/STALE/UNKNOWN for What Next answer-cache currency."""
    scoped = _safe_project_id(project_id)
    vault_path = vault.expanduser().resolve()
    manifest = _read_json(vault_path / CONNECT_MANIFEST)
    if manifest is None:
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "reason": "connect-manifest absent or unreadable; not fabricated FRESH",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
                "stale_is_current": False,
                "unknown_is_fresh": False,
                "next_is_authority": False,
            },
        }

    sources = manifest.get("sources")
    rows: list[dict[str, str]] = []
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict):
                continue
            if item.get("exclusion_reason"):
                continue
            owner = item.get("likely_project") or item.get("project_id")
            if isinstance(owner, str) and owner != scoped:
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
    if not rows:
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "reason": "no project-scoped sources in connect-manifest",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
                "stale_is_current": False,
                "unknown_is_fresh": False,
                "next_is_authority": False,
            },
        }

    raw_root = manifest.get("source_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        receipt = _read_json(vault_path / "generated" / "ops" / "connect-receipt.json")
        raw_root = receipt.get("project_root") if receipt else None
    if not isinstance(raw_root, str) or not raw_root.strip():
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "reason": "source_root missing; stored hashes are not live evidence",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
                "stale_is_current": False,
                "unknown_is_fresh": False,
                "next_is_authority": False,
            },
        }
    if raw_root.startswith("\\\\") or ".." in Path(raw_root).parts:
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "reason": "source_root rejected; not fabricated FRESH",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
                "stale_is_current": False,
                "unknown_is_fresh": False,
                "next_is_authority": False,
            },
        }
    try:
        root = Path(raw_root).expanduser().resolve()
    except OSError:
        root = None
    if root is None or not root.is_dir():
        return {
            "schema": SCHEMA_NAME,
            "package": PACKAGE_ID,
            "project_id": scoped,
            "status": "UNKNOWN",
            "reason": "source_root missing on disk; stored hashes are not live evidence",
            "changed_paths": [],
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATOR_ID},
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
                "stale_is_current": False,
                "unknown_is_fresh": False,
                "next_is_authority": False,
            },
        }

    changed: list[str] = []
    for row in rows:
        rel = row["path"]
        if not rel or ".." in Path(rel).parts or rel.startswith("/"):
            changed.append(rel or "UNKNOWN")
            continue
        live_path = root / rel
        if not live_path.is_file():
            changed.append(rel)
            continue
        try:
            live = canonical_source_sha256(live_path)
        except OSError:
            changed.append(rel)
            continue
        if live != (row["sha256"] or ""):
            changed.append(rel)

    stale = bool(changed)
    return {
        "schema": SCHEMA_NAME,
        "package": PACKAGE_ID,
        "project_id": scoped,
        "status": "STALE" if stale else "FRESH",
        "reason": "live source fingerprint drifted from connect-manifest"
        if stale
        else "live sources match connect-manifest",
        "changed_paths": changed,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "answer_evidence_stale": stale,
            "live_source_unverified": False,
            "stale_is_current": False,
            "unknown_is_fresh": False,
            "next_is_authority": False,
        },
    }


def stale_queue_item(drift: dict[str, Any]) -> dict[str, Any] | None:
    """Queue item only when drift is proven STALE. UNKNOWN does not invent work."""
    if drift.get("status") != "STALE":
        return None
    changed = [item for item in (drift.get("changed_paths") or []) if isinstance(item, str)]
    why = drift.get("reason") or "source files changed after last connect"
    return {
        "kind": "stale_evidence",
        "title": "What Next evidence may be stale",
        "why": str(why),
        "action": "Re-run atlas connect before treating What Next as current",
        "evidence": ["generated/ops/connect-manifest.json", *changed[:6]],
        "source_package": PACKAGE_ID,
        "subject_id": None,
    }
