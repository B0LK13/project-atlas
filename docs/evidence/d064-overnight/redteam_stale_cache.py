#!/usr/bin/env python3
"""D-064 overnight red-team: TOCTOU connect + stale cache truth (frozen tip 9c71cc2).

Stand-alone — does not modify src/.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from project_atlas.estate_discovery import (  # noqa: E402
    EstateDiscoveryError,
    connect_discovered_candidate,
    discover_estate,
)

OUT_DIR = Path(__file__).resolve().parent
INDIVIDUAL = OUT_DIR / "redteam_stale_cache-results.json"

ALPHA_UUID = "11111111-1111-4111-8111-111111111111"
BETA_UUID = "22222222-2222-4222-8222-222222222222"


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


def _seed_project(root: Path, project_id: str, project_uuid: str) -> Path:
    _write(
        root / ".atlas-project.yaml",
        f"project:\n  id: {project_id}\nproject_uuid: {project_uuid}\n",
    )
    _write(root / "README.md", f"# {project_id}\n")
    (root / ".git").mkdir(parents=True, exist_ok=True)
    return root


def _finding(
    severity: str, code: str, detail: str, *, evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    row: dict[str, Any] = {"severity": severity, "code": code, "detail": detail}
    if evidence is not None:
        row["evidence"] = evidence
    return row


def _expect_connect_fail(
    report: dict[str, Any],
    candidate_id: str,
    vault: Path,
    *,
    label: str,
) -> dict[str, Any]:
    try:
        connect_discovered_candidate(
            report, candidate_id, vault=vault, dry_run=True
        )
        return {
            "label": label,
            "failed_closed": False,
            "error": None,
        }
    except EstateDiscoveryError as exc:
        return {
            "label": label,
            "failed_closed": True,
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "label": label,
            "failed_closed": True,
            "error": f"{type(exc).__name__}: {exc}",
            "unexpected_exception_type": type(exc).__name__,
        }


def run() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    stale_cache_truth = 0
    cache_used_for_skip_seen = False

    with tempfile.TemporaryDirectory(prefix="d064-stale-") as tmp:
        base = Path(tmp)
        estate = base / "estate"
        proj = estate / "alpha"
        vault = base / "vault"
        (vault / "projects" / "alpha").mkdir(parents=True)
        (vault / "projects" / "beta").mkdir(parents=True)
        _allocation(vault, "alpha", ALPHA_UUID)
        _allocation(vault, "beta", BETA_UUID)
        _seed_project(proj, "alpha", ALPHA_UUID)

        # --- discover then mutate marker → connect must fail ---
        report_marker = discover_estate(estate, vault=vault, include_knowledge=False)
        cand = report_marker["candidates"]["projects"][0]
        cid = cand["candidate_id"]
        _write(
            proj / ".atlas-project.yaml",
            f"project:\n  id: beta\nproject_uuid: {BETA_UUID}\n",
        )
        marker_res = _expect_connect_fail(
            report_marker, cid, vault, label="mutate_marker"
        )
        checks["discover_mutate_marker_connect"] = marker_res
        if not marker_res["failed_closed"]:
            findings.append(
                _finding(
                    "HIGH",
                    "TOCTOU_MARKER_CONNECT_ALLOWED",
                    "connect succeeded after marker mutation (stale report authority)",
                )
            )

        # Reset identity for next case
        _write(
            proj / ".atlas-project.yaml",
            f"project:\n  id: alpha\nproject_uuid: {ALPHA_UUID}\n",
        )

        # --- discover then change uuid → connect fail ---
        report_uuid = discover_estate(estate, vault=vault, include_knowledge=False)
        cand_u = report_uuid["candidates"]["projects"][0]
        _write(
            proj / ".atlas-project.yaml",
            f"project:\n  id: alpha\nproject_uuid: {BETA_UUID}\n",
        )
        uuid_res = _expect_connect_fail(
            report_uuid, cand_u["candidate_id"], vault, label="change_uuid"
        )
        checks["discover_change_uuid_connect"] = uuid_res
        if not uuid_res["failed_closed"]:
            findings.append(
                _finding(
                    "HIGH",
                    "TOCTOU_UUID_CONNECT_ALLOWED",
                    "connect succeeded after UUID change (stale report authority)",
                )
            )

        # Reset
        _write(
            proj / ".atlas-project.yaml",
            f"project:\n  id: alpha\nproject_uuid: {ALPHA_UUID}\n",
        )

        # --- discover then delete path → connect fail ---
        report_del = discover_estate(estate, vault=vault, include_knowledge=False)
        cand_d = report_del["candidates"]["projects"][0]
        shutil.rmtree(proj)
        del_res = _expect_connect_fail(
            report_del, cand_d["candidate_id"], vault, label="delete_path"
        )
        checks["discover_delete_path_connect"] = del_res
        if not del_res["failed_closed"]:
            findings.append(
                _finding(
                    "HIGH",
                    "TOCTOU_DELETE_CONNECT_ALLOWED",
                    "connect succeeded after candidate path deletion",
                )
            )

        # Recreate for cache truth case
        _seed_project(proj, "alpha", ALPHA_UUID)

        # --- scan, change identity, rescan with prior_cache → new identity ---
        report1 = discover_estate(estate, vault=vault, include_knowledge=False)
        if report1.get("incremental_foundation", {}).get("cache_used_for_skip") is True:
            cache_used_for_skip_seen = True
            findings.append(
                _finding(
                    "HIGH",
                    "CACHE_USED_FOR_SKIP",
                    "initial scan set cache_used_for_skip=True",
                )
            )
        fp1 = report1["candidates"]["projects"][0]["fingerprint"]
        if fp1.get("atlas_project_id") != "alpha":
            findings.append(
                _finding(
                    "MEDIUM",
                    "UNEXPECTED_INITIAL_IDENTITY",
                    f"expected alpha, got {fp1.get('atlas_project_id')}",
                )
            )

        _write(
            proj / ".atlas-project.yaml",
            f"project:\n  id: beta\nproject_uuid: {BETA_UUID}\n",
        )
        stale_cache = {"entries": report1.get("_cache_entries")}
        report2 = discover_estate(
            estate,
            vault=vault,
            include_knowledge=False,
            prior_cache=stale_cache,
        )
        inc2 = report2.get("incremental_foundation") or {}
        if inc2.get("cache_used_for_skip") is True:
            cache_used_for_skip_seen = True
            findings.append(
                _finding(
                    "HIGH",
                    "CACHE_USED_FOR_SKIP",
                    "rescan with prior_cache set cache_used_for_skip=True",
                )
            )
        projects2 = report2.get("candidates", {}).get("projects") or []
        if not projects2:
            stale_cache_truth = 1
            findings.append(
                _finding(
                    "HIGH",
                    "STALE_CACHE_TRUTH",
                    "rescan with prior_cache produced no projects",
                )
            )
            live_id = None
        else:
            live_id = projects2[0].get("fingerprint", {}).get("atlas_project_id")
            if live_id != "beta":
                stale_cache_truth = 1
                findings.append(
                    _finding(
                        "HIGH",
                        "STALE_CACHE_TRUTH",
                        "rescan with prior_cache did not reflect new identity "
                        f"(got {live_id!r}, expected 'beta')",
                        evidence={
                            "fingerprint": projects2[0].get("fingerprint"),
                            "cache_used_for_skip": inc2.get("cache_used_for_skip"),
                        },
                    )
                )

        checks["stale_cache_rescan"] = {
            "cache_used_for_skip": inc2.get("cache_used_for_skip"),
            "live_atlas_project_id": live_id,
            "expected": "beta",
            "prior_cache_entries": len((stale_cache.get("entries") or {})),
        }

    hard_counters = {
        "STALE_CACHE_TRUTH": stale_cache_truth,
        "CACHE_USED_FOR_SKIP_TRUE": 1 if cache_used_for_skip_seen else 0,
    }
    # Explicit boolean required by directive
    hard_counters["cache_used_for_skip"] = hard_counters["CACHE_USED_FOR_SKIP_TRUE"]

    high = [f for f in findings if f["severity"] == "HIGH"]
    hard_ok = all(v == 0 for v in hard_counters.values())
    status = "PASS" if hard_ok and not high else "FAIL"

    return {
        "script": "redteam_stale_cache.py",
        "frozen_tip": "9c71cc2",
        "status": status,
        "hard_counters": hard_counters,
        "checks": checks,
        "findings": findings,
        "high_findings": len(high),
    }


def main() -> int:
    result = run()
    INDIVIDUAL.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS" or result["high_findings"]:
        return 1
    if any(v != 0 for v in result["hard_counters"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
