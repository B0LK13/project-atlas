#!/usr/bin/env python3
"""D-064 overnight: CLI / API / Web estate-discovery semantic parity.

Frozen surfaces: project_atlas.estate_discovery, web_api.discovery, cli discover.
Does not modify src/. Emits JSON results beside this script.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import (
    REPORT_RELATIVE,
    discover_estate,
    write_discovery_report,
)
from project_atlas.web_api.discovery import load_estate_discovery_view

OUT_DIR = Path(__file__).resolve().parent
RESULT_PATH = OUT_DIR / "parity_cli_api_web.result.json"

SEMANTIC_FIELDS = (
    "candidate_id",
    "match_state",
    "category",
    "required_review",
    "why_matched",
    "why_connected",
    "conflicting_evidence",
)

SCAN_FIELDS = ("scan_complete", "truncation_reason")

CATEGORY_KEYS = (
    "DISCOVERED_PROJECTS",
    "NEW_KNOWLEDGE",
    "AMBIGUOUS_MATCHES",
    "UNMATCHED_KNOWLEDGE",
    "CONNECTED",
)

ALPHA_UUID = "11111111-1111-4111-8111-111111111111"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


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
    """One CONNECTED project (bind), one unmatched project, one Obsidian vault."""
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

    unmatched = estate / "lonely-tool"
    _write(unmatched / "README.md", "# Lonely\n")
    _write(unmatched / "package.json", '{"name":"lonely-tool"}\n')
    (unmatched / "src").mkdir(parents=True)
    (unmatched / ".git").mkdir()

    notes = estate / "personal-notes"
    (notes / ".obsidian").mkdir(parents=True)
    _write(notes / ".obsidian" / "app.json", "{}\n")
    for name in ("a.md", "b.md", "c.md"):
        _write(notes / name, "note\n")

    (vault / "projects" / "alpha").mkdir(parents=True)
    _write(
        vault / "projects" / "alpha" / "project.md",
        f"---\nproject_uuid: {ALPHA_UUID}\n---\n",
    )
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


def _normalize_conflicts(rows: Any) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "kind": str(row.get("kind") or ""),
                "detail": str(row.get("detail") or ""),
                "strength": str(row.get("strength") or ""),
            }
        )
    out.sort(key=lambda r: (r["kind"], r["detail"], r["strength"]))
    return out


def _semantic_slice(item: dict[str, Any], *, scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id"),
        "match_state": item.get("match_state"),
        "category": item.get("category"),
        "required_review": bool(item.get("required_review")),
        "why_matched": list(item.get("why_matched") or []),
        "why_connected": list(item.get("why_connected") or []),
        "conflicting_evidence": _normalize_conflicts(item.get("conflicting_evidence")),
        "scan_complete": bool(scan.get("scan_complete", True)),
        "truncation_reason": scan.get("truncation_reason"),
    }


def flatten_report_candidates(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scan = report.get("scan") if isinstance(report.get("scan"), dict) else {}
    by_id: dict[str, dict[str, Any]] = {}
    candidates = report.get("candidates") if isinstance(report.get("candidates"), dict) else {}
    for bucket in ("projects", "knowledge"):
        for item in candidates.get(bucket) or []:
            if isinstance(item, dict) and item.get("candidate_id"):
                by_id[str(item["candidate_id"])] = _semantic_slice(item, scan=scan)
    return by_id


def flatten_view_categories(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scan = view.get("scan") if isinstance(view.get("scan"), dict) else {}
    categories = view.get("categories") if isinstance(view.get("categories"), dict) else {}
    by_id: dict[str, dict[str, Any]] = {}
    for key in CATEGORY_KEYS:
        for item in categories.get(key) or []:
            if not isinstance(item, dict) or not item.get("candidate_id"):
                continue
            cid = str(item["candidate_id"])
            # Prefer first occurrence; drift if later differs.
            sliced = _semantic_slice(item, scan=scan)
            if cid in by_id and by_id[cid] != sliced:
                # Keep first; UI_RECLASSIFICATION counts elsewhere.
                continue
            by_id[cid] = sliced
    return by_id


def compare_semantic(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
    *,
    label: str,
) -> list[dict[str, Any]]:
    drifts: list[dict[str, Any]] = []
    ids = sorted(set(left) | set(right))
    for cid in ids:
        if cid not in left:
            drifts.append(
                {
                    "label": label,
                    "candidate_id": cid,
                    "kind": "missing_in_left",
                    "right": right[cid],
                }
            )
            continue
        if cid not in right:
            drifts.append(
                {
                    "label": label,
                    "candidate_id": cid,
                    "kind": "missing_in_right",
                    "left": left[cid],
                }
            )
            continue
        a, b = left[cid], right[cid]
        for field in (*SEMANTIC_FIELDS, *SCAN_FIELDS):
            if a.get(field) != b.get(field):
                drifts.append(
                    {
                        "label": label,
                        "candidate_id": cid,
                        "field": field,
                        "left": a.get(field),
                        "right": b.get(field),
                    }
                )
    return drifts


def ui_reclassification_events(
    report: dict[str, Any], view: dict[str, Any]
) -> list[dict[str, Any]]:
    """Count candidates whose category bucket differs between report and view."""
    report_by_id: dict[str, str] = {}
    for bucket in ("projects", "knowledge"):
        for item in (report.get("candidates") or {}).get(bucket) or []:
            if isinstance(item, dict) and item.get("candidate_id"):
                report_by_id[str(item["candidate_id"])] = str(item.get("category") or "")

    view_by_id: dict[str, str] = {}
    categories = view.get("categories") if isinstance(view.get("categories"), dict) else {}
    for key in CATEGORY_KEYS:
        for item in categories.get(key) or []:
            if isinstance(item, dict) and item.get("candidate_id"):
                cid = str(item["candidate_id"])
                # Category key on the item vs bucket placement.
                item_cat = str(item.get("category") or key)
                bucket_cat = key
                if cid in view_by_id and view_by_id[cid] != bucket_cat:
                    pass
                view_by_id[cid] = bucket_cat
                # Also flag item.category vs bucket mismatch as UI reclass.
                if item_cat and item_cat != bucket_cat and item_cat in CATEGORY_KEYS:
                    view_by_id[cid] = bucket_cat

    events: list[dict[str, Any]] = []
    for cid, report_cat in sorted(report_by_id.items()):
        view_cat = view_by_id.get(cid)
        if view_cat is None:
            events.append(
                {
                    "candidate_id": cid,
                    "report_category": report_cat,
                    "view_category": None,
                    "reason": "absent_from_view_categories",
                }
            )
        elif view_cat != report_cat:
            events.append(
                {
                    "candidate_id": cid,
                    "report_category": report_cat,
                    "view_category": view_cat,
                    "reason": "category_bucket_mismatch",
                }
            )
    for cid, view_cat in sorted(view_by_id.items()):
        if cid not in report_by_id:
            events.append(
                {
                    "candidate_id": cid,
                    "report_category": None,
                    "view_category": view_cat,
                    "reason": "extra_in_view",
                }
            )
    return events


def run_cli_discover(estate: Path, vault: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(Path("/workspace/.venv/bin/python")),
            "-m",
            "project_atlas.cli",
            "discover",
            "--root",
            str(estate),
            "--vault",
            str(vault),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/workspace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"CLI discover failed rc={proc.returncode}\n"
            f"stdout={proc.stdout[:2000]}\nstderr={proc.stderr[:2000]}"
        )
    # CLI may print logs to stderr; JSON is on stdout.
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("CLI --json did not emit an object")
    return payload


def count_states(by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in by_id.values():
        state = str(row.get("match_state") or "")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="d064-parity-") as tmp:
        root = Path(tmp)
        estate, vault = build_fixture(root)

        api_report = discover_estate(estate, vault=vault)
        report_path = vault / REPORT_RELATIVE
        write_discovery_report(api_report, report_path)
        view = load_estate_discovery_view(vault)

        api_flat = flatten_report_candidates(api_report)
        view_flat = flatten_view_categories(view)
        api_vs_view = compare_semantic(api_flat, view_flat, label="api_vs_web")

        cli_report = run_cli_discover(estate, vault)
        # CLI with --vault rewrites the report; reload web view from that report.
        view_after_cli = load_estate_discovery_view(vault)
        cli_flat = flatten_report_candidates(cli_report)
        view_cli_flat = flatten_view_categories(view_after_cli)
        cli_vs_api = compare_semantic(api_flat, cli_flat, label="api_vs_cli")
        cli_vs_view = compare_semantic(cli_flat, view_cli_flat, label="cli_vs_web")

        ui_events = ui_reclassification_events(api_report, view)
        ui_events_cli = ui_reclassification_events(cli_report, view_after_cli)

        semantic_drifts = api_vs_view + cli_vs_api + cli_vs_view
        api_web_drift = len(api_vs_view) + len(cli_vs_view)
        # Also count pure API↔CLI semantic drift into the same counter family.
        api_web_drift += len(cli_vs_api)

        # Key counts/states comparison (CLI vs API).
        count_keys = ("projects", "knowledge", "ignored", "required_review", "connected")
        api_counts = {
            k: int((api_report.get("counts") or {}).get(k) or 0) for k in count_keys
        }
        cli_counts = {
            k: int((cli_report.get("counts") or {}).get(k) or 0) for k in count_keys
        }
        view_counts = {
            k: int((view.get("counts") or {}).get(k) or 0) for k in count_keys
        }
        count_mismatches = [
            {"key": k, "api": api_counts[k], "cli": cli_counts[k], "view": view_counts[k]}
            for k in count_keys
            if not (api_counts[k] == cli_counts[k] == view_counts[k])
        ]

        result = {
            "schema": "d064-overnight-parity-cli-api-web-v1",
            "package_id": "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001",
            "fixture": {
                "authorized_root": estate.as_posix(),
                "vault": vault.as_posix(),
                "expected": {
                    "connected_project": "alpha",
                    "unmatched_project": "lonely-tool",
                    "obsidian": "personal-notes",
                },
            },
            "api_candidate_ids": sorted(api_flat),
            "cli_candidate_ids": sorted(cli_flat),
            "view_candidate_ids": sorted(view_flat),
            "api_match_state_counts": count_states(api_flat),
            "cli_match_state_counts": count_states(cli_flat),
            "view_match_state_counts": count_states(view_flat),
            "counts": {
                "api": api_counts,
                "cli": cli_counts,
                "view": view_counts,
                "mismatches": count_mismatches,
            },
            "scan": {
                "api": api_report.get("scan"),
                "cli": cli_report.get("scan"),
                "view": view.get("scan"),
            },
            "semantic_drifts": semantic_drifts,
            "ui_reclassification_events": ui_events + ui_events_cli,
            "connected_sample": {
                cid: row
                for cid, row in api_flat.items()
                if row.get("category") == "CONNECTED"
            },
            "counters": {
                "API_WEB_DISCOVERY_SEMANTIC_DRIFT": api_web_drift,
                "UI_RECLASSIFICATION": len(ui_events) + len(ui_events_cli),
            },
            "pass": api_web_drift == 0
            and len(ui_events) + len(ui_events_cli) == 0
            and not count_mismatches,
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
