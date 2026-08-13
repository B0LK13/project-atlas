#!/usr/bin/env python3
"""D-049 / D-064 overnight red-team: knowledge + Obsidian association honesty.

Does not modify src/project_atlas. Exercises project_atlas.estate_discovery only.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import discover_estate

OUT_DIR = Path(__file__).resolve().parent
ESTATE_ROOT = Path("/tmp/d064-redteam/knowledge-obsidian")
VAULT_ROOT = Path("/tmp/d064-redteam/vault")
RESULTS_PATH = OUT_DIR / "redteam_knowledge_obsidian_results.json"

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


def _seed_vault(vault: Path) -> list[str]:
    """Seed governed vault identities; return project dir names before discover."""
    if vault.exists():
        shutil.rmtree(vault)
    for pid, uuid in (("alpha", ALPHA_UUID), ("beta", BETA_UUID)):
        (vault / "projects" / pid).mkdir(parents=True)
        _write(vault / "projects" / pid / "project.md", f"# {pid}\n")
        _allocation(vault, pid, uuid)
    return sorted(p.name for p in (vault / "projects").iterdir() if p.is_dir())


def _build_estate(estate: Path) -> None:
    if estate.exists():
        shutil.rmtree(estate)
    estate.mkdir(parents=True)

    # Scenario 1: project-local nested research → expect KNOWLEDGE_PROJECT_MATCHED
    alpha = estate / "alpha"
    _write(alpha / "README.md", "# Alpha\n")
    _write(alpha / "pyproject.toml", '[project]\nname = "alpha"\n')
    (alpha / "src").mkdir(parents=True)
    (alpha / ".git").mkdir()
    _write(
        alpha / ".atlas-project.yaml",
        f"project:\n  id: alpha\nproject_uuid: {ALPHA_UUID}\n",
    )
    research = alpha / "research"
    for name in ("paper.md", "notes.md", "more.md"):
        _write(research / name, f"{name} body\n")

    beta = estate / "beta"
    _write(beta / "README.md", "# Beta\n")
    _write(beta / "package.json", '{"name":"beta"}\n')
    (beta / "src").mkdir(parents=True)
    (beta / ".git").mkdir()
    _write(
        beta / ".atlas-project.yaml",
        f"project:\n  id: beta\nproject_uuid: {BETA_UUID}\n",
    )

    # Scenario 2: personal Obsidian vault — must not auto-assign wholesale
    personal = estate / "personal-brain"
    (personal / ".obsidian").mkdir(parents=True)
    _write(personal / ".obsidian" / "app.json", "{}\n")
    for name in ("daily.md", "inbox.md", "journal.md"):
        _write(personal / name, "note\n")

    # Scenario 3: Obsidian dirname mentions multiple vault project ids
    # (alpha + beta) → must not silently pick one; red-team observes relation.
    multi = estate / "alpha-beta-shared-notes"
    (multi / ".obsidian").mkdir(parents=True)
    _write(multi / ".obsidian" / "app.json", "{}\n")
    for name in ("a.md", "b.md", "c.md"):
        _write(multi / name, "shared\n")


def _knowledge_by_name(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in report["candidates"]["knowledge"]:
        out[Path(row["path"]).name] = row
    return out


def _count_silent_assignment(knowledge: list[dict[str, Any]]) -> int:
    """Silent assignment: matched to a project without required_review."""
    n = 0
    for row in knowledge:
        if row.get("matched_project_id") and not row.get("required_review"):
            # Nested research under a single project is intentional structural match.
            if row.get("knowledge_relation") == "KNOWLEDGE_PROJECT_MATCHED":
                continue
            n += 1
        # Obsidian with a matched id and no review is always silent/bad.
        if (
            row.get("kind") == "obsidian_vault"
            and row.get("matched_project_id")
            and not row.get("required_review")
        ):
            n += 1
    return n


def _count_cross_project_leak(
    knowledge: list[dict[str, Any]], projects: list[dict[str, Any]]
) -> int:
    """Knowledge nested under project A but matched to a different project id."""
    project_roots = [
        (Path(p["path"]), p.get("matched_project_id") or p.get("display_name"))
        for p in projects
    ]
    leaks = 0
    for row in knowledge:
        kpath = Path(row["path"])
        matched = row.get("matched_project_id")
        if not matched:
            continue
        parents = [
            (root, pid)
            for root, pid in project_roots
            if kpath != root and str(kpath).startswith(str(root) + "/")
        ]
        if not parents:
            continue
        parents.sort(key=lambda item: len(item[0].parts), reverse=True)
        structural_pid = parents[0][1]
        if structural_pid and structural_pid != matched:
            leaks += 1
    return leaks


def main() -> int:
    projects_before = _seed_vault(VAULT_ROOT)
    _build_estate(ESTATE_ROOT)

    t0 = time.perf_counter()
    report = discover_estate(ESTATE_ROOT, vault=VAULT_ROOT)
    elapsed = time.perf_counter() - t0

    projects_after = sorted(
        p.name for p in (VAULT_ROOT / "projects").iterdir() if p.is_dir()
    )
    by_name = _knowledge_by_name(report)
    knowledge = report["candidates"]["knowledge"]
    projects = report["candidates"]["projects"]

    nested = by_name.get("research")
    personal = by_name.get("personal-brain")
    multi = by_name.get("alpha-beta-shared-notes")

    # OBSIDIAN_AUTO_INGEST: discovery must never create/ingest into vault projects.
    vault_unchanged = projects_before == projects_after
    obsidian_auto_ingest = 0 if vault_unchanged else 1

    silent = _count_silent_assignment(knowledge)
    # Also flag Obsidian wholesale assignment as silent if matched without review.
    for row in knowledge:
        if (
            row.get("kind") == "obsidian_vault"
            and row.get("knowledge_relation") == "KNOWLEDGE_PROJECT_MATCHED"
            and not row.get("required_review")
        ):
            silent += 1

    cross_leak = _count_cross_project_leak(knowledge, projects)

    scenarios = {
        "nested_research_under_project": {
            "path_name": "research",
            "found": nested is not None,
            "knowledge_relation": (nested or {}).get("knowledge_relation"),
            "required_review": (nested or {}).get("required_review"),
            "matched_project_id": (nested or {}).get("matched_project_id"),
            "expect": "KNOWLEDGE_PROJECT_MATCHED",
            "pass": (nested or {}).get("knowledge_relation")
            == "KNOWLEDGE_PROJECT_MATCHED",
        },
        "personal_obsidian_not_wholesale": {
            "path_name": "personal-brain",
            "found": personal is not None,
            "kind": (personal or {}).get("kind"),
            "knowledge_relation": (personal or {}).get("knowledge_relation"),
            "required_review": (personal or {}).get("required_review"),
            "matched_project_id": (personal or {}).get("matched_project_id"),
            "vault_projects_before": projects_before,
            "vault_projects_after": projects_after,
            "vault_projects_unchanged": vault_unchanged,
            "expect": {
                "kind": "obsidian_vault",
                "required_review": True,
                "not_auto_assigned": True,
                "no_ingest": True,
            },
            "pass": bool(
                personal
                and personal.get("kind") == "obsidian_vault"
                and personal.get("required_review") is True
                and personal.get("knowledge_relation")
                in {"KNOWLEDGE_UNMATCHED", "KNOWLEDGE_AMBIGUOUS"}
                and vault_unchanged
            ),
        },
        "obsidian_multi_project_dirname": {
            "path_name": "alpha-beta-shared-notes",
            "found": multi is not None,
            "kind": (multi or {}).get("kind"),
            "knowledge_relation": (multi or {}).get("knowledge_relation"),
            "match_state": (multi or {}).get("match_state"),
            "required_review": (multi or {}).get("required_review"),
            "matched_project_id": (multi or {}).get("matched_project_id"),
            "match_evidence": (multi or {}).get("match_evidence"),
            "expect": (
                "not silently assigned to a single project; "
                "required_review; dirname mentions alpha and beta"
            ),
            "pass": bool(
                multi
                and multi.get("kind") == "obsidian_vault"
                and multi.get("required_review") is True
                and multi.get("knowledge_relation")
                != "KNOWLEDGE_PROJECT_MATCHED"
                and multi.get("matched_project_id") is None
            ),
            "note": (
                "When dirname contains multiple vault project ids, current "
                "implementation returns KNOWLEDGE_UNMATCHED (fail-closed) "
                "rather than KNOWLEDGE_AMBIGUOUS — still not silent assignment."
            ),
        },
    }

    counters = {
        "OBSIDIAN_AUTO_INGEST": obsidian_auto_ingest,
        "KNOWLEDGE_SILENT_PROJECT_ASSIGNMENT": silent,
        "CROSS_PROJECT_KNOWLEDGE_LEAK": cross_leak,
    }

    results: dict[str, Any] = {
        "label": "D064_OVERNIGHT_REDTEAM_KNOWLEDGE_OBSIDIAN",
        "package_id": report.get("package_id"),
        "authorized_root": str(ESTATE_ROOT),
        "vault": str(VAULT_ROOT),
        "scan_seconds": round(elapsed, 6),
        "counts": report.get("counts"),
        "scan": report.get("scan"),
        "scenarios": scenarios,
        "counters": counters,
        "all_scenarios_pass": all(s["pass"] for s in scenarios.values()),
        "honesty": {
            "DISCOVER_NE_INGEST": vault_unchanged,
            "invariant": report.get("invariant"),
        },
        "knowledge_summary": [
            {
                "name": Path(k["path"]).name,
                "kind": k.get("kind"),
                "knowledge_relation": k.get("knowledge_relation"),
                "required_review": k.get("required_review"),
                "matched_project_id": k.get("matched_project_id"),
            }
            for k in knowledge
        ],
    }

    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nWrote {RESULTS_PATH}", flush=True)
    return 0 if results["all_scenarios_pass"] and all(
        v == 0 for v in counters.values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
