#!/usr/bin/env python3
"""D-064 overnight: estate discovery determinism replay.

Same estate scanned 3 times, plus once with prior_cache from the first run.
Compares sorted candidate_ids, match_states, and categories.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import discover_estate

OUT_DIR = Path(__file__).resolve().parent
RESULT_PATH = OUT_DIR / "determinism_replay.result.json"

ALPHA_UUID = "11111111-1111-4111-8111-111111111111"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _allocation(vault: Path, project_id: str, project_uuid: str) -> None:
    path = (
        vault
        / "receipts"
        / "source-lineage"
        / f"project-{project_id}-allocation.json"
    )
    _write(
        path,
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "project-identity-allocation",
                "project": project_id,
                "project_uuid": project_uuid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def build_fixture(root: Path) -> tuple[Path, Path]:
    estate = root / "estate"
    vault = root / "vault"

    alpha = estate / "alpha"
    _write(
        alpha / ".atlas-project.yaml",
        f"project:\n  id: alpha\nproject_uuid: {ALPHA_UUID}\n",
    )
    _write(alpha / "README.md", "# Alpha\n")
    _write(alpha / "pyproject.toml", '[project]\nname = "alpha-app"\n')
    (alpha / "src").mkdir(parents=True)
    (alpha / ".git").mkdir()
    _write(
        alpha / ".git" / "config",
        '[remote "origin"]\n\turl = https://example.com/alpha.git\n',
    )

    beta = estate / "beta-notes"
    _write(beta / "README.md", "# Beta\n")
    _write(beta / "package.json", '{"name":"beta-notes"}\n')
    (beta / "src").mkdir(parents=True)
    (beta / ".git").mkdir()

    notes = estate / "obsidian-brain"
    (notes / ".obsidian").mkdir(parents=True)
    _write(notes / ".obsidian" / "app.json", "{}\n")
    for name in ("x.md", "y.md", "z.md"):
        _write(notes / name, "note\n")

    (vault / "projects" / "alpha").mkdir(parents=True)
    _allocation(vault, "alpha", ALPHA_UUID)
    _write(
        alpha / ".atlas" / "connect.json",
        json.dumps(
            {
                "schema_version": 1,
                "schema": "atlas.connect.bind.v1",
                "project_root": str(alpha.resolve()),
                "vault": str(vault.resolve()),
                "project_id": "alpha",
                "project_ids": ["alpha"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return estate, vault


def extract_signature(report: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    candidates = report.get("candidates") if isinstance(report.get("candidates"), dict) else {}
    for bucket in ("projects", "knowledge"):
        for item in candidates.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "match_state": item.get("match_state"),
                    "category": item.get("category"),
                    "kind": item.get("kind"),
                }
            )
    rows.sort(key=lambda r: str(r.get("candidate_id") or ""))
    return {
        "candidate_ids": [r["candidate_id"] for r in rows],
        "match_states": [r["match_state"] for r in rows],
        "categories": [r["category"] for r in rows],
        "rows": rows,
        "counts": report.get("counts"),
        "scan_complete": (report.get("scan") or {}).get("scan_complete"),
        "truncation_reason": (report.get("scan") or {}).get("truncation_reason"),
    }


def drift(field: str, signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = signatures[0].get(field)
    events: list[dict[str, Any]] = []
    for idx, sig in enumerate(signatures[1:], start=1):
        other = sig.get(field)
        if other != base:
            events.append(
                {
                    "field": field,
                    "baseline_run": 0,
                    "drift_run": idx,
                    "baseline": base,
                    "observed": other,
                }
            )
    return events


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="d064-determinism-") as tmp:
        estate, vault = build_fixture(Path(tmp))

        reports: list[dict[str, Any]] = []
        for _ in range(3):
            reports.append(discover_estate(estate, vault=vault))

        prior_cache = {
            "entries": reports[0].get("_cache_entries") or {},
            "schema": "estate-discovery-cache-v1",
        }
        reports.append(
            discover_estate(estate, vault=vault, prior_cache=prior_cache)
        )

        signatures = [extract_signature(r) for r in reports]
        id_drifts = drift("candidate_ids", signatures)
        state_drifts = drift("match_states", signatures)
        cat_drifts = drift("categories", signatures)

        result = {
            "schema": "d064-overnight-determinism-replay-v1",
            "package_id": "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001",
            "runs": len(reports),
            "runs_with_prior_cache": 1,
            "signatures": [
                {
                    "run": i,
                    "with_prior_cache": i == 3,
                    "candidate_ids": sig["candidate_ids"],
                    "match_states": sig["match_states"],
                    "categories": sig["categories"],
                    "counts": sig["counts"],
                    "scan_complete": sig["scan_complete"],
                    "truncation_reason": sig["truncation_reason"],
                    "cache_used_for_skip": (
                        reports[i].get("incremental_foundation") or {}
                    ).get("cache_used_for_skip"),
                }
                for i, sig in enumerate(signatures)
            ],
            "drift_events": {
                "candidate_ids": id_drifts,
                "match_states": state_drifts,
                "categories": cat_drifts,
            },
            "counters": {
                "CANDIDATE_ID_DRIFT": len(id_drifts),
                "MATCH_STATE_DRIFT": len(state_drifts),
                "CATEGORY_DRIFT": len(cat_drifts),
            },
            "pass": not (id_drifts or state_drifts or cat_drifts),
        }

        RESULT_PATH.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result["counters"], indent=2, sort_keys=True))
        print(f"wrote {RESULT_PATH}")
        print(f"pass={result['pass']}")
        return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
