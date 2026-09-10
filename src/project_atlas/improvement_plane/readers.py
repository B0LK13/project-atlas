"""Read-only loaders for delivery evidence and optional vault ops surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.ops_receipts import inventory_ops_receipts

EVIDENCE_REL = Path("docs") / "evidence"


def load_evidence_records(repo_root: Path) -> list[dict[str, Any]]:
    """Load JSON evidence packets under ``docs/evidence`` (read-only).

    Unreadable or non-object JSON is skipped with an honest skip record rather
    than fabricated content.
    """
    root = repo_root.expanduser().resolve()
    evidence_dir = root / EVIDENCE_REL
    records: list[dict[str, Any]] = []
    if not evidence_dir.is_dir():
        return records

    for path in sorted(evidence_dir.rglob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            records.append(
                {
                    "path": rel,
                    "parse_status": "unreadable",
                    "error": type(exc).__name__,
                    "payload": None,
                }
            )
            continue
        if not isinstance(raw, dict):
            records.append(
                {
                    "path": rel,
                    "parse_status": "non_object",
                    "error": "expected-json-object",
                    "payload": None,
                }
            )
            continue
        records.append(
            {
                "path": rel,
                "parse_status": "ok",
                "error": None,
                "payload": raw,
            }
        )
    return records


def load_optional_ops_coverage(vault_path: Path | None) -> dict[str, Any]:
    """Inventory optional vault ops receipts without inventing health."""
    if vault_path is None:
        return {
            "vault_provided": False,
            "kinds": {},
            "receipt_rows": 0,
            "health_snapshot": "not_requested",
            "workflow_metrics": "not_requested",
            "ops_report": "not_requested",
            "events_stream": "not_requested",
            "note": "No vault path supplied; ops coverage not scanned.",
        }

    vault = vault_path.expanduser().resolve()
    inventory = inventory_ops_receipts(vault, limit=100)
    ops = vault / "generated" / "ops"

    def _presence(rel: Path) -> str:
        path = ops / rel
        if not path.exists():
            return "absent"
        if not path.is_file():
            return "unknown"
        return "present"

    return {
        "vault_provided": True,
        "kinds": dict(inventory.get("kinds") or {}),
        "receipt_rows": len(inventory.get("receipts") or []),
        "ops_root_status": inventory.get("ops_root"),
        "health_snapshot": _presence(Path("health-snapshot.json")),
        "workflow_metrics": _presence(Path("workflow-metrics.json")),
        "ops_report": _presence(Path("ops-report.json")),
        "events_stream": _presence(Path("events") / "stream.jsonl"),
        "note": (
            "Absence stays unknown; receipt presence is not health, completion, "
            "or Truth Core. Optional consume only."
        ),
        "truth_boundary": inventory.get("truth_boundary"),
    }
